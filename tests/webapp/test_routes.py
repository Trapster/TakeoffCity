import os

ADMIN_USER = os.environ["WEB_ADMIN_USERNAME"]


def test_dashboard_redirects_unauthenticated(client):
    r = client.get("/dashboard")
    assert r.status_code == 302
    assert "/" in r.headers["Location"]


def test_dashboard_renders_authenticated(client):
    with client.session_transaction() as sess:
        sess["username"] = ADMIN_USER
    r = client.get("/dashboard")
    assert r.status_code == 200


def test_group_page_renders_and_sets_csrf(client):
    r = client.get("/group/abc123")
    assert r.status_code == 200
    with client.session_transaction() as sess:
        assert "csrf_token" in sess


def test_admin_redirects_non_admin(client):
    with client.session_transaction() as sess:
        sess["username"] = "notadmin"
    r = client.get("/admin")
    assert r.status_code == 302


def test_admin_renders_for_admin(client):
    with client.session_transaction() as sess:
        sess["username"] = ADMIN_USER
    r = client.get("/admin")
    assert r.status_code == 200
