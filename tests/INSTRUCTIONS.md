# Test Instructions

## Structure

```
tests/
  backend/   — FastAPI backend tests (run against real PostgreSQL in Docker)
  webapp/    — Flask webapp tests (HTTP calls to backend are mocked)
  INSTRUCTIONS.md
```

## Adding tests

### Backend tests
- Place new test files in `tests/backend/`
- Use the `client` fixture (defined in `conftest.py`) for HTTP requests
- The database is automatically cleaned between each test — no teardown needed
- Import from `main` directly: `from main import SomeModel, some_function`
- Use real data — no mocking of the DB layer

```python
def test_something(client):
    r = client.post("/events", json={...}, headers={"X-Username": "alice"})
    assert r.status_code == 200
```

### Webapp tests
- Place new test files in `tests/webapp/`
- Use the `client` fixture (Flask test client) from `conftest.py`
- Mock all calls to the backend with `unittest.mock.patch("app.http_client.request", ...)`
- Set session state via `client.session_transaction()`

```python
from unittest.mock import patch, MagicMock

def test_something(client):
    mock = MagicMock()
    mock.status_code = 200
    mock.headers = {"Content-Type": "application/json"}
    mock.iter_content.return_value = iter([b'{"ok":true}'])

    with patch("app.http_client.request", return_value=mock):
        r = client.get("/api/events")
    assert r.status_code == 200
```

## Coverage guidelines

- Test the success path and the main failure cases (auth, not-found, validation)
- One helper function per test file is fine; avoid shared fixtures beyond `conftest.py`
- Keep each test focused on one behaviour — no multi-assertion sprawl

## Running tests (see README for Docker commands)
