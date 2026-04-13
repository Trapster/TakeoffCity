from unittest.mock import patch, MagicMock


def _mock_response(status=200, content=b'{"ok":true}', content_type="application/json"):
    mock = MagicMock()
    mock.status_code = status
    mock.headers = {"Content-Type": content_type}
    mock.iter_content.return_value = iter([content])
    return mock


def test_proxy_blocks_internal_paths(client):
    r = client.get("/api/internal/activity")
    assert r.status_code == 404


def test_proxy_injects_username_header(client):
    with client.session_transaction() as sess:
        sess["username"] = "jame"
    with patch("app.http_client.request", return_value=_mock_response()) as mock_req:
        client.get("/api/events")
    _, kwargs = mock_req.call_args
    assert kwargs["headers"]["X-Username"] == "jame"


def test_proxy_injects_empty_username_when_unauthenticated(client):
    with patch("app.http_client.request", return_value=_mock_response()) as mock_req:
        client.get("/api/events")
    _, kwargs = mock_req.call_args
    assert kwargs["headers"]["X-Username"] == ""


def test_proxy_forwards_post_with_json(client):
    payload = {"name": "Trip", "earliest_date": "2024-01-01", "latest_date": "2024-01-10"}
    with patch("app.http_client.request", return_value=_mock_response()) as mock_req:
        client.post("/api/events", json=payload)
    args, kwargs = mock_req.call_args
    assert args[0] == "POST"
    assert kwargs["json"] == payload


def test_proxy_forwards_delete(client):
    with patch("app.http_client.request", return_value=_mock_response()) as mock_req:
        client.delete("/api/events/abc123")
    args, _ = mock_req.call_args
    assert args[0] == "DELETE"


def test_proxy_passes_through_status_code(client):
    with patch("app.http_client.request", return_value=_mock_response(status=404)):
        r = client.get("/api/events/missing")
    assert r.status_code == 404
