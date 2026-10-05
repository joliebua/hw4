"""Everything the Campus Customs agent and API read from the store database,
and the tools the agent can call.

Sections
  1. Database           paths and the SQLite connection helper
  2. Catalogue          products, stock by size, search, "you might also like"
  3. Saved chats        chat_messages for signed-in shoppers
  4. Sizes              "My size", size history, recommended size
  5. Agent tools        ShopDeps (per-turn state) and the 7 tools in SHOP_TOOLS

The database (data/campus_customs.db) is the single source of truth for price
and stock: the API routes in main.py and the agent's tools both call these
functions, so the shop pages and the chatbot always agree.

Every tool records the products, prices and quantities it returned on
ShopDeps, so the output validator in agent.py can check that a reply quotes
only what the database said. Data the tools can reach: the catalogue and
inventory tables; for a signed-in shopper, their own name, email, join date,
saved size, size history and chats. Nothing here reads password hashes,
sessions, or any other shopper's data, and nothing reaches the internet.
"""

from __future__ import annotations

import json
import re
import sqlite3
from collections import Counter
from contextlib import contextmanager
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterator, Literal

from pydantic_ai import ModelRetry, RunContext

from models import (
    Collection,
    Facet,
    PastChatMessage,
    ProductDetail,
    ProductFacts,
    ProductMatch,
    ProductSummary,
    SearchResults,
    ShopperProfile,
    SizeAvailability,
    SizeRecommendation,
    SizeStock,
    StockCheck,
    StockStatus,
    StoreFacets,
    User,
)


# =========================================================================== #
# 1. Database
# =========================================================================== #

PROJECT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_DIR / "data"
DB_FILE = DATA_DIR / "campus_customs.db"
IMAGES_DIR = DATA_DIR / "products"


@contextmanager
def connect() -> Iterator[sqlite3.Connection]:
    """Open a connection; commit if the block succeeds, roll back if it raises."""
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

# =========================================================================== #
# 2. Catalogue
# =========================================================================== #

SIZES = ["XS", "S", "M", "L", "XL", "XXL"]
LOW_STOCK_THRESHOLD = 10

Sort = Literal["relevance", "name", "price_asc", "price_desc"]

# The database's garment_type is free text ("pullover hoodie", "hooded
# sweatshirt", "hoodie" ...). Group it into a few shelves for browsing.
# Order matters: "full-zip hooded sweatshirt" is a full-zip, not a hoodie.
CATEGORY_RULES = [
    ("quarter-zip", "quarter-zip"),
    ("full-zip", "jacket"),
    ("jacket", "jacket"),
    ("hood", "hoodie"),
    ("long-sleeve", "long-sleeve"),
    ("t-shirt", "t-shirt"),
    ("crewneck", "crewneck"),
    ("sweatshirt", "crewneck"),
]

# Curated shelves for the Home page tiles. The catalogue has no single tag for
# "family" or "residential college", so each collection lists the name
# phrases that put a product on that shelf (any one phrase is enough).
COLLECTIONS: dict[str, tuple[str, list[str]]] = {
    "family": (
        "For the whole family",
        ["yale mom", "yale dad", "grandpa", "grandma", "yale aunt", "yale uncle", "yale cousin", "yale brother", "yale sister"],
    ),
    "sports": (
        "Game day",
        ["sports", "baseball", "soccer", "hockey", "diving", "tennis", "golf", "squash", "lacrosse",
         "fencing", "sailing", "volleyball", "swimming", "football", "track", "basketball"],
    ),
    "colleges": (
        "Residential colleges",
        ["benjamin franklin", "berkeley", "branford", "davenport", "grace hopper", "jonathan edwards",
         "morse", "pauli murray", "pierson", "saybrook", "silliman", "ezra stiles", "timothy dwight", "trumbull"],
    ),
    "schools": (
        "Graduate & professional schools",
        ["school of", "law school", "divinity school", "forest school"],
    ),
}


def category_for(garment_type: str) -> str:
    g = garment_type.lower()
    return next((cat for key, cat in CATEGORY_RULES if key in g), "other")


def in_collection(name: str, key: str) -> bool:
    return any(phrase in name.lower() for phrase in COLLECTIONS[key][1])


def short_text(text: str, limit: int = 100) -> str:
    """First sentence, trimmed at a word boundary so cards stay tidy."""
    match = re.match(r"(.+?[.!?])(\s|$)", text)
    sentence = match.group(1) if match else text
    if len(sentence) <= limit:
        return sentence
    return sentence[:limit].rsplit(" ", 1)[0].rstrip(",;:—-") + "…"


def image_url(image_file_path: str) -> str:
    # Paths are stored relative to data/, e.g. "products/yale-mom-hoodie.jpg".
    # Only the products folder is served, never the database file beside it.
    return "/api/images/" + Path(image_file_path).name


