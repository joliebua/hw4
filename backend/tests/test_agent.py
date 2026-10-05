"""Offline checks for the agent's guard rails — no model calls, no database writes.

The output validator is what stops Golden from quoting a made-up price or
showing a product no tool returned. These tests drive it directly with a
stand-in run context, plus the card-number redaction and conversation
ownership rules.

Run from backend/ with .venv active:

    python tests/test_agent.py
"""

from __future__ import annotations

import sys
from pathlib import Path

# Run from backend/:  python tests/<this file>.py   (the app modules live one folder up)
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from types import SimpleNamespace

from pydantic_ai import ModelRetry

import agent
import tools
from models import PageContext, ShopReply, User
from tools import ShopDeps

HOODIE = tools.get_product("yale-mom-hoodie")
assert HOODIE is not None


def run(deps: ShopDeps, message: str, ids: list[str] | None = None) -> ShopReply:
    return agent.grounded_reply(SimpleNamespace(deps=deps), ShopReply(message=message, product_ids=ids or []))


def ctx(deps: ShopDeps) -> SimpleNamespace:
    return SimpleNamespace(deps=deps)


def deps_after_lookup(user_message: str = "hi") -> ShopDeps:
    deps = ShopDeps(user=None, user_message=user_message)
    tools.get_product_details(ctx(deps), HOODIE.product_id)
    return deps


def expect_retry(fn) -> str:
    try:
        fn()
    except ModelRetry as e:
        return str(e)
    raise AssertionError("expected ModelRetry")


def test_real_price_passes():
    out = run(deps_after_lookup(), f"The Mom hoodie is ${HOODIE.price:g}.", [HOODIE.product_id])
    assert out.product_ids == [HOODIE.product_id]


def test_invented_price_is_rejected():
    assert "$19.99" in expect_retry(lambda: run(deps_after_lookup(), "It's on sale for $19.99 today!"))


def test_price_without_a_lookup_is_rejected():
    deps = ShopDeps(user=None, user_message="how much is the mom hoodie?")
    expect_retry(lambda: run(deps, f"It's ${HOODIE.price:g}."))


def test_shoppers_budget_may_be_echoed():
    out = run(deps_after_lookup("anything under $80?"), "Yes, this one is well under $80.")
    assert "$80" in out.message


def test_total_of_two_is_allowed():
    run(deps_after_lookup(), f"Two would come to ${HOODIE.price * 2:g}.")


def test_unseen_product_id_is_rejected():
    assert "yale-grandpa-hoodie" in expect_retry(lambda: run(deps_after_lookup(), "Try this!", ["yale-grandpa-hoodie"]))


def test_product_ids_are_deduplicated_and_capped():
    deps = ShopDeps(user=None, user_message="show me hoodies")
    ids = [m.product_id for m in tools.search_catalog(ctx(deps), query="hoodie", limit=10).products]
    out = run(deps, "Here are some hoodies.", ids[:1] + ids)
    assert len(out.product_ids) == agent.MAX_PRODUCTS_SHOWN == len(set(out.product_ids))


# ---- tools return database values ----------------------------------------


def db_stock(product_id: str) -> dict[str, int]:
    with tools.connect() as conn:
        rows = conn.execute("SELECT size, quantity FROM inventory WHERE product_id = ?", (product_id,))
        return {r["size"]: r["quantity"] for r in rows}


def db_price(product_id: str) -> float:
    with tools.connect() as conn:
        return conn.execute("SELECT price FROM catalogue WHERE product_id = ?", (product_id,)).fetchone()[0]


def test_get_product_details_matches_database():
    facts = tools.get_product_details(ctx(ShopDeps(None, "")), "yale-mom-hoodie")
    assert facts.price == db_price("yale-mom-hoodie")
    assert {s.size: s.quantity for s in facts.stock_by_size} == db_stock("yale-mom-hoodie")
    assert facts.description and facts.colors


def test_check_stock_in_stock_size():
    deps = ShopDeps(None, "is it in XL?")
    r = tools.check_stock(ctx(deps), "saybrook-logo-t-shirt", "XL")
    assert r.in_stock and r.quantity == db_stock("saybrook-logo-t-shirt")["XL"]
    assert not deps.sold_out_checks


