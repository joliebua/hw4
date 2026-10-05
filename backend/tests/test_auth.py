"""Checks for the create-account / log-in flow — run against a temporary copy
of the database, so the real `data/campus_customs.db` is never touched.

Run from backend/ with .venv active:

    python tests/test_auth.py
"""

from __future__ import annotations

import sys
from pathlib import Path

# Run from backend/:  python tests/<this file>.py   (the app modules live one folder up)
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import hashlib
import shutil
import sqlite3
import tempfile

import tools

# Point every connection at a throwaway copy before the app is imported.
_tmp = Path(tempfile.mkdtemp()) / "campus_customs.db"
shutil.copy(tools.DB_FILE, _tmp)
tools.DB_FILE = _tmp

from fastapi.testclient import TestClient  # noqa: E402

import main  # noqa: E402

# The test account that ships with the provided database.
TEST_EMAIL = "test@campuscustoms.yale.edu"
TEST_PASSWORD = "password"

NEW = {
    "first_name": "Brand",
    "last_name": "New",
    "email": "brand.new@example.com",
    "password": "Correct-Horse-Battery-9",
    "confirm_password": "Correct-Horse-Battery-9",
}


def raw_user(email: str) -> sqlite3.Row:
    conn = sqlite3.connect(_tmp)
    conn.row_factory = sqlite3.Row
    try:
        return conn.execute("SELECT * FROM users WHERE LOWER(email) = ?", (email.lower(),)).fetchone()
    finally:
        conn.close()


def client() -> TestClient:
    main._failures.clear()
    return TestClient(main.app)


def test_provided_test_user_can_log_in():
    with client() as c:
        r = c.post("/api/auth/login", json={"email": TEST_EMAIL, "password": TEST_PASSWORD})
        assert r.status_code == 200, r.text
        assert r.json()["email"] == TEST_EMAIL and "password_hash" not in r.json()
        assert c.get("/api/auth/me").json()["first_name"] == "Test"
    assert raw_user(TEST_EMAIL)["password_hash"].startswith("$argon2id$")


def test_legacy_pbkdf2_hash_is_upgraded_on_login():
    # A user stored the way the provided database stores them.
    salt, password = "legacysalt0001", "Legacy-Pass-42"
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), main.LEGACY_PBKDF2_ITERATIONS).hex()
    conn = sqlite3.connect(_tmp)
    conn.execute(
        "INSERT INTO users (name, first_name, last_name, email, password_hash) VALUES (?,?,?,?,?)",
        ("Legacy User", "Legacy", "User", "legacy@example.com", f"pbkdf2_sha256${salt}${digest}"),
    )
    conn.commit()
    conn.close()

    with client() as c:
        assert c.post("/api/auth/login", json={"email": "legacy@example.com", "password": "wrong-one"}).status_code == 401
        assert c.post("/api/auth/login", json={"email": "legacy@example.com", "password": password}).status_code == 200
    assert raw_user("legacy@example.com")["password_hash"].startswith("$argon2id$"), "should upgrade to Argon2id"
    with client() as c:
        assert c.post("/api/auth/login", json={"email": "LEGACY@example.com", "password": password}).status_code == 200


def test_wrong_password_and_unknown_email_look_the_same():
    with client() as c:
        a = c.post("/api/auth/login", json={"email": TEST_EMAIL, "password": "nope-nope"})
        b = c.post("/api/auth/login", json={"email": "nobody@example.com", "password": "nope-nope"})
    assert a.status_code == b.status_code == 401
    assert a.json() == b.json()


def test_new_account_is_stored_hashed_and_can_log_in():
    with client() as c:
        r = c.post("/api/auth/register", json=NEW)
        assert r.status_code == 201, r.text
        body = r.json()
        assert (body["first_name"], body["last_name"], body["name"]) == ("Brand", "New", "Brand New")
        assert c.get("/api/auth/me").json()["email"] == NEW["email"], "register should sign the shopper in"

    row = raw_user(NEW["email"])
    assert row["first_name"] == "Brand" and row["last_name"] == "New"
    assert row["password_hash"].startswith("$argon2id$v=19$m=65536,t=3,p=4$")
    assert NEW["password"] not in row["password_hash"]

    with client() as c:
        assert c.post("/api/auth/login", json={"email": NEW["email"], "password": NEW["password"]}).status_code == 200


def test_registration_rules():
    with client() as c:
        dup = c.post("/api/auth/register", json={**NEW, "email": NEW["email"].upper()})
        assert dup.status_code == 409
        mismatch = c.post("/api/auth/register", json={**NEW, "email": "x1@example.com", "confirm_password": "different-123"})
        assert mismatch.status_code == 422 and "match" in mismatch.text
        short = c.post("/api/auth/register", json={**NEW, "email": "x2@example.com", "password": "short", "confirm_password": "short"})
        assert short.status_code == 422
        common = c.post("/api/auth/register", json={**NEW, "email": "x3@example.com", "password": "password123", "confirm_password": "password123"})
        assert common.status_code == 422 and "common" in common.text
        blank = c.post("/api/auth/register", json={**NEW, "email": "x4@example.com", "first_name": "   "})
        assert blank.status_code == 422


def test_session_cookie_is_httponly_and_only_hash_is_stored():
    with client() as c:
        r = c.post("/api/auth/login", json={"email": NEW["email"], "password": NEW["password"]})
        cookie = r.headers["set-cookie"]
        assert "HttpOnly" in cookie and "SameSite=lax" in cookie
        token = r.cookies.get(main.SESSION_COOKIE)
        conn = sqlite3.connect(_tmp)
        stored = [t for (t,) in conn.execute("SELECT token_hash FROM sessions")]
        conn.close()
        assert token not in stored and main._token_hash(token) in stored

        assert c.post("/api/auth/logout").status_code == 204
        assert c.get("/api/auth/me").json() is None


def test_repeated_failures_are_throttled():
    with client() as c:
        codes = [
            c.post("/api/auth/login", json={"email": NEW["email"], "password": "wrong-guess"}).status_code
            for _ in range(6)
        ]
    assert codes[:5] == [401] * 5 and codes[5] == 429


if __name__ == "__main__":
    tests = [(n, f) for n, f in globals().items() if n.startswith("test_")]
    for name, fn in tests:
        fn()
        print(f"ok  {name}")
    print(f"\n{len(tests)} passed (on a temporary copy of the database)")
