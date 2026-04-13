from unittest.mock import patch, MagicMock


def _mock_auth_ok(username="jame"):
    m = MagicMock()
    m.status_code = 200
    m.json.return_value = {"ok": True, "username": username}
    return m


def _mock_auth_fail():
    m = MagicMock()
    m.status_code = 401
    return m


def _mock_signup_ok():
    m = MagicMock()
    m.status_code = 201
    return m


def _mock_signup_conflict(detail="Username already taken"):
    m = MagicMock()
    m.status_code = 409
    m.json.return_value = {"detail": detail}
    return m


# ── CSRF token ─────────────────────────────────────────────────────────────────

def test_home_sets_csrf_token(client):
    with client.session_transaction() as sess:
        sess.clear()
    client.get("/")
    with client.session_transaction() as sess:
        assert "csrf_token" in sess


def test_home_reuses_existing_csrf_token(client):
    with client.session_transaction() as sess:
        sess["csrf_token"] = "existing-token"
    client.get("/")
    with client.session_transaction() as sess:
        assert sess["csrf_token"] == "existing-token"


# ── Login ──────────────────────────────────────────────────────────────────────

def test_login_valid_credentials(client):
    with client.session_transaction() as sess:
        sess["csrf_token"] = "valid-token"
    with patch("app.http_client.post", side_effect=[_mock_auth_ok(), MagicMock(status_code=200)]):
        r = client.post("/login", data={"username": "jame", "password": "secret", "csrf_token": "valid-token"})
    assert r.status_code == 302
    with client.session_transaction() as sess:
        assert sess["username"] == "jame"


def test_login_bad_csrf(client):
    with client.session_transaction() as sess:
        sess["csrf_token"] = "real-token"
    r = client.post("/login", data={"username": "jame", "password": "secret", "csrf_token": "wrong-token"})
    assert r.status_code == 403


def test_login_wrong_password(client):
    with client.session_transaction() as sess:
        sess["csrf_token"] = "valid-token"
    with patch("app.http_client.post", return_value=_mock_auth_fail()):
        r = client.post("/login", data={"username": "jame", "password": "wrongpass", "csrf_token": "valid-token"})
    assert r.status_code == 401


def test_login_unknown_user(client):
    with client.session_transaction() as sess:
        sess["csrf_token"] = "valid-token"
    with patch("app.http_client.post", return_value=_mock_auth_fail()):
        r = client.post("/login", data={"username": "nobody", "password": "x", "csrf_token": "valid-token"})
    assert r.status_code == 401


# ── Logout ─────────────────────────────────────────────────────────────────────

def test_logout_clears_session(client):
    with client.session_transaction() as sess:
        sess["username"] = "jame"
    client.get("/logout")
    with client.session_transaction() as sess:
        assert "username" not in sess


# ── Signup ─────────────────────────────────────────────────────────────────────

def test_signup_success(client):
    with client.session_transaction() as sess:
        sess["csrf_token"] = "valid-token"
    with patch("app.http_client.post", side_effect=[_mock_signup_ok(), MagicMock(status_code=200)]):
        r = client.post("/signup", data={
            "username": "newuser",
            "email": "newuser@example.com",
            "password": "password123",
            "confirm_password": "password123",
            "csrf_token": "valid-token",
        })
    assert r.status_code == 302
    with client.session_transaction() as sess:
        assert sess["username"] == "newuser"


def test_signup_password_mismatch(client):
    with client.session_transaction() as sess:
        sess["csrf_token"] = "valid-token"
    r = client.post("/signup", data={
        "username": "newuser",
        "email": "newuser@example.com",
        "password": "password123",
        "confirm_password": "different",
        "csrf_token": "valid-token",
    })
    assert r.status_code == 302
    with client.session_transaction() as sess:
        assert "username" not in sess


def test_signup_bad_csrf(client):
    with client.session_transaction() as sess:
        sess["csrf_token"] = "real-token"
    r = client.post("/signup", data={
        "username": "newuser",
        "email": "newuser@example.com",
        "password": "password123",
        "confirm_password": "password123",
        "csrf_token": "wrong-token",
    })
    assert r.status_code == 403


def test_signup_duplicate_username(client):
    with client.session_transaction() as sess:
        sess["csrf_token"] = "valid-token"
    with patch("app.http_client.post", return_value=_mock_signup_conflict("Username already taken")):
        r = client.post("/signup", data={
            "username": "taken",
            "email": "taken@example.com",
            "password": "password123",
            "confirm_password": "password123",
            "csrf_token": "valid-token",
        })
    assert r.status_code == 302
    with client.session_transaction() as sess:
        assert "username" not in sess
