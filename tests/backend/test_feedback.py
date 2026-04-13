from main import FeedbackDB


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


def test_submit_feedback_stores_username_from_header(client, db):
    event_id = _create_event(client)
    r = client.post(
        f"/events/{event_id}/feedback",
        json={"city": "Paris", "start_date": "2024-06-05", "end_date": "2024-06-10"},
        headers={"X-Username": "alice"},
    )
    assert r.status_code == 200
    fb = db.query(FeedbackDB).filter_by(event_id=event_id).first()
    assert fb.attendee_username == "alice"


def test_submit_feedback_stores_attendee_email(client, db):
    event_id = _create_event(client)
    r = client.post(
        f"/events/{event_id}/feedback",
        json={
            "city": "Berlin",
            "start_date": "2024-06-05",
            "end_date": "2024-06-10",
            "attendee_email": "traveller@example.com",
        },
    )
    assert r.status_code == 200
    fb = db.query(FeedbackDB).filter_by(event_id=event_id).first()
    assert fb.attendee_email == "traveller@example.com"


def test_submit_feedback_anonymous_no_email_still_works(client):
    event_id = _create_event(client)
    r = client.post(
        f"/events/{event_id}/feedback",
        json={"city": "Tokyo", "start_date": "2024-06-05", "end_date": "2024-06-10"},
    )
    assert r.status_code == 200


def test_submit_feedback_empty_username_stored_as_none(client, db):
    event_id = _create_event(client)
    client.post(
        f"/events/{event_id}/feedback",
        json={"city": "Paris", "start_date": "2024-06-05", "end_date": "2024-06-10"},
        headers={"X-Username": ""},
    )
    fb = db.query(FeedbackDB).filter_by(event_id=event_id).first()
    assert fb.attendee_username is None


def test_submit_feedback_no_dates_still_works(client):
    event_id = _create_event(client)
    r = client.post(
        f"/events/{event_id}/feedback",
        json={"city": "Tokyo"},
    )
    assert r.status_code == 200


def test_submit_feedback_with_availability_periods(client, db):
    event_id = _create_event(client)
    periods = '[{"start":"2025-05-05","end":"2025-05-10"},{"start":"2025-05-20","end":"2025-05-25"}]'
    r = client.post(
        f"/events/{event_id}/feedback",
        json={"city": "Paris", "availability_periods": periods},
    )
    assert r.status_code == 200
    fb = db.query(FeedbackDB).filter_by(event_id=event_id).first()
    assert fb.availability_periods == periods


def test_submit_feedback_stores_adults_and_children(client, db):
    event_id = _create_event(client)
    r = client.post(
        f"/events/{event_id}/feedback",
        json={"city": "Paris", "start_date": "2024-06-05", "end_date": "2024-06-10",
              "adults": 2, "children": 3},
    )
    assert r.status_code == 200
    fb = db.query(FeedbackDB).filter_by(event_id=event_id).first()
    assert fb.adults == 2
    assert fb.children == 3


def test_submit_feedback_adults_defaults_to_one(client, db):
    event_id = _create_event(client)
    client.post(
        f"/events/{event_id}/feedback",
        json={"city": "Paris", "start_date": "2024-06-05", "end_date": "2024-06-10"},
    )
    fb = db.query(FeedbackDB).filter_by(event_id=event_id).first()
    assert fb.adults == 1
    assert fb.children == 0
