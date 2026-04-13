import os

os.environ.setdefault("SECRET_KEY", "test-secret-key")
os.environ.setdefault("BACKEND_URL", "http://mock-backend")
os.environ.setdefault("WEB_ADMIN_USERNAME", "testadmin")
os.environ.setdefault("WEB_PASSWORD", "testpassword")

import pytest
from app import app as flask_app


@pytest.fixture
def client():
    flask_app.config["TESTING"] = True
    with flask_app.test_client() as c:
        yield c
