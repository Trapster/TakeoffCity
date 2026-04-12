import json
import pytest


USER = {"username": "alice", "email": "alice@example.com", "password": "s3cr3tPass!"}
JSON_HEADERS = {"Content-Type": "application/json"}


def _create(client, data=None):
    return client.post("/internal/users", json=data or USER)


# ── Signup ─────────────────────────────────────────────────────────────────────

def test_signup_creates_user(client):
    r = _create(client)
    assert r.status_code == 201
    assert r.json() == {"ok": True}


def test_signup_duplicate_username(client):
    _create(client)
    r = _create(client, {**USER, "email": "other@example.com"})
    assert r.status_code == 409
    assert "Username" in r.json()["detail"]


def test_signup_duplicate_email(client):
    _create(client)
    r = _create(client, {**USER, "username": "bob"})
    assert r.status_code == 409
    assert "Email" in r.json()["detail"]


def test_password_not_stored_in_plaintext(client):
    from main import SessionLocal, UserDB
    _create(client)
    db = SessionLocal()
    try:
        user = db.query(UserDB).filter(UserDB.username == USER["username"]).first()
        assert user is not None
        assert USER["password"] not in user.password_hash
        assert ":" in user.password_hash  # salt:hash format
    finally:
        db.close()


# ── Auth verify ────────────────────────────────────────────────────────────────

def test_auth_valid_credentials(client):
    _create(client)
    r = client.post("/internal/auth", json={"username": USER["username"], "password": USER["password"]})
    assert r.status_code == 200
    assert r.json()["username"] == USER["username"]


def test_auth_wrong_password(client):
    _create(client)
    r = client.post("/internal/auth", json={"username": USER["username"], "password": "wrongpass"})
    assert r.status_code == 401


def test_auth_unknown_user(client):
    r = client.post("/internal/auth", json={"username": "nobody", "password": "x"})
    assert r.status_code == 401


# ── Get profile ────────────────────────────────────────────────────────────────

def test_get_user_me(client):
    _create(client)
    r = client.get("/internal/users/me", params={"username": USER["username"]})
    assert r.status_code == 200
    data = r.json()
    assert data["username"] == USER["username"]
    assert data["email"] == USER["email"]
    assert "member_since" in data


def test_get_user_me_not_found(client):
    r = client.get("/internal/users/me", params={"username": "nobody"})
    assert r.status_code == 404


# ── Change password ────────────────────────────────────────────────────────────

def test_change_password_success(client):
    _create(client)
    r = client.put("/internal/users/me/password", json={
        "username": USER["username"],
        "current_password": USER["password"],
        "new_password": "newPassw0rd!",
    })
    assert r.status_code == 200
    # Old password no longer works
    r2 = client.post("/internal/auth", json={"username": USER["username"], "password": USER["password"]})
    assert r2.status_code == 401
    # New password works
    r3 = client.post("/internal/auth", json={"username": USER["username"], "password": "newPassw0rd!"})
    assert r3.status_code == 200


def test_change_password_wrong_current(client):
    _create(client)
    r = client.put("/internal/users/me/password", json={
        "username": USER["username"],
        "current_password": "wrongpass",
        "new_password": "doesntmatter",
    })
    assert r.status_code == 403


# ── Change email ───────────────────────────────────────────────────────────────

def test_change_email_success(client):
    _create(client)
    r = client.put("/internal/users/me/email", json={
        "username": USER["username"],
        "password": USER["password"],
        "new_email": "newalice@example.com",
    })
    assert r.status_code == 200
    profile = client.get("/internal/users/me", params={"username": USER["username"]}).json()
    assert profile["email"] == "newalice@example.com"


def test_change_email_wrong_password(client):
    _create(client)
    r = client.put("/internal/users/me/email", json={
        "username": USER["username"],
        "password": "wrongpass",
        "new_email": "new@example.com",
    })
    assert r.status_code == 403


def test_change_email_duplicate(client):
    _create(client)
    _create(client, {"username": "bob", "email": "bob@example.com", "password": "bobpass123"})
    r = client.put("/internal/users/me/email", json={
        "username": USER["username"],
        "password": USER["password"],
        "new_email": "bob@example.com",
    })
    assert r.status_code == 409


# ── Delete account ─────────────────────────────────────────────────────────────

def _delete_user(client, username, password):
    return client.request("DELETE", "/internal/users/me", json={"username": username, "password": password})


def test_delete_account_success(client):
    from main import SessionLocal, UserDB
    _create(client)
    r = _delete_user(client, USER["username"], USER["password"])
    assert r.status_code == 200
    db = SessionLocal()
    try:
        assert db.query(UserDB).filter(UserDB.username == USER["username"]).first() is None
    finally:
        db.close()


def test_delete_account_wrong_password(client):
    _create(client)
    r = _delete_user(client, USER["username"], "wrongpass")
    assert r.status_code == 403


def test_delete_account_cascades_events(client):
    from main import SessionLocal, EventDB
    _create(client)
    # Create an event owned by this user
    client.post("/events", json={
        "name": "Team Offsite",
        "earliest_date": "2025-06-01",
        "latest_date": "2025-06-30",
    }, headers={"X-Username": USER["username"]})
    # Delete the account
    _delete_user(client, USER["username"], USER["password"])
    db = SessionLocal()
    try:
        events = db.query(EventDB).filter(EventDB.creator_username == USER["username"]).all()
        assert events == []
    finally:
        db.close()
