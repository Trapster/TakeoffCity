def _create_event(client):
    r = client.post(
        "/events",
        json={"name": "Trip", "earliest_date": "2024-06-01", "latest_date": "2024-06-30"},
        headers={"X-Username": "alice"},
    )
    return r.json()["event_id"]


def test_calculate_event_not_found(client):
    r = client.post("/calculate/nonexistent-id")
    assert r.status_code == 404


def test_calculate_marks_event_calculated(client):
    event_id = _create_event(client)

    r = client.get(f"/events/{event_id}", headers={"X-Username": "alice"})
    assert r.json()["calculated"] is False

    client.post(f"/calculate/{event_id}")

    r2 = client.get(f"/events/{event_id}", headers={"X-Username": "alice"})
    assert r2.json()["calculated"] is True


def test_calculate_streams_text_plain(client):
    event_id = _create_event(client)
    r = client.post(f"/calculate/{event_id}")
    assert r.status_code == 200
    assert "text/plain" in r.headers["content-type"]
    assert len(r.text) > 0
