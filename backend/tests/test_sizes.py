"""Checks for "You might also like" and the recommended size — on a temporary
copy of the database, so the real `data/campus_customs.db` is never touched.

Run from backend/ with .venv active:

    python tests/test_sizes.py
"""

from __future__ import annotations

import sys
from pathlib import Path

# Run from backend/:  python tests/<this file>.py   (the app modules live one folder up)
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import shutil
import tempfile

import tools

_tmp = Path(tempfile.mkdtemp()) / "campus_customs.db"
shutil.copy(tools.DB_FILE, _tmp)
tools.DB_FILE = _tmp

from fastapi.testclient import TestClient  # noqa: E402

import main  # noqa: E402

main.init_auth_tables()
tools.init_size_tables()

SAYBROOK_TEE = "saybrook-logo-t-shirt"  # sold out in L; XL has stock
NEW = {"first_name": "Size", "last_name": "Tester", "email": "size.tester@example.com",
       "password": "Correct-Horse-Battery-9", "confirm_password": "Correct-Horse-Battery-9"}


def stock(pid: str) -> dict[str, int]:
    return {s.size: s.quantity for s in tools.get_product(pid).stock_by_size}


# ---- You might also like ------------------------------------------------------


def test_related_excludes_itself_and_matches_identity():
    names = [p.name for p in tools.related_products(SAYBROOK_TEE, 6)]
    assert "Saybrook Logo T Shirt" not in names
    assert any("Saybrook" in n for n in names[:2]), "same college should rank first"


def test_related_prefers_items_in_stock_in_my_size():
    for p in tools.related_products("yale-grandpa-hoodie", 6, "M")[:3]:
        assert p.total_stock > 0 and "M" in p.sizes_in_stock


def test_related_route():
    with TestClient(main.app) as c:
        assert len(c.get(f"/api/products/{SAYBROOK_TEE}/related", params={"limit": 4}).json()) == 4
        assert c.get("/api/products/nope/related").status_code == 404


# ---- Recommended size -------------------------------------------------------


def test_guest_without_size_gets_asked():
    rec = tools.recommend_size_for(SAYBROOK_TEE, stock(SAYBROOK_TEE), None, None)
    assert rec.basis == "none" and rec.recommended_size is None


def test_guest_size_in_stock():
    rec = tools.recommend_size_for(SAYBROOK_TEE, stock(SAYBROOK_TEE), None, "xl")
    assert (rec.recommended_size, rec.exact_match, rec.quantity) == ("XL", True, stock(SAYBROOK_TEE)["XL"])


def test_sold_out_size_moves_to_nearest_in_stock_size_up_first():
    rec = tools.recommend_size_for(SAYBROOK_TEE, stock(SAYBROOK_TEE), None, "L")
    assert rec.usual_size == "L" and rec.recommended_size == "XL" and rec.exact_match is False
    assert "sold out in L" in rec.reason


def test_signed_in_saved_size_and_history():
    with TestClient(main.app) as c:
        c.post("/api/auth/register", json=NEW)
        uid = c.get("/api/auth/me").json()["id"]

        # No saved size, no history: the browser size is used.
        assert tools.usual_size(uid, "S")[0:2] == ("S", "my_size")

        # History alone: picking M on two items makes M the usual size.
        for pid in ("yale-mom-hoodie", "yale-dad-hoodie"):
            assert c.post("/api/me/size-history", json={"product_id": pid, "size": "M"}).status_code == 204
        size, basis, why = tools.usual_size(uid, None)
        assert (size, basis) == ("M", "history") and "picked M 2 times" in why

        # Repeating the same pick the same day is not counted twice.
        assert tools.record_size_event(uid, "yale-mom-hoodie", "M", "selected") is False

        # A saved size outweighs a little history.
        assert c.put("/api/me/size", json={"size": "XL"}).json() == {"size": "XL"}
        assert c.get("/api/me/size").json() == {"size": "XL"}
        rec = c.get(f"/api/products/{SAYBROOK_TEE}/size-recommendation").json()
        assert rec["recommended_size"] == "XL" and rec["basis"] == "my_size" and "saved size" in rec["reason"]

        # Purchases weigh most (no checkout yet; recorded directly here).
        for pid in ("yale-mom-hoodie", "yale-dad-hoodie", "yale-uncle-hoodie"):
            tools.record_size_event(uid, pid, "L", "purchased")
        size, basis, why = tools.usual_size(uid, None)
        assert (size, basis) == ("L", "history") and "bought 3 items in L" in why


def test_size_routes_need_login_and_valid_sizes():
    with TestClient(main.app) as c:
        assert c.get("/api/me/size").status_code == 401
        assert c.post("/api/me/size-history", json={"product_id": SAYBROOK_TEE, "size": "M"}).status_code == 401
        c.post("/api/auth/login", json={"email": NEW["email"], "password": NEW["password"]})
        assert c.put("/api/me/size", json={"size": "XXXL"}).status_code == 422


if __name__ == "__main__":
    tests = [(n, f) for n, f in globals().items() if n.startswith("test_")]
    for name, fn in tests:
        fn()
        print(f"ok  {name}")
    print(f"\n{len(tests)} passed (on a temporary copy of the database)")
