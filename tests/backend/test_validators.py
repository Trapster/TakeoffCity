import pytest
from pydantic import ValidationError
from main import _validate_iso_date, EventCreate, FeedbackCreate


def test_validate_iso_date_valid():
    assert _validate_iso_date("2024-06-15") == "2024-06-15"


def test_validate_iso_date_invalid():
    with pytest.raises(ValueError, match="not a valid"):
        _validate_iso_date("not-a-date")


def test_validate_iso_date_wrong_separator():
    with pytest.raises(ValueError):
        _validate_iso_date("2024/06/15")


# EventCreate ──────────────────────────────────────────────────────────────────

def test_event_create_valid():
    e = EventCreate(name="Trip", earliest_date="2024-01-01", latest_date="2024-01-10")
    assert e.name == "Trip"


def test_event_create_same_dates_valid():
    e = EventCreate(name="Trip", earliest_date="2024-06-01", latest_date="2024-06-01")
    assert e.earliest_date == e.latest_date


def test_event_create_earliest_after_latest():
    with pytest.raises(ValidationError, match="must not be after"):
        EventCreate(name="Trip", earliest_date="2024-06-10", latest_date="2024-06-01")


def test_event_create_invalid_date_format():
    with pytest.raises(ValidationError):
        EventCreate(name="Trip", earliest_date="bad", latest_date="2024-06-01")


# FeedbackCreate ───────────────────────────────────────────────────────────────

def test_feedback_create_valid():
    f = FeedbackCreate(city="Paris", start_date="2024-03-01", end_date="2024-03-07")
    assert f.city == "Paris"


def test_feedback_create_start_after_end():
    with pytest.raises(ValidationError, match="must not be after"):
        FeedbackCreate(city="Paris", start_date="2024-03-10", end_date="2024-03-01")