def _stock_for(conn: sqlite3.Connection, ids: list[str]) -> dict[str, dict[str, int]]:
    out: dict[str, dict[str, int]] = {pid: {} for pid in ids}
    if not ids:
        return out
    marks = ",".join("?" * len(ids))
    for r in conn.execute(
        f"SELECT product_id, size, quantity FROM inventory WHERE product_id IN ({marks})", ids
    ):
        out[r["product_id"]][r["size"]] = r["quantity"]
    return out


def _status(total: int) -> StockStatus:
    if total == 0:
        return StockStatus.SOLD_OUT
    if total <= LOW_STOCK_THRESHOLD:
        return StockStatus.LOW_STOCK
    return StockStatus.IN_STOCK


def _summary(row: sqlite3.Row, stock: dict[str, int]) -> ProductSummary:
    total = sum(stock.values())
    return ProductSummary(
        product_id=row["product_id"],
        name=row["name"],
        category=category_for(row["garment_type"]),
        garment_type=row["garment_type"],
        price=row["price"],
        short_description=short_text(row["description"]),
        image_url=image_url(row["image_file_path"]),
        total_stock=total,
        stock_status=_status(total),
        sizes_in_stock=[s for s in SIZES if stock.get(s, 0) > 0],
    )


def _detail(row: sqlite3.Row, stock: dict[str, int]) -> ProductDetail:
    return ProductDetail(
        **_summary(row, stock).model_dump(),
        description=row["description"],
        colors=json.loads(row["colors"]),
        search_tags=json.loads(row["search_tags"]),
        stock_by_size=[SizeStock(size=s, quantity=stock.get(s, 0)) for s in SIZES],
    )


# --------------------------------------------------------------------------- #
# Reads
# --------------------------------------------------------------------------- #


def get_product(product_id: str) -> ProductDetail | None:
    with connect() as conn:
        row = conn.execute("SELECT * FROM catalogue WHERE product_id = ?", (product_id,)).fetchone()
        if row is None:
            return None
        return _detail(row, _stock_for(conn, [product_id])[product_id])


def get_summaries(product_ids: list[str]) -> list[ProductSummary]:
    """Summaries in the order requested, skipping unknown IDs."""
    if not product_ids:
        return []
    with connect() as conn:
        marks = ",".join("?" * len(product_ids))
        rows = {
            r["product_id"]: r
            for r in conn.execute(f"SELECT * FROM catalogue WHERE product_id IN ({marks})", product_ids)
        }
        stock = _stock_for(conn, list(rows))
    return [_summary(rows[pid], stock[pid]) for pid in product_ids if pid in rows]


# --------------------------------------------------------------------------- #
# Lookup results for the agent
# --------------------------------------------------------------------------- #


def to_match(p: ProductSummary) -> ProductMatch:
    return ProductMatch(
        product_id=p.product_id,
        name=p.name,
        garment_type=p.garment_type,
        price=p.price,
        short_description=p.short_description,
        total_stock=p.total_stock,
        stock_status=p.stock_status,
        sizes_in_stock=p.sizes_in_stock,
        sold_out_sizes=[s for s in SIZES if s not in p.sizes_in_stock],
    )


def product_facts(product_id: str) -> ProductFacts | None:
    d = get_product(product_id)
    if d is None:
        return None
    return ProductFacts(
        product_id=d.product_id,
        name=d.name,
        garment_type=d.garment_type,
        description=d.description,
        colors=d.colors,
        price=d.price,
        total_stock=d.total_stock,
        stock_status=d.stock_status,
        stock_by_size=[SizeAvailability(size=s.size, quantity=s.quantity, in_stock=s.quantity > 0) for s in d.stock_by_size],
        sold_out_sizes=[s.size for s in d.stock_by_size if s.quantity == 0],
    )


def stock_check(product_id: str, size: str | None = None) -> StockCheck | None:
    """Stock for one product, optionally one size, with the facts written out."""
    d = get_product(product_id)
    if d is None:
        return None
    by_size = {s.size: s.quantity for s in d.stock_by_size}
    available = [SizeAvailability(size=s, quantity=q, in_stock=True) for s, q in by_size.items() if q > 0]
    sold_out = [s for s, q in by_size.items() if q == 0]
    others = ", ".join(f"{a.size} ({a.quantity})" for a in available)

    if size:
        size = size.upper()
        qty = by_size.get(size, 0)
        in_stock = qty > 0
        if in_stock:
            answer = f"{d.name} is in stock in size {size}: {qty} on hand. Price ${d.price:g}."
        else:
            rest = f" Sizes still in stock: {others}." if available else " It is sold out in every size."
            answer = f"{d.name} is SOLD OUT in size {size} (0 on hand).{rest} Price ${d.price:g}."
    else:
        qty = None
        in_stock = d.total_stock > 0
        if in_stock:
            gone = f" Sold out in: {', '.join(sold_out)}." if sold_out else ""
            answer = f"{d.name}: {d.total_stock} on hand. In stock: {others}.{gone} Price ${d.price:g}."
        else:
            answer = f"{d.name} is SOLD OUT in every size. Price ${d.price:g}."

    return StockCheck(
        product_id=d.product_id,
        name=d.name,
        price=d.price,
        size_requested=size,
        quantity=qty,
        in_stock=in_stock,
        available_sizes=available,
        sold_out_sizes=sold_out,
        total_stock=d.total_stock,
        answer=answer,
    )


