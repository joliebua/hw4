"""Campus Customs API — the FastAPI app the website talks to.

Run from this folder (backend/), with .venv active:

    uvicorn main:app --reload --port 8000

The Vite dev server (http://127.0.0.1:5173) proxies every /api request here.

Routes
  /api/health                 status, model name, whether the API key is set
  /api/products, /{id}        catalogue + stock (tools.py)
  /api/facets                 categories, collections, price range
  /api/images/{file}          product photos
  /api/auth/...               create account, log in, log out, me (accounts section below)
  /api/chat                   one message in → Handsome Dan's reply + product cards (agent.py)
  /api/chat/history           a signed-in shopper's saved chat
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import os
import re
import secrets
import sqlite3
import time
from collections import defaultdict, deque
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from fastapi import APIRouter, Cookie, Depends, FastAPI, HTTPException, Query, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator

import agent
import tools
from tools import IMAGES_DIR, connect
from models import (
    ChatHistory,
    ChatRequest,
    ChatResponse,
    MySize,
    ProductDetail,
    ProductSummary,
    SizeEvent,
    SizeRecommendation,
    StoreFacets,
    User,
)

log = logging.getLogger("campus_customs")


# =========================================================================== #
# Accounts: create account, log in, log out, "who am I"
#
# Passwords: Argon2id (64 MiB, 3 passes, random salt); legacy PBKDF2 hashes from
# the provided database still work and are upgraded on first login. Wrong
# email / wrong password look identical; failures are throttled. Sessions: a
# random 256-bit token in an HttpOnly, SameSite=Lax cookie; only its SHA-256 is
# stored. Nothing here ever returns a password hash.
# =========================================================================== #

router = APIRouter(prefix="/api/auth", tags=["accounts"])

SESSION_COOKIE = "cc_session"
SESSION_DAYS = 7
# Browsers only send Secure cookies over HTTPS; local dev runs on plain HTTP.
COOKIE_SECURE = os.getenv("COOKIE_SECURE", "false").lower() == "true"

MIN_PASSWORD = 8
MAX_PASSWORD = 128

# Argon2id with the RFC 9106 "low memory" profile: 64 MiB, 3 iterations, 4 lanes.
hasher = PasswordHasher(time_cost=3, memory_cost=64 * 1024, parallelism=4)

# Hashed once at startup and verified against when an email isn't found, so a
# missing account takes as long to reject as a wrong password.
_DUMMY_HASH = hasher.hash(secrets.token_urlsafe(16))

# Legacy hashes in the provided database are PBKDF2-HMAC-SHA256 with 120,000
# iterations and the salt stored as text. The format string doesn't record the
# count, so it's fixed here (confirmed against the provided test account).
LEGACY_PBKDF2_ITERATIONS = 120_000

# A few of the most common passwords, refused outright at sign-up.
COMMON_PASSWORDS = {
    "password", "password1", "password123", "12345678", "123456789", "1234567890",
    "qwerty123", "qwertyuiop", "iloveyou", "11111111", "abc12345", "letmein1",
    "welcome1", "football", "baseball", "sunshine", "princess", "admin123",
    "yale1701", "bulldogs", "boolaboola", "harvardsucks",
}

SESSIONS_SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions (
    token_hash TEXT PRIMARY KEY,
    user_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    expires_at TEXT NOT NULL
)
"""


def init_auth_tables() -> None:
    with connect() as conn:
        conn.execute(SESSIONS_SCHEMA)
        conn.execute("DELETE FROM sessions WHERE expires_at < ?", (_now().isoformat(),))


# --------------------------------------------------------------------------- #
# Models
# --------------------------------------------------------------------------- #


def _clean_name(value: str) -> str:
    value = re.sub(r"\s+", " ", value).strip()
    if not value:
        raise ValueError("can't be blank")
    return value


