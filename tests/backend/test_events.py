def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_list_events_empty(client):
    r = client.get("/events", headers={"X-Username": "alice"})
    assert r.status_code == 200
    assert r.json() == []


def test_create_and_list_event(client):
    client.post(
        "/events",
        json={"name": "Weekend Trip", "earliest_date": "2024-08-01", "latest_date": "2024-08-10"},
        headers={"X-Username": "alice"},
    )
    r = client.get("/events", headers={"X-Username": "alice"})
    assert len(r.json()) == 1
    assert r.json()[0]["name"] == "Weekend Trip"
    assert r.json()[0]["feedback_count"] == 0


def test_list_events_scoped_to_user(client):
    client.post(
        "/events",
        json={"name": "Alice Trip", "earliest_date": "2024-08-01", "latest_date": "2024-08-05"},
        headers={"X-Username": "alice"},
    )
    client.post(
        "/events",
        json={"name": "Bob Trip", "earliest_date": "2024-09-01", "latest_date": "2024-09-05"},
        headers={"X-Username": "bob"},
    )
    r = client.get("/events", headers={"X-Username": "alice"})
    assert len(r.json()) == 1
    assert r.json()[0]["name"] == "Alice Trip"


def test_create_event_invalid_date(client):
    r = client.post(
        "/events",
        json={"name": "Trip", "earliest_date": "bad-date", "latest_date": "2024-08-10"},
        headers={"X-Username": "alice"},
    )
    assert r.status_code == 422


def test_create_event_date_order_violation(client):
    r = client.post(
        "/events",
        json={"name": "Trip", "earliest_date": "2024-08-10", "latest_date": "2024-08-01"},
        headers={"X-Username": "alice"},
    )
    assert r.status_code == 422


def test_get_event_found_with_ownership(client):
    create_r = client.post(
        "/events",
        json={"name": "My Event", "earliest_date": "2024-07-01", "latest_date": "2024-07-05"},
        headers={"X-Username": "alice"},
    )
    event_id = create_r.json()["event_id"]

    r = client.get(f"/events/{event_id}", headers={"X-Username": "alice"})
    assert r.status_code == 200
    assert r.json()["is_owner"] is True

    r2 = client.get(f"/events/{event_id}", headers={"X-Username": "bob"})
    assert r2.json()["is_owner"] is False


def test_get_event_not_found(client):
    r = client.get("/events/nonexistent-id", headers={"X-Username": "alice"})
    assert r.status_code == 404


def test_delete_event_authorized(client):
    create_r = client.post(
        "/events",
        json={"name": "Delete Me", "earliest_date": "2024-07-01", "latest_date": "2024-07-05"},
        headers={"X-Username": "alice"},
    )
    event_id = create_r.json()["event_id"]
    r = client.delete(f"/events/{event_id}", headers={"X-Username": "alice"})
    assert r.status_code == 200


def test_delete_event_not_found(client):
    r = client.delete("/events/nonexistent-id", headers={"X-Username": "alice"})
    assert r.status_code == 404


def test_delete_event_unauthorized(client):
    create_r = client.post(
        "/events",
        json={"name": "Alice Event", "earliest_date": "2024-07-01", "latest_date": "2024-07-05"},
        headers={"X-Username": "alice"},
    )
    event_id = create_r.json()["event_id"]
    r = client.delete(f"/events/{event_id}", headers={"X-Username": "bob"})
    assert r.status_code == 403


def test_create_event_with_min_max_days(client):
    create_r = client.post(
        "/events",
        json={"name": "Trip", "earliest_date": "2025-05-01", "latest_date": "2025-06-30",
              "min_days": 5, "max_days": 7},
        headers={"X-Username": "alice"},
    )
    assert create_r.status_code == 200
    event_id = create_r.json()["event_id"]
    r = client.get(f"/events/{event_id}", headers={"X-Username": "alice"})
    assert r.json()["min_days"] == 5
    assert r.json()["max_days"] == 7


def test_create_event_organiser_attends_true(client):
    create_r = client.post(
        "/events",
        json={"name": "Trip", "earliest_date": "2025-05-01", "latest_date": "2025-06-30",
              "organiser_attends": True},
        headers={"X-Username": "alice"},
    )
    event_id = create_r.json()["event_id"]
    r = client.get(f"/events/{event_id}", headers={"X-Username": "alice"})
    assert r.json()["organiser_attends"] is True


def test_get_event_returns_new_fields(client):
    create_r = client.post(
        "/events",
        json={"name": "Trip", "earliest_date": "2025-05-01", "latest_date": "2025-06-30"},
        headers={"X-Username": "alice"},
    )
    event_id = create_r.json()["event_id"]
    r = client.get(f"/events/{event_id}", headers={"X-Username": "alice"})
    data = r.json()
    assert "min_days" in data
    assert "max_days" in data
    assert "organiser_attends" in data
    assert data["min_days"] is None
    assert data["max_days"] is None
    assert data["organiser_attends"] is False