def store_facets() -> StoreFacets:
    with connect() as conn:
        rows = conn.execute("SELECT name, garment_type, price FROM catalogue").fetchall()
    counts: dict[str, int] = {}
    for r in rows:
        cat = category_for(r["garment_type"])
        counts[cat] = counts.get(cat, 0) + 1
    prices = [r["price"] for r in rows]
    return StoreFacets(
        categories=[Facet(value=k, count=v) for k, v in sorted(counts.items(), key=lambda kv: -kv[1])],
        collections=[
            Collection(key=key, label=label, count=sum(in_collection(r["name"], key) for r in rows))
            for key, (label, _) in COLLECTIONS.items()
        ],
        product_count=len(rows),
        min_price=min(prices),
        max_price=max(prices),
    )


# --------------------------------------------------------------------------- #
# Search
# --------------------------------------------------------------------------- #

STOP_WORDS = {
    "a", "an", "the", "and", "or", "for", "with", "in", "of", "to", "my", "me", "i", "im",
    "something", "anything", "any", "some", "do", "you", "have", "got", "want", "looking",
    "need", "show", "find", "shirt", "merch", "please", "is", "are", "that", "this", "it",
    "on", "under", "over", "than", "less", "more", "size", "yale", "what", "which", "who",
    "gift", "ideas", "idea", "buy", "get", "like", "would", "could", "can",
}

# Shopper words → catalogue vocabulary.
SYNONYMS = {
    "tee": "t-shirt", "tees": "t-shirt", "tshirt": "t-shirt", "t-shirts": "t-shirt",
    "crew": "crewneck", "sweatshirts": "sweatshirt",
    "hoody": "hoodie", "hoodies": "hoodie", "hooded": "hood",
    "quarter": "quarter-zip", "1/4": "quarter-zip",
    "grey": "gray", "mother": "mom", "mum": "mom", "father": "dad",
    "grandmother": "grandma", "grandfather": "grandpa",
    "bulldogs": "bulldog", "colour": "color",
}

FIELD_WEIGHTS = {"name": 4.0, "garment": 3.0, "color": 3.0, "tags": 2.0, "description": 1.0}


def _tokens(text: str) -> list[str]:
    out = []
    for w in re.findall(r"[a-z0-9/&'-]+", text.lower()):
        w = SYNONYMS.get(w, w)
        if w in STOP_WORDS or len(w) < 2:
            continue
        if len(w) > 4 and w.endswith("s") and not w.endswith("ss"):
            w = w[:-1]  # crude singular: "hats" → "hat"
        out.append(w)
    return out


def _score(tokens: list[str], row: sqlite3.Row) -> float:
    fields = {
        "name": row["name"].lower(),
        "garment": row["garment_type"].lower(),
        "color": " ".join(json.loads(row["colors"])).lower(),
        "tags": " ".join(json.loads(row["search_tags"])).lower(),
        "description": row["description"].lower(),
    }
    score, matched = 0.0, 0
    for tok in tokens:
        hit = sum(
            FIELD_WEIGHTS[f] for f, text in fields.items() if re.search(rf"(?<![a-z0-9]){re.escape(tok)}", text)
        )
        score += hit
        matched += bool(hit)
    # Scale by the share of query words matched, so "navy hoodie" ranks navy
    # hoodies above grey hoodies and navy tees.
    return score * (matched / len(tokens)) ** 2


def search_products(
    query: str = "",
    category: str | None = None,
    collection: str | None = None,
    color: str | None = None,
    size: str | None = None,
    min_price: float | None = None,
    max_price: float | None = None,
    in_stock_only: bool = False,
    sold_out_in: str | None = None,
    sort: Sort = "relevance",
    limit: int | None = None,
) -> list[ProductSummary]:
    """Filter in SQL, rank by keyword relevance in Python."""
    where, params = [], []
    if min_price is not None:
        where.append("price >= ?")
        params.append(min_price)
    if max_price is not None:
        where.append("price <= ?")
        params.append(max_price)
    if color:
        where.append("LOWER(colors) LIKE ?")
        params.append(f"%{SYNONYMS.get(color.lower(), color.lower())}%")
    sql = "SELECT * FROM catalogue" + (f" WHERE {' AND '.join(where)}" if where else "")

    with connect() as conn:
        rows = conn.execute(sql, params).fetchall()
        stock = _stock_for(conn, [r["product_id"] for r in rows])

    if collection:
        rows = [r for r in rows if in_collection(r["name"], collection)]

    tokens = _tokens(query)
    size = size.upper() if size else None
    sold_out_in = sold_out_in.upper() if sold_out_in else None
    scored: list[tuple[float, ProductSummary]] = []
    for row in rows:
        s = stock[row["product_id"]]
        if size and s.get(size, 0) == 0:
            continue
        if in_stock_only and sum(s.values()) == 0:
            continue
        if sold_out_in and s.get(sold_out_in, 0) > 0:
            continue
        p = _summary(row, s)
        if category and p.category != category:
            continue
        score = _score(tokens, row) if tokens else 0.0
        if tokens and score <= 0:
            continue
        scored.append((score, p))

    if sort == "price_asc":
        scored.sort(key=lambda t: (t[1].price, t[1].name))
    elif sort == "price_desc":
        scored.sort(key=lambda t: (-t[1].price, t[1].name))
    elif sort == "name" or not tokens:
        scored.sort(key=lambda t: t[1].name)
    else:
        scored.sort(key=lambda t: (-t[0], t[1].name))

    results = [p for _, p in scored]
    return results[:limit] if limit else results