class RegisterRequest(BaseModel):
    first_name: str = Field(min_length=1, max_length=50)
    last_name: str = Field(min_length=1, max_length=50)
    email: EmailStr
    password: str = Field(min_length=MIN_PASSWORD, max_length=MAX_PASSWORD)
    confirm_password: str = Field(max_length=MAX_PASSWORD)

    _names = field_validator("first_name", "last_name")(_clean_name)

    @model_validator(mode="after")
    def check_password(self) -> "RegisterRequest":
        if self.password != self.confirm_password:
            raise ValueError("Passwords don't match.")
        if not self.password.strip():
            raise ValueError("Password can't be only spaces.")
        if self.password.lower() in COMMON_PASSWORDS:
            raise ValueError("That password is too common. Please choose another.")
        if self.password.lower() == str(self.email).lower():
            raise ValueError("Your password can't be your email address.")
        return self


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=MAX_PASSWORD)


# --------------------------------------------------------------------------- #
# Password hashing
# --------------------------------------------------------------------------- #


def hash_password(password: str) -> str:
    return hasher.hash(password)


def _verify_legacy_pbkdf2(password: str, stored: str) -> bool:
    try:
        algorithm, salt, digest_hex = stored.split("$")
    except ValueError:
        return False
    if algorithm != "pbkdf2_sha256":
        return False
    candidate = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), LEGACY_PBKDF2_ITERATIONS).hex()
    return hmac.compare_digest(candidate, digest_hex)


def verify_password(password: str, stored: str) -> tuple[bool, bool]:
    """Returns (matches, needs_rehash)."""
    if stored.startswith("$argon2"):
        try:
            hasher.verify(stored, password)
        except (VerificationError, InvalidHashError):
            return False, False
        return True, hasher.check_needs_rehash(stored)
    # Legacy format: verify, then always upgrade to Argon2id.
    return _verify_legacy_pbkdf2(password, stored), True


# --------------------------------------------------------------------------- #
# Login throttling (in memory; resets when the server restarts)
# --------------------------------------------------------------------------- #

MAX_FAILURES = 5
FAILURE_WINDOW_SECONDS = 15 * 60
_failures: dict[str, deque[float]] = defaultdict(deque)


def _recent_failures(key: str) -> deque[float]:
    q = _failures[key]
    cutoff = time.monotonic() - FAILURE_WINDOW_SECONDS
    while q and q[0] < cutoff:
        q.popleft()
    return q


def _check_throttle(*keys: str) -> None:
    if any(len(_recent_failures(k)) >= MAX_FAILURES for k in keys):
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            "Too many failed attempts. Please wait 15 minutes and try again.",
        )


def _record_failure(*keys: str) -> None:
    now = time.monotonic()
    for k in keys:
        _recent_failures(k).append(now)


def _clear_failures(*keys: str) -> None:
    for k in keys:
        _failures.pop(k, None)


# --------------------------------------------------------------------------- #
# Sessions
# --------------------------------------------------------------------------- #


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _to_user(row: sqlite3.Row) -> User:
    first = row["first_name"] or (row["name"].split(" ", 1)[0] if row["name"] else "")
    last = row["last_name"] or (row["name"].split(" ", 1)[1] if " " in (row["name"] or "") else "")
    return User(id=row["id"], first_name=first, last_name=last, name=row["name"], email=row["email"])


def _start_session(conn: sqlite3.Connection, response: Response, user_id: int) -> None:
    token = secrets.token_urlsafe(32)
    expires = _now() + timedelta(days=SESSION_DAYS)
    conn.execute(
        "INSERT INTO sessions (token_hash, user_id, expires_at) VALUES (?, ?, ?)",
        (_token_hash(token), user_id, expires.isoformat()),
    )
    response.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=SESSION_DAYS * 24 * 3600,
        httponly=True,
        samesite="lax",
        secure=COOKIE_SECURE,
        path="/",
    )


def current_user(cc_session: str | None = Cookie(default=None)) -> User | None:
    if not cc_session:
        return None
    with connect() as conn:
        row = conn.execute(
            """SELECT u.*, s.expires_at FROM sessions s JOIN users u ON u.id = s.user_id
               WHERE s.token_hash = ?""",
            (_token_hash(cc_session),),
        ).fetchone()
        if row is None:
            return None
        if datetime.fromisoformat(row["expires_at"]) < _now():
            conn.execute("DELETE FROM sessions WHERE token_hash = ?", (_token_hash(cc_session),))
            return None
        return _to_user(row)