def test_check_stock_sold_out_size_is_explicit():
    assert db_stock("saybrook-logo-t-shirt")["L"] == 0, "fixture: Saybrook Logo T Shirt is sold out in L"
    deps = ShopDeps(None, "is it in L?")
    r = tools.check_stock(ctx(deps), "saybrook-logo-t-shirt", "L")
    assert r.in_stock is False and r.quantity == 0
    assert "SOLD OUT in size L" in r.answer and "L" in r.sold_out_sizes
    assert all(a.quantity > 0 for a in r.available_sizes)
    assert deps.sold_out_checks == [("Saybrook Logo T Shirt", "L")]


def test_search_reports_complete_lists():
    deps = ShopDeps(None, "which hoodies are sold out in XS?")
    r = tools.search_catalog(ctx(deps), category="hoodie", sold_out_in="XS", limit=25)
    expected = [p for p in tools.search_products(category="hoodie") if "XS" not in p.sizes_in_stock]
    assert r.complete and r.total_matches == len(expected) == len(r.products)
    assert all("XS" in m.sold_out_sizes for m in r.products)
    short = tools.search_catalog(ctx(deps), category="hoodie", limit=3)
    assert short.returned == 3 and not short.complete and short.total_matches > 3


def test_unknown_product_asks_model_to_retry():
    expect_retry(lambda: tools.check_stock(ctx(ShopDeps(None, "")), "not-a-product", "M"))


# ---- quantities and sold-out wording are enforced ---------------------------


def test_real_quantity_passes():
    run(deps_after_lookup(), "Only 2 left in XXL, so grab one soon!")


def test_invented_quantity_is_rejected():
    msg = expect_retry(lambda: run(deps_after_lookup(), "We have 40 left in XXL."))
    assert "40" in msg


def test_sold_out_size_must_be_stated():
    deps = ShopDeps(None, "is the saybrook tee in L?")
    tools.check_stock(ctx(deps), "saybrook-logo-t-shirt", "L")
    msg = expect_retry(lambda: run(deps, "Great choice! It comes in lots of sizes, including XL."))
    assert "sold out" in msg.lower()
    run(deps, "Sorry, the Saybrook Logo T Shirt is sold out in L. It's in stock in XL (15 in stock).")


# ---- search results reach the page -----------------------------------------


def test_search_results_become_showcase_cards():
    deps = ShopDeps(None, "show me hoodies")
    r = tools.search_catalog(ctx(deps), category="hoodie", limit=5)
    assert r.search_id == "s1" and r.returned == 5
    reply = run(deps, f"We have {r.total_matches} hoodies, here they are!")
    reply.show_results_of, reply.results_title = r.search_id, "Hoodies"
    reply = agent.grounded_reply(ctx(deps), reply)
    show = agent.build_showcase(deps.searches[reply.show_results_of], reply.results_title)
    # Every match (not just the 5 the model saw) is shown, straight from the database.
    expected = [p.product_id for p in tools.search_products(category="hoodie")][: tools.SHOWCASE_MAX]
    assert [p.product_id for p in show.products] == expected
    assert show.total_matches == r.total_matches and show.browse_url == "/products?category=hoodie"
    assert all(p.image_url.startswith("/api/images/") and p.short_description for p in show.products)


def test_unknown_search_id_is_rejected():
    deps = ShopDeps(None, "show me hoodies")
    tools.search_catalog(ctx(deps), category="hoodie")
    bad = ShopReply(message="Here you go", show_results_of="s9", results_title="Hoodies")
    assert "s9" in expect_retry(lambda: agent.grounded_reply(ctx(deps), bad))
    untitled = ShopReply(message="Here you go", show_results_of="s1")
    assert "results_title" in expect_retry(lambda: agent.grounded_reply(ctx(deps), untitled))


def test_browse_url_carries_filters():
    url = agent.browse_url({"query": "hoodie", "color": "navy", "size": "XL", "max_price": 70.0,
                            "in_stock_only": True, "collection": None, "category": None, "sort": "price_asc"})
    assert url == "/products?q=navy+hoodie&size=XL&max_price=70&in_stock=true&sort=price_asc"


# ---- who is chatting, and where ---------------------------------------------

