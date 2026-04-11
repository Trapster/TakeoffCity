from unittest.mock import patch


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


def test_login_valid_credentials(client):
    with client.session_transaction() as sess:
        sess["csrf_token"] = "valid-token"
    with patch("app.http_client.post"):
        r = client.post("/login", data={"username": "jame", "csrf_token": "valid-token"})
    assert r.status_code == 302
    with client.session_transaction() as sess:
        assert sess["username"] == "jame"


def test_login_bad_csrf(client):
    with client.session_transaction() as sess:
        sess["csrf_token"] = "real-token"
    r = client.post("/login", data={"username": "jame", "csrf_token": "wrong-token"})
    assert r.status_code == 403


def test_login_invalid_username(client):
    with client.session_transaction() as sess:
        sess["csrf_token"] = "valid-token"
    r = client.post("/login", data={"username": "hacker", "csrf_token": "valid-token"})
    assert r.status_code == 401


def test_logout_clears_session(client):
    with client.session_transaction() as sess:
        sess["username"] = "jame"
    client.get("/logout")
    with client.session_transaction() as sess:
        assert "username" not in sess