def require_user(user: User | None = Depends(current_user)) -> User:
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Please log in.")
    return user


# --------------------------------------------------------------------------- #
# Routes
# --------------------------------------------------------------------------- #


@router.post("/register", response_model=User, status_code=status.HTTP_201_CREATED)
def register(body: RegisterRequest, response: Response):
    email = str(body.email).strip().lower()
    password_hash = hash_password(body.password)
    with connect() as conn:
        # The column's UNIQUE constraint is case-sensitive; emails are not.
        if conn.execute("SELECT 1 FROM users WHERE LOWER(email) = ?", (email,)).fetchone():
            raise HTTPException(status.HTTP_409_CONFLICT, "An account with that email already exists. Try logging in.")
        try:
            cur = conn.execute(
                """INSERT INTO users (name, first_name, last_name, email, password_hash)
                   VALUES (?, ?, ?, ?, ?)""",
                (f"{body.first_name} {body.last_name}", body.first_name, body.last_name, email, password_hash),
            )
        except sqlite3.IntegrityError:
            raise HTTPException(status.HTTP_409_CONFLICT, "An account with that email already exists. Try logging in.")
        _start_session(conn, response, cur.lastrowid)
        row = conn.execute("SELECT * FROM users WHERE id = ?", (cur.lastrowid,)).fetchone()
        return _to_user(row)


@router.post("/login", response_model=User)
def login(body: LoginRequest, request: Request, response: Response):
    email = str(body.email).strip().lower()
    ip = request.client.host if request.client else "unknown"
    keys = (f"email:{email}", f"ip:{ip}")
    _check_throttle(*keys)

    with connect() as conn:
        row = conn.execute("SELECT * FROM users WHERE LOWER(email) = ?", (email,)).fetchone()
        if row is None:
            _burn_time(body.password)
            ok, needs_rehash = False, False
        else:
            ok, needs_rehash = verify_password(body.password, row["password_hash"])

        if not ok:
            _record_failure(*keys)
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Email or password is incorrect.")

        _clear_failures(*keys)
        if needs_rehash:
            conn.execute(
                "UPDATE users SET password_hash = ? WHERE id = ?", (hash_password(body.password), row["id"])
            )
        _start_session(conn, response, row["id"])
        return _to_user(row)


def _burn_time(password: str) -> None:
    """Spend the same effort as a real check when the email doesn't exist."""
    try:
        hasher.verify(_DUMMY_HASH, password)
    except VerificationError:
        pass


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(response: Response, cc_session: str | None = Cookie(default=None)):
    if cc_session:
        with connect() as conn:
            conn.execute("DELETE FROM sessions WHERE token_hash = ?", (_token_hash(cc_session),))
    response.delete_cookie(SESSION_COOKIE, path="/")


@router.get("/me", response_model=User | None)
def me(user: User | None = Depends(current_user)):
    """The logged-in shopper, or null for guests (not an error: most visitors are guests)."""
    return user


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_auth_tables()
    tools.init_size_tables()
    yield


app = FastAPI(title="Campus Customs", version="0.3.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:5173", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Content-Type"],
)
app.mount("/api/images", StaticFiles(directory=IMAGES_DIR), name="images")
app.include_router(router)


@app.get("/api/health")
def health():
    with connect() as conn:
        count = conn.execute("SELECT COUNT(*) FROM catalogue").fetchone()[0]
    try:
        agent.portkey_api_key()
        key_set = True
    except agent.AgentUnavailable:
        key_set = False
    return {
        "ok": True,
        "database": tools.DB_FILE.name,
        "products": count,
        "assistant": "Handsome Dan",
        "model": agent.MODEL_NAME,
        "portkey_key_set": key_set,
    }


# --------------------------------------------------------------------------- #
# Products
# --------------------------------------------------------------------------- #