# --------------------------------------------------------------------------- #
# "You might also like"
# --------------------------------------------------------------------------- #

# Words in product names that say nothing about who an item is for.
GENERIC_NAME_WORDS = {
    "yale", "university", "t", "shirt", "tee", "hoodie", "hood", "crewneck", "creqneck", "sweatshirt",
    "sweater", "zip", "full", "quarter", "1", "4", "left", "chest", "logo", "college", "school", "of",
    "the", "and", "crest", "tri", "blend", "jacket", "fleece", "sports", "long", "sleeve", "heavyweight",
    "super", "crew", "neck", "pullover", "big", "basic", "vintage", "district", "vit", "champion",
    "reverse", "weave", "brooks", "brothers", "double", "knit", "ua", "mens", "s", "tech", "2",
}


def _name_words(name: str) -> set[str]:
    return {w for w in re.findall(r"[a-z0-9]+", name.lower()) if w not in GENERIC_NAME_WORDS and len(w) > 1}


@lru_cache(maxsize=1)
def _common_tags() -> frozenset[str]:
    """Tags on more than a fifth of products ("yale", "college apparel"…) don't signal similarity."""
    with connect() as conn:
        rows = conn.execute("SELECT search_tags FROM catalogue").fetchall()
    counts = Counter(t.lower() for (tags,) in rows for t in set(json.loads(tags)))
    return frozenset(t for t, n in counts.items() if n > len(rows) / 5)


def related_products(product_id: str, limit: int = 6, size: str | None = None) -> list[ProductSummary]:
    """Products similar to this one, best first, preferring items in stock (in `size`, if given).

    Similarity, strongest first: a shared distinctive name word (college, team, family
    member, school: "Saybrook", "Grandpa", "Hockey"), the same collection, the same
    garment shelf, shared uncommon tags, the same main colour.
    """
    size = size.upper() if size else None
    common = _common_tags()
    with connect() as conn:
        rows = conn.execute("SELECT * FROM catalogue").fetchall()
        stock = _stock_for(conn, [r["product_id"] for r in rows])
    by_id = {r["product_id"]: r for r in rows}
    base = by_id.get(product_id)
    if base is None:
        return []

    base_words = _name_words(base["name"])
    base_cols = {k for k in COLLECTIONS if in_collection(base["name"], k)}
    base_cat = category_for(base["garment_type"])
    base_tags = {t.lower() for t in json.loads(base["search_tags"])} - common
    base_color = (json.loads(base["colors"]) or [""])[0].lower()

    scored: list[tuple[float, str, ProductSummary]] = []
    for pid, row in by_id.items():
        if pid == product_id:
            continue
        score = 5.0 * len(base_words & _name_words(row["name"]))
        score += 3.0 * len(base_cols & {k for k in COLLECTIONS if in_collection(row["name"], k)})
        score += 2.0 if category_for(row["garment_type"]) == base_cat else 0.0
        score += 0.5 * min(4, len(base_tags & ({t.lower() for t in json.loads(row["search_tags"])} - common)))
        score += 0.5 if (json.loads(row["colors"]) or [""])[0].lower() == base_color else 0.0
        s = stock[pid]
        if sum(s.values()) == 0:
            score -= 6.0  # never lead with something nobody can buy
        elif size and s.get(size, 0) == 0:
            score -= 3.0  # sold out in the shopper's size
        if score > 0:
            scored.append((score, row["name"], _summary(row, s)))

    scored.sort(key=lambda t: (-t[0], t[1]))
    return [p for _, _, p in scored[:limit]]

# =========================================================================== #
# 3. Saved chats (chat_messages)
# =========================================================================== #
#
# chat_messages(id, user_id, role, content, products_json, created_at): one row
# per message, the shopper's and Handsome Dan's reply (with the cards it showed).
# Guests are never saved. Every query is filtered by user_id.

def save_chat_turn(user_id: int, message: str, reply: str, cards: list[dict]) -> None:
    """Save one exchange. `cards` are {product_id, name} for the products shown."""
    with connect() as conn:
        conn.execute(
            "INSERT INTO chat_messages (user_id, role, content, products_json) VALUES (?, 'user', ?, NULL)",
            (user_id, message),
        )
        conn.execute(
            "INSERT INTO chat_messages (user_id, role, content, products_json) VALUES (?, 'assistant', ?, ?)",
            (user_id, reply, json.dumps(cards) if cards else None),
        )


