def test_admin_stats_non_admin_forbidden(client):
    r = client.get("/admin/stats", headers={"X-Username": "notanadmin"})
    assert r.status_code == 403


def test_admin_stats_returns_expected_structure(client):
    r = client.get("/admin/stats", headers={"X-Username": "jame"})
    assert r.status_code == 200
    data = r.json()
    assert set(data.keys()) == {"all_time", "period", "series", "top_cities"}
    assert set(data["all_time"].keys()) == {"total_groups", "total_calculated", "unique_users", "total_feedback"}
    assert set(data["period"].keys()) == {"groups_created", "groups_calculated", "feedback_submitted", "active_users"}
    assert set(data["series"].keys()) == {"groups", "feedback", "logins"}


def test_admin_stats_invalid_period_does_not_crash(client):
    r = client.get("/admin/stats?period=99y", headers={"X-Username": "jame"})
    assert r.status_code == 200


def test_record_activity(client):
    r = client.post("/internal/activity", json={"username": "alice", "action": "login"})
    assert r.status_code == 200
    assert r.json() == {"ok": True}
