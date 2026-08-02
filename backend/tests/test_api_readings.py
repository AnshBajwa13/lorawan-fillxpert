"""
API integration tests for sensor data endpoints.

Tests /api/sensor-data (GET + POST), /api/gateways, /api/nodes, /api/stats.
Covers: authentication, multi-tenancy (user isolation), time filtering,
        filter options independence from data results (the dashboard refresh bug).

Run:
    pytest tests/test_api_readings.py -v
"""

import pytest
from datetime import datetime, timedelta


# ─────────────────────────────────────────────────────────────────────────────
# Helper: insert a reading via POST /api/sensor-data
# ─────────────────────────────────────────────────────────────────────────────

def post_reading(client, headers, gateway="chandigarh", node="SNR001",
                 moisture=45.0, hours_ago=0):
    ts = (datetime.utcnow() - timedelta(hours=hours_ago)).isoformat() + "Z"
    return client.post("/api/sensor-data", json={
        "gateway_id": gateway,
        "node_id":    node,
        "timestamp":  ts,
        "moisture":   moisture,
    }, headers=headers)


# ─────────────────────────────────────────────────────────────────────────────
# GET /api/sensor-data
# ─────────────────────────────────────────────────────────────────────────────

class TestGetSensorData:
    def test_empty_returns_empty_list(self, client, auth_headers):
        resp = client.get("/api/sensor-data", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json() == []

    def test_saved_reading_appears_in_list(self, client, auth_headers):
        post_reading(client, auth_headers)
        resp = client.get("/api/sensor-data", headers=auth_headers)
        assert resp.status_code == 200
        assert len(resp.json()) == 1

    def test_readings_ordered_newest_first(self, client, auth_headers):
        """Most recent reading should appear first."""
        post_reading(client, auth_headers, moisture=10.0, hours_ago=2)
        post_reading(client, auth_headers, moisture=20.0, hours_ago=1)
        post_reading(client, auth_headers, moisture=30.0, hours_ago=0)
        data = client.get("/api/sensor-data", headers=auth_headers).json()
        moistures = [r.get("moisture") for r in data if r.get("moisture") is not None]
        assert moistures[0] == 30.0  # newest first

    def test_limit_parameter_respected(self, client, auth_headers):
        for _ in range(5):
            post_reading(client, auth_headers)
        resp = client.get("/api/sensor-data?limit=2", headers=auth_headers)
        assert len(resp.json()) <= 2

    def test_gateway_id_filter(self, client, auth_headers):
        post_reading(client, auth_headers, gateway="chandigarh", node="D001")
        post_reading(client, auth_headers, gateway="sangrur",    node="D002")
        resp = client.get("/api/sensor-data?gateway_id=chandigarh", headers=auth_headers)
        data = resp.json()
        assert all(r["gateway_id"] == "chandigarh" for r in data)

    def test_node_id_filter(self, client, auth_headers):
        post_reading(client, auth_headers, node="D001")
        post_reading(client, auth_headers, node="D002")
        resp = client.get("/api/sensor-data?node_id=D001", headers=auth_headers)
        data = resp.json()
        assert all(r["node_id"] == "D001" for r in data)

    def test_hours_filter_excludes_old_readings(self, client, auth_headers):
        """A reading 3 hours old should NOT appear when hours=1."""
        post_reading(client, auth_headers, moisture=99.0, hours_ago=3)  # old
        post_reading(client, auth_headers, moisture=50.0, hours_ago=0)  # recent
        resp = client.get("/api/sensor-data?hours=1", headers=auth_headers)
        data = resp.json()
        # Only the recent reading should be returned
        moistures = [r.get("moisture") for r in data if r.get("moisture") is not None]
        assert 99.0 not in moistures
        assert 50.0 in moistures


# ─────────────────────────────────────────────────────────────────────────────
# Multi-tenancy — user isolation
# ─────────────────────────────────────────────────────────────────────────────

class TestMultiTenantIsolation:
    def test_user_only_sees_own_readings(self, client, auth_headers):
        """User A's readings must not be visible to User B."""
        # User A posts a reading
        post_reading(client, auth_headers, moisture=77.0)

        # Register and login User B
        client.post("/api/auth/register", json={
            "username": "userb",
            "email":    "userb@test.io",
            "password": "UserBPass123!",
            "full_name": "User B",
        })
        login_resp = client.post("/api/auth/login", json={
            "email": "userb@test.io",
            "password": "UserBPass123!",
        })
        token_b = login_resp.json()["access_token"]
        headers_b = {"Authorization": f"Bearer {token_b}"}

        # User B should see 0 readings
        resp_b = client.get("/api/sensor-data", headers=headers_b)
        assert resp_b.status_code == 200
        assert len(resp_b.json()) == 0


# ─────────────────────────────────────────────────────────────────────────────
# GET /api/gateways and /api/nodes
# ─────────────────────────────────────────────────────────────────────────────

class TestGatewaysAndNodes:
    def test_gateways_empty_initially(self, client, auth_headers):
        resp = client.get("/api/gateways", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json() == []

    def test_gateways_returns_unique_locations(self, client, auth_headers):
        post_reading(client, auth_headers, gateway="chandigarh")
        post_reading(client, auth_headers, gateway="chandigarh")  # duplicate
        post_reading(client, auth_headers, gateway="sangrur")
        resp = client.get("/api/gateways", headers=auth_headers)
        gateways = resp.json()
        assert len(gateways) == 2
        assert "chandigarh" in gateways
        assert "sangrur"    in gateways

    def test_nodes_empty_initially(self, client, auth_headers):
        resp = client.get("/api/nodes", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json() == []

    def test_nodes_returns_unique_device_ids(self, client, auth_headers):
        post_reading(client, auth_headers, node="D001")
        post_reading(client, auth_headers, node="D001")  # duplicate
        post_reading(client, auth_headers, node="D002")
        resp = client.get("/api/nodes", headers=auth_headers)
        nodes = resp.json()
        assert len(nodes) == 2
        assert "D001" in nodes
        assert "D002" in nodes

    def test_nodes_filtered_by_gateway(self, client, auth_headers):
        """Dashboard Bug Fix 3b: /api/nodes?gateway_id= scopes to location."""
        post_reading(client, auth_headers, gateway="chandigarh", node="D001")
        post_reading(client, auth_headers, gateway="chandigarh", node="D002")
        post_reading(client, auth_headers, gateway="sangrur",    node="D003")
        resp = client.get("/api/nodes?gateway_id=chandigarh", headers=auth_headers)
        nodes = resp.json()
        assert "D001" in nodes
        assert "D002" in nodes
        assert "D003" not in nodes  # different location

    def test_gateways_endpoint_always_returns_all_locations(self, client, auth_headers):
        """
        Dashboard Bug Fix 2: /api/gateways should return ALL locations
        regardless of the time filter on /api/sensor-data.
        This verifies the endpoints are independent.
        """
        # Post an old reading (would be excluded by hours=1 filter)
        post_reading(client, auth_headers, gateway="oldsite", hours_ago=100)
        # /api/gateways has no time filter — should still return "oldsite"
        resp = client.get("/api/gateways", headers=auth_headers)
        assert "oldsite" in resp.json()


# ─────────────────────────────────────────────────────────────────────────────
# GET /api/stats
# ─────────────────────────────────────────────────────────────────────────────

class TestStats:
    def test_stats_zero_initially(self, client, auth_headers):
        resp = client.get("/api/stats", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_readings"] == 0
        assert data["total_gateways"] == 0
        assert data["total_nodes"]    == 0
        assert data["latest_reading_time"] is None

    def test_stats_counts_correct(self, client, auth_headers):
        post_reading(client, auth_headers, gateway="chandigarh", node="D001")
        post_reading(client, auth_headers, gateway="chandigarh", node="D002")
        post_reading(client, auth_headers, gateway="sangrur",    node="D003")
        resp = client.get("/api/stats", headers=auth_headers)
        data = resp.json()
        assert data["total_readings"] == 3
        assert data["total_gateways"] == 2   # chandigarh, sangrur
        assert data["total_nodes"]    == 3   # D001, D002, D003
        assert data["latest_reading_time"] is not None

    def test_stats_does_not_leak_other_users(self, client, auth_headers):
        """Stats only count for the current user."""
        post_reading(client, auth_headers)  # 1 reading for our user

        # Another user with their own reading
        client.post("/api/auth/register", json={
            "username": "statuser",
            "email":    "statuser@test.io",
            "password": "StatPass123!",
            "full_name": "Stat User",
        })
        login = client.post("/api/auth/login", json={"email": "statuser@test.io", "password": "StatPass123!"})
        h2 = {"Authorization": f"Bearer {login.json()['access_token']}"}
        post_reading(client, h2)  # their reading

        # Our user should only see 1, not 2
        stats = client.get("/api/stats", headers=auth_headers).json()
        assert stats["total_readings"] == 1