def recent_chat_messages(user_id: int, limit: int, before_id: int | None = None) -> list[dict]:
    """The shopper's most recent messages, oldest first."""
    sql = "SELECT id, role, content, products_json, created_at FROM chat_messages WHERE user_id = ?"
    params: list = [user_id]
    if before_id is not None:
        sql += " AND id < ?"
        params.append(before_id)
    sql += " ORDER BY id DESC LIMIT ?"
    params.append(limit)
    with connect() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [dict(r) for r in reversed(rows)]


def count_chat_messages(user_id: int) -> int:
    with connect() as conn:
        return conn.execute("SELECT COUNT(*) FROM chat_messages WHERE user_id = ?", (user_id,)).fetchone()[0]


def chat_cards(products_json: str | None) -> list[dict]:
    """[{product_id, name}] from a row. Older rows hold full product dicts."""
    if not products_json:
        return []
    try:
        items = json.loads(products_json)
    except (json.JSONDecodeError, TypeError):
        return []
    return [
        {"product_id": p["product_id"], "name": p.get("name", "")}
        for p in items
        if isinstance(p, dict) and "product_id" in p
    ]

# =========================================================================== #
# 4. Sizes
# =========================================================================== #
#
# shopper_sizes(user_id, size, updated_at): the size a signed-in shopper says is theirs.
# size_history(id, user_id, product_id, size, source, created_at): sizes chosen before;
#   source is 'purchased' (weight 4; no checkout records these yet), 'selected'
#   (picked on a product page, weight 1) or 'asked' (asked Dan about it, weight 1).
# Guests' "My size" stays in their browser and is passed in as a hint.
# A saved size counts 10; history events add their weight (last 50). The highest
# total is the usual size; if it's sold out in this item, the nearest size in
# stock is recommended (one size up first).

SOURCE_WEIGHTS = {"purchased": 4.0, "selected": 1.0, "asked": 1.0}
SAVED_SIZE_WEIGHT = 10.0
HISTORY_WINDOW = 50

SIZE_SCHEMA = """
CREATE TABLE IF NOT EXISTS shopper_sizes (
    user_id    INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    size       TEXT NOT NULL CHECK (size IN ('XS','S','M','L','XL','XXL')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS size_history (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    product_id TEXT NOT NULL REFERENCES catalogue(product_id),
    size       TEXT NOT NULL CHECK (size IN ('XS','S','M','L','XL','XXL')),
    source     TEXT NOT NULL CHECK (source IN ('purchased','selected','asked')),
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS size_history_user ON size_history(user_id, id);
"""


def init_size_tables() -> None:
    with connect() as conn:
        conn.executescript(SIZE_SCHEMA)


def normalize_size(size: str | None) -> str | None:
    size = (size or "").strip().upper()
    return size if size in SIZES else None


# --------------------------------------------------------------------------- #
# "My size"
# --------------------------------------------------------------------------- #


def saved_size(user_id: int) -> str | None:
    with connect() as conn:
        row = conn.execute("SELECT size FROM shopper_sizes WHERE user_id = ?", (user_id,)).fetchone()
    return row["size"] if row else None


def save_size(user_id: int, size: str) -> None:
    with connect() as conn:
        conn.execute(
            """INSERT INTO shopper_sizes (user_id, size) VALUES (?, ?)
               ON CONFLICT(user_id) DO UPDATE SET size = excluded.size, updated_at = datetime('now')""",
            (user_id, size),
        )


def clear_size(user_id: int) -> None:
    with connect() as conn:
        conn.execute("DELETE FROM shopper_sizes WHERE user_id = ?", (user_id,))


# --------------------------------------------------------------------------- #
# Size history
# --------------------------------------------------------------------------- #


def record_size_event(user_id: int, product_id: str, size: str, source: str) -> bool:
    """Add one size event. The same product+size+source within a day counts once,
    so clicking back and forth between sizes doesn't skew the history."""
    with connect() as conn:
        exists = conn.execute("SELECT 1 FROM catalogue WHERE product_id = ?", (product_id,)).fetchone()
        if not exists:
            return False
        dup = conn.execute(
            """SELECT 1 FROM size_history WHERE user_id = ? AND product_id = ? AND size = ? AND source = ?
               AND created_at > datetime('now', '-1 day')""",
            (user_id, product_id, size, source),
        ).fetchone()
        if dup:
            return False
        conn.execute(
            "INSERT INTO size_history (user_id, product_id, size, source) VALUES (?, ?, ?, ?)",
            (user_id, product_id, size, source),
        )
        return True


def size_history_counts(user_id: int) -> dict[str, Counter]:
    """{source: Counter(size → events)} over the most recent events."""
    with connect() as conn:
        rows = conn.execute(
            "SELECT size, source FROM size_history WHERE user_id = ? ORDER BY id DESC LIMIT ?",
            (user_id, HISTORY_WINDOW),
        ).fetchall()
    out: dict[str, Counter] = {s: Counter() for s in SOURCE_WEIGHTS}
    for r in rows:
        out[r["source"]][r["size"]] += 1
    return out