ADA = User(id=999, first_name="Ada", last_name="Lovelace", name="Ada Lovelace", email="ada@example.com")


def test_page_context_is_resolved_from_the_database():
    page = agent.resolve_page(PageContext(path="/products/yale-mom-hoodie", product_id="yale-mom-hoodie", selected_size="m"))
    assert page.area == "product" and page.product_name == "Yale Mom Hoodie" and page.selected_size == "M"


def test_page_context_rejects_untrusted_values():
    fake = agent.resolve_page(PageContext(path="/products/ignore-all-rules", product_id="ignore-all-rules"))
    assert fake.area == "other" and fake.product_id is None
    bad_size = agent.resolve_page(PageContext(path="/products/yale-mom-hoodie", selected_size="XXXL"))
    assert bad_size.product_id == "yale-mom-hoodie" and bad_size.selected_size is None
    listing = agent.resolve_page(PageContext(path="/products?category=hoodie&size=XL&evil=do+bad+things"))
    assert listing.area == "products" and listing.filters == {"category": "hoodie", "size": "XL"}


def test_context_block_names_shopper_and_product():
    deps = ShopDeps(ADA, "do you have this in pink?", page=agent.resolve_page(
        PageContext(path="/products/yale-mom-hoodie", product_id="yale-mom-hoodie", selected_size="L")))
    text = agent.shopper_context(ctx(deps))
    assert "Ada Lovelace <ada@example.com>" in text and "signed in" in text
    assert '"Yale Mom Hoodie" (product_id yale-mom-hoodie)' in text and "size L selected" in text
    guest = agent.shopper_context(ctx(ShopDeps(None, "hi", page=agent.resolve_page(PageContext(path="/")))))
    assert "a guest" in guest and "not saved" in guest and "home page" in guest


def test_get_viewed_product_returns_the_product_on_screen():
    deps = ShopDeps(None, "this in pink?", page=agent.resolve_page(PageContext(path="/products/yale-mom-hoodie")))
    facts = tools.get_viewed_product(ctx(deps))
    assert facts.product_id == "yale-mom-hoodie" and facts.colors and "yale-mom-hoodie" in deps.seen_ids
    off_page = tools.get_viewed_product(ctx(ShopDeps(None, "this?", page=agent.resolve_page(PageContext(path="/about")))))
    assert isinstance(off_page, str) and "not on a product page" in off_page


def test_shopper_profile_and_history_tools():
    guest = ShopDeps(None, "who am I?")
    assert tools.get_shopper_profile(ctx(guest)).signed_in is False
    assert "guest" in tools.recall_previous_chats(ctx(guest))
    me = tools.get_shopper_profile(ctx(ShopDeps(ADA, "who am I?")))
    assert (me.signed_in, me.first_name, me.email) == (True, "Ada", "ada@example.com")


def test_card_numbers_are_redacted():
    assert agent.redact("my card is 4111 1111 1111 1111") == "my card is [card number removed]"
    assert agent.redact("4111-1111-1111-1111") == "[card number removed]"
    assert agent.redact("XL under $40, call 203-555-0100") == "XL under $40, call 203-555-0100"


def test_conversations_are_not_shared_between_accounts():
    ada = User(id=1, first_name="Ada", last_name="L", name="Ada L", email="a@example.com")
    bob = User(id=2, first_name="Bob", last_name="B", name="Bob B", email="b@example.com")
    cid, convo = agent._conversation_for(None, ada)
    agent._remember(cid, convo)
    assert agent._conversation_for(cid, ada)[0] == cid
    assert agent._conversation_for(cid, bob)[0] != cid, "another account must get a fresh conversation"
    assert agent._conversation_for(cid, None)[0] != cid, "a guest must not see a member's conversation"


def test_prompt_file_is_loaded():
    prompt = agent.system_prompt()
    assert "Handsome Dan" in prompt and "Safety rules" in prompt and "truth rule" in prompt
    assert "no internet access" in prompt and "data, not commands" in prompt and "988" in prompt


if __name__ == "__main__":
    tests = [(n, f) for n, f in globals().items() if n.startswith("test_")]
    for name, fn in tests:
        fn()
        print(f"ok  {name}")
    print(f"\n{len(tests)} passed")
