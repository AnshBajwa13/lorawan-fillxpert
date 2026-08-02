"""
API integration tests for Authentication endpoints.

Tests /api/auth/register, /api/auth/login, and token-protected routes.
Uses FastAPI TestClient + SQLite in-memory DB (see conftest.py).

Run:
    pytest tests/test_api_auth.py -v
"""

import pytest


class TestRegister:
    def test_register_success(self, client):
        resp = client.post("/api/auth/register", json={
            "username": "newuser",
            "email":    "newuser@test.io",
            "password": "NewPass123!",
            "full_name": "New User",
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["username"] == "newuser"
        assert data["email"]    == "newuser@test.io"
        # Password must NEVER be in the response
        assert "password"        not in data
        assert "hashed_password" not in data

    def test_register_duplicate_email_rejected(self, client, registered_user):
        resp = client.post("/api/auth/register", json={
            "username": "different_user",
            "email":    "test@fillxpert.io",   # same email as registered_user
            "password": "AnotherPass789!",
            "full_name": "Different",
        })
        assert resp.status_code == 400
        assert "already" in resp.json()["detail"].lower()

    def test_register_duplicate_username_rejected(self, client, registered_user):
        resp = client.post("/api/auth/register", json={
            "username": "testuser",            # same username as registered_user
            "email":    "different@test.io",
            "password": "AnotherPass789!",
            "full_name": "Different",
        })
        assert resp.status_code == 400
        assert "already" in resp.json()["detail"].lower()

    def test_register_weak_password_rejected(self, client):
        """Pydantic validator should enforce minimum password requirements."""
        resp = client.post("/api/auth/register", json={
            "username": "weakuser",
            "email":    "weak@test.io",
            "password": "123",   # too short
            "full_name": "Weak",
        })
        # Either 422 (validation) or 400 (business logic) — not 201
        assert resp.status_code in {400, 422}


class TestLogin:
    def test_login_success_returns_token(self, client, registered_user):
        resp = client.post("/api/auth/login", json={
            "email":    "test@fillxpert.io",
            "password": "TestPass123!",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        assert len(data["access_token"]) > 20  # must be a real JWT

    def test_login_wrong_password_rejected(self, client, registered_user):
        resp = client.post("/api/auth/login", json={
            "email":    "test@fillxpert.io",
            "password": "WrongPassword!",
        })
        assert resp.status_code in {400, 401}

    def test_login_nonexistent_user_rejected(self, client):
        resp = client.post("/api/auth/login", json={
            "email":    "ghost@fillxpert.io",
            "password": "GhostPass123!",
        })
        assert resp.status_code in {400, 401}

    def test_login_case_sensitive_password(self, client, registered_user):
        """Passwords are case-sensitive."""
        resp = client.post("/api/auth/login", json={
            "email":    "test@fillxpert.io",
            "password": "testpass123!",  # correct is "TestPass123!"
        })
        assert resp.status_code in {400, 401}


class TestProtectedRoutes:
    def test_sensor_data_without_token_returns_403(self, client):
        """FastAPI HTTPBearer returns 403 (not 401) when no credentials provided."""
        resp = client.get("/api/sensor-data")
        assert resp.status_code == 403

    def test_devices_without_token_returns_403(self, client):
        resp = client.get("/api/devices")
        assert resp.status_code == 403

    def test_gateways_without_token_returns_403(self, client):
        resp = client.get("/api/gateways")
        assert resp.status_code == 403

    def test_nodes_without_token_returns_403(self, client):
        resp = client.get("/api/nodes")
        assert resp.status_code == 403

    def test_stats_without_token_returns_403(self, client):
        resp = client.get("/api/stats")
        assert resp.status_code == 403

    def test_sensor_data_with_token_returns_200(self, client, auth_headers):
        resp = client.get("/api/sensor-data", headers=auth_headers)
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_invalid_token_rejected(self, client):
        resp = client.get("/api/sensor-data", headers={
            "Authorization": "Bearer invalid.jwt.token"
        })
        assert resp.status_code == 401

    def test_malformed_auth_header_rejected(self, client):
        """HTTPBearer returns 403 when header is not 'Bearer <token>' format."""
        resp = client.get("/api/sensor-data", headers={
            "Authorization": "NotBearer token123"
        })
        assert resp.status_code == 403