# --------------------------------------------------------------------------- #
# Recommendation
# --------------------------------------------------------------------------- #


def usual_size(user_id: int | None, browser_size: str | None) -> tuple[str | None, str, str]:
    """(size, basis, why) — the shopper's usual size before looking at stock."""
    browser_size = normalize_size(browser_size)
    if user_id is None:
        if browser_size:
            return browser_size, "my_size", f"{browser_size} is the size you told us you wear"
        return None, "none", "We don't know your size yet"

    saved = saved_size(user_id)
    counts = size_history_counts(user_id)
    scores: Counter = Counter()
    if saved:
        scores[saved] += SAVED_SIZE_WEIGHT
    for source, sizes in counts.items():
        for size, n in sizes.items():
            scores[size] += SOURCE_WEIGHTS[source] * n
    if not scores:
        if browser_size:
            return browser_size, "my_size", f"{browser_size} is the size you told us you wear"
        return None, "none", "We don't know your size yet"

    best = max(SIZES, key=lambda s: (scores[s], -abs(SIZES.index(s) - 2)))
    bought, chosen = counts["purchased"][best], counts["selected"][best] + counts["asked"][best]
    if saved == best:
        why = f"{best} is your saved size"
        if bought:
            why += f", and you've bought {bought} item{'s' if bought > 1 else ''} in {best}"
        return best, "my_size", why
    parts = []
    if bought:
        parts.append(f"you've bought {bought} item{'s' if bought > 1 else ''} in {best}")
    if chosen:
        parts.append(f"you've picked {best} {chosen} time{'s' if chosen > 1 else ''} before")
    why = " and ".join(parts) or f"{best} comes up most in your size history"
    return best, "history", why[0].upper() + why[1:]


def recommend_size_for(product_id: str, stock_by_size: dict[str, int], user_id: int | None, browser_size: str | None) -> SizeRecommendation:
    usual, basis, why = usual_size(user_id, browser_size)
    if usual is None:
        return SizeRecommendation(
            product_id=product_id, recommended_size=None, usual_size=None, basis="none",
            reason="Tell us the size you usually wear and we'll recommend one for every item.",
            in_stock=False, quantity=None, exact_match=False,
        )

    qty = stock_by_size.get(usual, 0)
    if qty > 0:
        return SizeRecommendation(
            product_id=product_id, recommended_size=usual, usual_size=usual, basis=basis,
            reason=f"{why}. {qty} in stock.", in_stock=True, quantity=qty, exact_match=True,
        )

    # Their size is sold out: nearest size in stock, one size up first.
    i = SIZES.index(usual)
    for step in (1, -1, 2, -2, 3, -3, 4, -4, 5, -5):
        j = i + step
        if 0 <= j < len(SIZES) and stock_by_size.get(SIZES[j], 0) > 0:
            alt = SIZES[j]
            direction = "up" if step > 0 else "down"
            return SizeRecommendation(
                product_id=product_id, recommended_size=alt, usual_size=usual, basis=basis,
                reason=(
                    f"{why}, but this item is sold out in {usual}. {alt} is the closest size in stock "
                    f"(one size {direction}{'' if abs(step) == 1 else ' or more'}; {stock_by_size[alt]} left)."
                ),
                in_stock=True, quantity=stock_by_size[alt], exact_match=False,
            )
    return SizeRecommendation(
        product_id=product_id, recommended_size=None, usual_size=usual, basis=basis,
        reason=f"{why}, but this item is sold out in every size.", in_stock=False, quantity=0, exact_match=False,
    )

# =========================================================================== #
# 5. Agent tools
# =========================================================================== #

Category = Literal["t-shirt", "long-sleeve", "crewneck", "hoodie", "quarter-zip", "jacket"]
CollectionKey = Literal["family", "sports", "colleges", "schools"]
Size = Literal["XS", "S", "M", "L", "XL", "XXL"]
ToolSort = Literal["relevance", "price_asc", "price_desc"]

MAX_RESULTS = 25
SHOWCASE_MAX = 24  # cards a search can put on the page


@dataclass
class RecordedSearch:
    """A search this turn: its arguments and every matching ID (for the page)."""

    args: dict[str, Any]
    total_matches: int
    product_ids: list[str]


@dataclass
class ViewedPage:
    """Where the shopper is, resolved from the widget's PageContext (agent.resolve_page)."""

    path: str
    area: str  # home, products, product, about, login, create-account, other
    product_id: str | None = None  # checked against the database
    product_name: str | None = None
    selected_size: str | None = None
    filters: dict[str, str] = field(default_factory=dict)  # known Products-page filters only


