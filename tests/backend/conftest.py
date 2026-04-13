import os

os.environ.setdefault("WEB_ADMIN_USERNAME", "testadmin")
os.environ.setdefault("WEB_ADMIN_EMAIL", "testadmin@admin.local")
os.environ.setdefault("WEB_PASSWORD", "testpassword")

import pytest
from fastapi.testclient import TestClient
from main import app, get_db, Base, engine, SessionLocal


def override_get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db


@pytest.fixture(scope="session", autouse=True)
def create_tables():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield


@pytest.fixture(autouse=True)
def clean_db():
    yield
    with engine.begin() as conn:
        for table in reversed(Base.metadata.sorted_tables):
            conn.execute(table.delete())


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
