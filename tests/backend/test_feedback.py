def _create_event(client, username="alice"):
    r = client.post(
        "/events",
        json={"name": "Trip", "earliest_date": "2024-06-01", "latest_date": "2024-06-30"},
        headers={"X-Username": username},
    )
    return r.json()["event_id"]


def test_submit_feedback_success(client):
    event_id = _create_event(client)
    r = client.post(
        f"/events/{event_id}/feedback",
        json={"city": "Paris", "start_date": "2024-06-05", "end_date": "2024-06-10"},
    )
    assert r.status_code == 200
    assert r.json()["message"] == "Feedback submitted successfully"

    # feedback_count increments
    r2 = client.get(f"/events/{event_id}", headers={"X-Username": "alice"})
    assert r2.json()["feedback_count"] == 1


def test_submit_feedback_event_not_found(client):
    r = client.post(
        "/events/nonexistent/feedback",
        json={"city": "Paris", "start_date": "2024-06-05", "end_date": "2024-06-10"},
    )
    assert r.status_code == 404


def test_submit_feedback_invalid_dates(client):
    event_id = _create_event(client)
    r = client.post(
        f"/events/{event_id}/feedback",
        json={"city": "Paris", "start_date": "bad-date", "end_date": "2024-06-10"},
    )
    assert r.status_code == 422


def test_submit_feedback_start_after_end(client):
    event_id = _create_event(client)
    r = client.post(
        f"/events/{event_id}/feedback",
        json={"city": "Paris", "start_date": "2024-06-20", "end_date": "2024-06-10"},
    )
    assert r.status_code == 422