@dataclass
class ShopDeps:
    """Per-turn state: who is chatting, where they are, and what tools returned.

    `user` and `page` are set by agent.chat() before the run. Tools record what
    they returned; the output validator reads it.
    """

    user: User | None
    user_message: str
    page: ViewedPage | None = None
    my_size: str | None = None  # a guest's "My size" from their browser
    seen_ids: set[str] = field(default_factory=set)
    seen_prices: set[float] = field(default_factory=set)
    seen_quantities: set[int] = field(default_factory=set)
    # (product name, size) for every size check_stock found sold out this turn.
    sold_out_checks: list[tuple[str, str]] = field(default_factory=list)
    # search_id → the search, so the reply can ask for its matches to be shown.
    searches: dict[str, RecordedSearch] = field(default_factory=dict)
    tools_used: list[str] = field(default_factory=list)

    def note(self, tool: str, product_id: str, price: float, quantities: list[int]) -> None:
        if tool not in self.tools_used:
            self.tools_used.append(tool)
        self.seen_ids.add(product_id)
        self.seen_prices.add(price)
        self.seen_quantities.update(quantities)


def _not_found(product_id: str) -> ModelRetry:
    return ModelRetry(f"No product has ID {product_id!r}. Use an ID returned by search_")


def search_catalog(
    ctx: RunContext[ShopDeps],
    query: str = "",
    category: Category | None = None,
    collection: CollectionKey | None = None,
    color: str | None = None,
    size: Size | None = None,
    max_price: float | None = None,
    min_price: float | None = None,
    in_stock_only: bool = False,
    sold_out_in: Size | None = None,
    sort: ToolSort = "relevance",
    limit: int = 8,
) -> SearchResults:
    """Find products. Returns each match's price, total stock, and which sizes are in stock or sold out.

    Use this first to turn what the shopper said ("the Saybrook tee", "a navy hoodie")
    into product IDs. For exact per-size quantities, follow up with check_stock.
    `total_matches` says how many products match in the whole database; if `complete`
    is false, the list was cut at `limit`, so raise the limit or narrow the filters
    before presenting it as a full list.

    Args:
        query: Descriptive words such as "hockey", "mom", "Saybrook", "bulldog", "crest".
            Leave empty to browse by filters only.
        category: Garment shelf, if the shopper named one. "crewneck" also holds other
            pullover sweatshirts (e.g. a mockneck) and "jacket" includes full-zips, so check
            garment_type before calling an item a crewneck or a jacket.
        collection: "family" (Mom, Dad, Grandpa…), "sports" (team gear), "colleges"
            (residential colleges) or "schools" (graduate and professional schools).
        color: A colour word such as "navy", "gray", "white", "cream".
        size: Only items with at least one unit in this size.
        max_price: Highest price in US dollars, inclusive.
        min_price: Lowest price in US dollars, inclusive.
        in_stock_only: Only items with stock in some size.
        sold_out_in: Only items that are sold out (0 on hand) in this size.
        sort: "relevance" (default), "price_asc" or "price_desc".
        limit: Maximum results, 1–25.
    """
    everything = search_products(
        query=query,
        category=category,
        collection=collection,
        color=color,
        size=size,
        min_price=min_price,
        max_price=max_price,
        in_stock_only=in_stock_only,
        sold_out_in=sold_out_in,
        sort=sort,
    )
    matches = [to_match(p) for p in everything[: max(1, min(limit, MAX_RESULTS))]]
    if not matches:
        ctx.deps.tools_used.append("search_catalog")
    for m in matches:
        ctx.deps.note("search_catalog", m.product_id, m.price, [m.total_stock])

    search_id = f"s{len(ctx.deps.searches) + 1}"
    ctx.deps.searches[search_id] = RecordedSearch(
        args={
            "query": query, "category": category, "collection": collection, "color": color, "size": size,
            "max_price": max_price, "min_price": min_price, "in_stock_only": in_stock_only,
            "sold_out_in": sold_out_in, "sort": sort,
        },
        total_matches=len(everything),
        product_ids=[p.product_id for p in everything[:SHOWCASE_MAX]],
    )
    return SearchResults(
        search_id=search_id,
        total_matches=len(everything),
        returned=len(matches),
        complete=len(matches) == len(everything),
        products=matches,
    )


def get_product_details(ctx: RunContext[ShopDeps], product_id: str) -> ProductFacts:
    """Full facts for one product: description, colours, price, and quantity on hand for every size.

    Use when the shopper asks what an item is like, what it's made of or looks like, or
    wants its price together with all its sizes.

    Args:
        product_id: An ID returned by search_
    """
    facts = product_facts(product_id)
    if facts is None:
        raise _not_found(product_id)
    ctx.deps.note(
        "get_product_details", facts.product_id, facts.price, [facts.total_stock, *(s.quantity for s in facts.stock_by_size)]
    )
    return facts


