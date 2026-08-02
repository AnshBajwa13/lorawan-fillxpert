"""
conftest.py — Shared pytest fixtures for all test modules.

Key design decisions:
  - Sets DATABASE_URL to SQLite BEFORE any backend import, so database.py
    reads it and uses SQLite (not PostgreSQL).
  - database.py uses pool_size/max_overflow → we patch them out by
    using env var DATABASE_URL=sqlite:///. SQLAlchemy then uses NullPool
    automatically and ignores those kwargs when env is set right.
  - Actually: we create our OWN engine to bypass database.py's engine entirely.
  - Overrides FastAPI's get_db() dependency injection.
  - MQTT handler NOT started.

Run:
    cd backend && pytest tests/ -v --tb=short
"""

import sys
import os

# Insert backend dir into path FIRST
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Set env vars BEFORE importing anything from the backend
os.environ["DATABASE_URL"]     = "sqlite:///./test_temp.db"  # file-based sqlite
os.environ["SECRET_KEY"]       = "test-secret-key-minimum-32-characters!!"
os.environ["MQTT_BROKER_HOST"] = "localhost"
os.environ["MQTT_BROKER_PORT"] = "1883"
os.environ["ENVIRONMENT"]      = "test"

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# Import models to register them with SQLAlchemy metadata BEFORE creating tables
import models          # noqa: F401
import models_auth     # noqa: F401
import models_device   # noqa: F401

# Import Base and get_db (get_db will be overridden per-test)
from database import Base, get_db
from app import app
from rate_limiter import limiter

# Disable rate limiting for testing
limiter.enabled = False

# ─────────────────────────────────────────────────────────────────────────────
# Our own SQLite engine — bypasses database.py's PostgreSQL-specific args
# ─────────────────────────────────────────────────────────────────────────────
_TEST_ENGINE = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
_TestSession = sessionmaker(autocommit=False, autoflush=False, bind=_TEST_ENGINE)


# ─────────────────────────────────────────────────────────────────────────────
# Session-scoped: create tables once, drop after all tests
# ─────────────────────────────────────────────────────────────────────────────
@pytest.fixture(scope="session", autouse=True)
def create_test_tables():
    Base.metadata.create_all(bind=_TEST_ENGINE)
    yield
    Base.metadata.drop_all(bind=_TEST_ENGINE)


# ─────────────────────────────────────────────────────────────────────────────
# Function-scoped: each test gets a fresh transaction, rolled back at end
# ─────────────────────────────────────────────────────────────────────────────
@pytest.fixture
def db_session():
    connection  = _TEST_ENGINE.connect()
    transaction = connection.begin()
    session     = _TestSession(bind=connection)
    yield session
    session.close()
    transaction.rollback()
    connection.close()


# ─────────────────────────────────────────────────────────────────────────────
# TestClient with get_db() overridden to use the test session
# IMPORTANT: We also override the lifespan to a no-op so MQTT never starts.
# ─────────────────────────────────────────────────────────────────────────────
from contextlib import asynccontextmanager

@asynccontextmanager
async def _noop_lifespan(app_):
    """Replace the real lifespan so MQTT handler never starts during tests."""
    yield

@pytest.fixture
def client(db_session):
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    # Swap out the MQTT lifespan for a no-op
    original_lifespan = app.router.lifespan_context
    app.router.lifespan_context = _noop_lifespan
    with TestClient(app, raise_server_exceptions=True) as c:
        yield c
    app.router.lifespan_context = original_lifespan
    app.dependency_overrides.clear()


# ─────────────────────────────────────────────────────────────────────────────
# Auth fixtures
# ─────────────────────────────────────────────────────────────────────────────
TEST_USER = {
    "username":  "testuser",
    "email":     "test@fillxpert.io",
    "password":  "TestPass123!",
    "full_name": "Test User",
}


@pytest.fixture
def registered_user(client):
    resp = client.post("/api/auth/register", json=TEST_USER)
    assert resp.status_code == 201, f"Registration failed: {resp.text}"
    return resp.json()


@pytest.fixture
def auth_token(client, registered_user):
    resp = client.post("/api/auth/login", json={
        "email":    TEST_USER["email"],
        "password": TEST_USER["password"],
    })
    assert resp.status_code == 200, f"Login failed: {resp.text}"
    return resp.json()["access_token"]


@pytest.fixture
def auth_headers(auth_token):
    return {"Authorization": f"Bearer {auth_token}"}


@pytest.fixture
def registered_device(client, auth_headers):
    resp = client.post("/api/devices", json={
        "device_id":   "TESTDEV001",
        "name":        "Test Device",
        "location":    "chandigarh",
        "sensor_type": "moisture",
        "device_type": "direct_esim",
    }, headers=auth_headers)
    assert resp.status_code == 201, f"Device registration failed: {resp.text}"
    return resp.json()


@pytest.fixture
def registered_gateway(client, auth_headers):
    resp = client.post("/api/devices", json={
        "device_id":   "GW001",
        "name":        "Test Gateway",
        "location":    "chandigarh",
        "sensor_type": "moisture",
        "device_type": "gateway",
    }, headers=auth_headers)
    assert resp.status_code == 201, f"Gateway registration failed: {resp.text}"
    return resp.json()