@app.get("/api/products", response_model=list[ProductSummary])
def list_products(
    q: str = "",
    category: str | None = None,
    collection: str | None = None,
    size: str | None = None,
    max_price: float | None = Query(None, ge=0),
    in_stock: bool = False,
    sort: tools.Sort = "relevance",
):
    """All products, optionally filtered. With `q`, results are ranked by relevance."""
    if collection and collection not in tools.COLLECTIONS:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Unknown collection {collection!r}.")
    return tools.search_products(
        query=q,
        category=category or None,
        collection=collection or None,
        size=size or None,
        max_price=max_price,
        in_stock_only=in_stock,
        sort=sort,
    )


@app.get("/api/products/{product_id}", response_model=ProductDetail)
def get_product(product_id: str):
    product = tools.get_product(product_id)
    if product is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Product not found.")
    return product


@app.get("/api/facets", response_model=StoreFacets)
def facets():
    return tools.store_facets()


@app.get("/api/products/{product_id}/related", response_model=list[ProductSummary])
def related_products(product_id: str, limit: int = Query(6, ge=1, le=12), size: str | None = None):
    """"You might also like": similar products, preferring ones in stock (in `size`)."""
    if tools.get_product(product_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Product not found.")
    return tools.related_products(product_id, limit, tools.normalize_size(size))


# --------------------------------------------------------------------------- #
# Sizes: "My size", size history, recommendations
# --------------------------------------------------------------------------- #


@app.get("/api/products/{product_id}/size-recommendation", response_model=SizeRecommendation)
def size_recommendation(
    product_id: str, my_size: str | None = None, user: User | None = Depends(current_user)
):
    """Recommended size for this item. Signed-in: saved size + size history.
    Guests: `my_size` from their browser."""
    product = tools.get_product(product_id)
    if product is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Product not found.")
    stock = {s.size: s.quantity for s in product.stock_by_size}
    return tools.recommend_size_for(product_id, stock, user.id if user else None, my_size)


@app.get("/api/me/size", response_model=MySize)
def get_my_size(user: User = Depends(require_user)):
    return MySize(size=tools.saved_size(user.id))


@app.put("/api/me/size", response_model=MySize)
def put_my_size(body: MySize, user: User = Depends(require_user)):
    if body.size is None:
        tools.clear_size(user.id)
    else:
        tools.save_size(user.id, body.size)
    return body


@app.post("/api/me/size-history", status_code=status.HTTP_204_NO_CONTENT)
def add_size_event(body: SizeEvent, user: User = Depends(require_user)):
    """A signed-in shopper picked a size on a product page."""
    tools.record_size_event(user.id, body.product_id, body.size, "selected")


# --------------------------------------------------------------------------- #
# Chat
# --------------------------------------------------------------------------- #

# Each chat turn costs a few model calls, so cap how fast one visitor can send.
CHAT_LIMIT = 20
CHAT_WINDOW_SECONDS = 60
_chat_calls: dict[str, deque[float]] = defaultdict(deque)


def chat_rate_limit(request: Request) -> None:
    key = request.client.host if request.client else "unknown"
    now = time.monotonic()
    calls = _chat_calls[key]
    while calls and calls[0] < now - CHAT_WINDOW_SECONDS:
        calls.popleft()
    if len(calls) >= CHAT_LIMIT:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS, "You're sending messages quickly — give Handsome Dan a moment and try again."
        )
    calls.append(now)


@app.post("/api/chat", response_model=ChatResponse, dependencies=[Depends(chat_rate_limit)])
async def chat(body: ChatRequest, user: User | None = Depends(current_user)):
    """One message from the chat widget → Handsome Dan's reply and product cards."""
    try:
        return await agent.chat(body.message.strip(), body.conversation_id, user, body.page)
    except agent.AgentUnavailable as e:
        log.error("Chat unavailable: %s", e)
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Handsome Dan is offline right now. Please try again later.")
    except Exception:
        log.exception("Chat turn failed")
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY, "Handsome Dan couldn't answer just now. Please try again in a moment."
        )


@app.get("/api/chat/history", response_model=ChatHistory)
def chat_history(user: User | None = Depends(current_user)):
    """The signed-in shopper's recent chat (empty for guests)."""
    return agent.load_history(user)


@app.delete("/api/chat/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
def forget_chat(conversation_id: str, user: User | None = Depends(current_user)):
    """Start over: the agent forgets this conversation. Saved history is kept."""
    agent.forget(conversation_id, user)