def check_stock(ctx: RunContext[ShopDeps], product_id: str, size: Size | None = None) -> StockCheck:
    """How many of one product are in stock, overall or in one size. Use for every stock question.

    Returns the exact quantity on hand, whether it's in stock, which sizes are sold out, and
    an `answer` sentence stating the facts. If the requested size is sold out, `in_stock` is
    false and `answer` says SOLD OUT: tell the shopper clearly and offer the sizes that are left.

    Args:
        product_id: An ID returned by search_
        size: The size the shopper asked about (XS, S, M, L, XL, XXL). Leave empty for all sizes.
    """
    result = stock_check(product_id, size)
    if result is None:
        raise _not_found(product_id)
    quantities = [result.total_stock, *(a.quantity for a in result.available_sizes)]
    if result.quantity is not None:
        quantities.append(result.quantity)
    ctx.deps.note("check_stock", result.product_id, result.price, quantities)
    if result.size_requested and not result.in_stock:
        ctx.deps.sold_out_checks.append((result.name, result.size_requested))
    if result.size_requested and ctx.deps.user:
        # Asking about a size is a (weak) signal of the shopper's size.
        record_size_event(ctx.deps.user.id, result.product_id, result.size_requested, "asked")
    return result


def recommend_size(ctx: RunContext[ShopDeps], product_id: str) -> SizeRecommendation:
    """Which size to suggest for one product, based on the shopper's saved size and size history,
    adjusted for this item's stock.

    Use when the shopper asks "what size should I get?", "will it come in my size?" or anything
    about their size. If `basis` is "none", ask what size they usually wear (and mention they can
    set "My size" on any product page). If `exact_match` is false, their usual size is sold out:
    say so clearly, then offer `recommended_size`.

    Args:
        product_id: An ID returned by search_catalog, or the product on screen.
    """
    product = get_product(product_id)
    if product is None:
        raise _not_found(product_id)
    user = ctx.deps.user
    rec = recommend_size_for(
        product.product_id,
        {s.size: s.quantity for s in product.stock_by_size},
        user.id if user else None,
        ctx.deps.my_size,
    )
    ctx.deps.note("recommend_size", product.product_id, product.price, [q for q in [rec.quantity] if q is not None])
    if rec.usual_size and not rec.exact_match:
        ctx.deps.sold_out_checks.append((product.name, rec.usual_size))
    return rec


def get_viewed_product(ctx: RunContext[ShopDeps]) -> ProductFacts | str:
    """The product the shopper is looking at right now on its product page.

    Call this when the shopper says "this", "it", "this one", "this hoodie" etc. on a
    product page. Returns its description, colours, price and stock for every size.
    """
    page = ctx.deps.page
    if page is None or page.product_id is None:
        ctx.deps.tools_used.append("get_viewed_product")
        return "The shopper is not on a product page right now. Ask which item they mean, or search for it."
    facts = product_facts(page.product_id)
    if facts is None:
        return "The product on screen could not be found in the database."
    ctx.deps.note(
        "get_viewed_product", facts.product_id, facts.price, [facts.total_stock, *(s.quantity for s in facts.stock_by_size)]
    )
    return facts


def get_shopper_profile(ctx: RunContext[ShopDeps]) -> ShopperProfile:
    """Who you are chatting with: signed in or guest; if signed in, their name, email and join date.

    Use when the shopper asks which account they're signed in as, or anything about
    their own account details. Never reveals anyone else's details.
    """
    ctx.deps.tools_used.append("get_shopper_profile")
    user = ctx.deps.user
    if user is None:
        return ShopperProfile(signed_in=False)
    with connect() as conn:
        row = conn.execute("SELECT created_at FROM users WHERE id = ?", (user.id,)).fetchone()
    return ShopperProfile(
        signed_in=True,
        first_name=user.first_name,
        last_name=user.last_name,
        email=user.email,
        member_since=(row["created_at"] or "")[:10] if row else None,
        saved_messages=count_chat_messages(user.id),
    )


def recall_previous_chats(ctx: RunContext[ShopDeps], limit: int = 10) -> list[PastChatMessage] | str:
    """The signed-in shopper's own earlier chat messages (most recent last), from the database.

    Use when they refer to an earlier conversation ("what did you recommend last time?",
    "that hoodie we talked about yesterday"). Product prices and stock in old messages may
    be out of date: look them up again before quoting them.

    Args:
        limit: How many recent messages to return, 1–30.
    """
    ctx.deps.tools_used.append("recall_previous_chats")
    if ctx.deps.user is None:
        return "The shopper is a guest, so there is no saved chat history. Guests' chats aren't stored."
    rows = recent_chat_messages(ctx.deps.user.id, max(1, min(limit, 30)))
    if not rows:
        return "No earlier chats are saved for this shopper."
    return [
        PastChatMessage(
            role=r["role"],
            content=r["content"],
            products_shown=[c["name"] for c in chat_cards(r["products_json"])],
            created_at=r["created_at"],
        )
        for r in rows
    ]


def store_overview(ctx: RunContext[ShopDeps]) -> StoreFacets:
    """Categories and collections (with item counts) and the shop's price range."""
    ctx.deps.tools_used.append("store_overview")
    facets = store_facets()
    ctx.deps.seen_prices.update({facets.min_price, facets.max_price})
    return facets


SHOP_TOOLS = [
    search_catalog,
    get_product_details,
    check_stock,
    recommend_size,
    get_viewed_product,
    store_overview,
    get_shopper_profile,
    recall_previous_chats,
]
