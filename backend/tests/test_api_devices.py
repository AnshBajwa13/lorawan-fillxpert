"""
API integration tests for device management endpoints.

Tests /api/devices CRUD, LoRa gateway architecture registration,
config push (MQTT publish is mocked), config history, and deletion.

The key insight: push_config() calls aiomqtt — we mock it so tests
don't need a real MQTT broker but still test the DB + API logic.

Run:
    pytest tests/test_api_devices.py -v
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def register_device(client, headers, device_id="D001", location="chandigarh",
                    device_type="direct_esim", **extra):
    body = {
        "device_id":   device_id,
        "location":    location,
        "sensor_type": "moisture",
        "device_type": device_type,
        **extra,
    }
    return client.post("/api/devices", json=body, headers=headers)


def mock_mqtt_publish():
    """Context manager that patches aiomqtt.Client so no real MQTT call is made."""
    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__  = AsyncMock(return_value=False)
    mock_client.publish    = AsyncMock()
    return patch("routers.devices.aiomqtt.Client", return_value=mock_client)


# ─────────────────────────────────────────────────────────────────────────────
# GET /api/devices  (list)
# ─────────────────────────────────────────────────────────────────────────────

class TestListDevices:
    def test_empty_fleet_initially(self, client, auth_headers):
        resp = client.get("/api/devices", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json() == []

    def test_registered_device_appears_in_list(self, client, auth_headers):
        register_device(client, auth_headers)
        resp = client.get("/api/devices", headers=auth_headers)
        assert resp.status_code == 200
        devices = resp.json()
        assert len(devices) == 1
        assert devices[0]["device_id"] == "D001"

    def test_user_only_sees_own_devices(self, client, auth_headers):
        """Multi-tenancy: user A's devices must not appear for user B."""
        register_device(client, auth_headers, device_id="D001")

        # Register + login user B
        client.post("/api/auth/register", json={
            "username": "userb_devices",
            "email":    "userb_devices@test.io",
            "password": "UserBPass123!",
            "full_name": "B",
        })
        login = client.post("/api/auth/login", json={
            "email": "userb_devices@test.io", "password": "UserBPass123!"
        })
        headers_b = {"Authorization": f"Bearer {login.json()['access_token']}"}

        resp = client.get("/api/devices", headers=headers_b)
        assert resp.json() == []


# ─────────────────────────────────────────────────────────────────────────────
# POST /api/devices  (register)
# ─────────────────────────────────────────────────────────────────────────────

class TestRegisterDevice:
    def test_register_direct_esim_device(self, client, auth_headers):
        resp = register_device(client, auth_headers, device_id="SNR001")
        assert resp.status_code == 201
        data = resp.json()
        assert data["device_id"]   == "SNR001"
        assert data["device_type"] == "direct_esim"
        assert data["is_online"]   is False
        assert data["cfg_version"] == 0

    def test_register_lora_gateway(self, client, auth_headers):
        resp = register_device(client, auth_headers, device_id="GW001",
                               device_type="gateway")
        assert resp.status_code == 201
        data = resp.json()
        assert data["device_type"] == "gateway"

    def test_register_sensor_node_linked_to_gateway(self, client, auth_headers):
        """sensor_node must point to an existing gateway device."""
        # Register gateway first
        register_device(client, auth_headers, device_id="GW001", device_type="gateway")
        # Now register sensor node
        resp = register_device(client, auth_headers, device_id="NODE001",
                               device_type="sensor_node",
                               gateway_device_id="GW001", lora_addr=1)
        assert resp.status_code == 201
        data = resp.json()
        assert data["device_type"]       == "sensor_node"
        assert data["gateway_device_id"] == "GW001"
        assert data["lora_addr"]         == 1

    def test_sensor_node_with_nonexistent_gateway_rejected(self, client, auth_headers):
        """gateway_device_id must point to a registered gateway."""
        resp = register_device(client, auth_headers, device_id="NODE002",
                               device_type="sensor_node",
                               gateway_device_id="NONEXISTENT_GW")
        assert resp.status_code == 422
        assert "not found" in resp.json()["detail"].lower() or \
               "gateway" in resp.json()["detail"].lower()

    def test_invalid_device_type_rejected(self, client, auth_headers):
        resp = register_device(client, auth_headers, device_id="BAD001",
                               device_type="invalid_type")
        assert resp.status_code == 422

    def test_duplicate_device_id_rejected(self, client, auth_headers):
        register_device(client, auth_headers, device_id="DUP001")
        resp = register_device(client, auth_headers, device_id="DUP001")
        assert resp.status_code == 409
        assert "already" in resp.json()["detail"].lower() or \
               "registered" in resp.json()["detail"].lower()

    def test_response_includes_all_lora_fields(self, client, auth_headers):
        resp = register_device(client, auth_headers, device_id="LORA001",
                               device_type="gateway")
        data = resp.json()
        assert "device_type"       in data
        assert "gateway_device_id" in data
        assert "lora_addr"         in data

    def test_name_defaults_to_device_id_when_not_provided(self, client, auth_headers):
        resp = register_device(client, auth_headers, device_id="NONAME001")
        data = resp.json()
        assert data["name"] == "NONAME001"

    def test_location_stored_correctly(self, client, auth_headers):
        resp = register_device(client, auth_headers, device_id="LOC001",
                               location="sangrur")
        assert resp.json()["location"] == "sangrur"


# ─────────────────────────────────────────────────────────────────────────────
# GET /api/devices/{device_id}
# ─────────────────────────────────────────────────────────────────────────────

class TestGetDevice:
    def test_get_own_device(self, client, auth_headers, registered_device):
        resp = client.get(f"/api/devices/{registered_device['device_id']}",
                         headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["device_id"] == registered_device["device_id"]

    def test_get_nonexistent_device_returns_404(self, client, auth_headers):
        resp = client.get("/api/devices/GHOST999", headers=auth_headers)
        assert resp.status_code == 404

    def test_get_other_users_device_returns_404(self, client, auth_headers, registered_device):
        """A different user should not be able to access another user's device."""
        client.post("/api/auth/register", json={
            "username": "thief",
            "email":    "thief@test.io",
            "password": "ThiefPass123!",
            "full_name": "Thief",
        })
        login = client.post("/api/auth/login",
                           json={"email": "thief@test.io", "password": "ThiefPass123!"})
        headers_thief = {"Authorization": f"Bearer {login.json()['access_token']}"}
        resp = client.get(f"/api/devices/{registered_device['device_id']}",
                         headers=headers_thief)
        assert resp.status_code == 404

    def test_latest_config_is_none_initially(self, client, auth_headers, registered_device):
        resp = client.get(f"/api/devices/{registered_device['device_id']}",
                         headers=auth_headers)
        assert resp.json()["latest_config"] is None


# ─────────────────────────────────────────────────────────────────────────────
# POST /api/devices/{device_id}/config
# MQTT publish is mocked — no real broker needed
# ─────────────────────────────────────────────────────────────────────────────

class TestPushConfig:
    def test_push_config_success(self, client, auth_headers, registered_device):
        with mock_mqtt_publish():
            resp = client.post(
                f"/api/devices/{registered_device['device_id']}/config",
                json={"sensor_type": "moisture", "freq": 2,
                      "time1": "10:00", "time2": "14:00"},
                headers=auth_headers,
            )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"]      == "published"
        assert data["cfg_version"] == 1

    def test_push_config_increments_version(self, client, auth_headers, registered_device):
        with mock_mqtt_publish():
            client.post(f"/api/devices/{registered_device['device_id']}/config",
                       json={"sensor_type": "moisture", "freq": 1, "time1": "08:00"},
                       headers=auth_headers)
            resp2 = client.post(f"/api/devices/{registered_device['device_id']}/config",
                               json={"sensor_type": "temperature", "freq": 1, "time1": "12:00"},
                               headers=auth_headers)
        assert resp2.json()["cfg_version"] == 2

    def test_push_config_payload_string_correct_format(self, client, auth_headers, registered_device):
        """
        Payload format: [sensor:2][freq:2][time1:4][ver:2]
        moisture=01, freq=1, time=10:00, ver=01 → "010110000001"
        """
        with mock_mqtt_publish():
            resp = client.post(
                f"/api/devices/{registered_device['device_id']}/config",
                json={"sensor_type": "moisture", "freq": 1, "time1": "10:00"},
                headers=auth_headers,
            )
        payload_str = resp.json()["payload_str"]
        # First 2 chars = sensor code, next 2 = freq
        assert payload_str[:2] == "01"   # moisture
        assert payload_str[2:4] == "01"  # freq=1

    def test_push_config_updates_device_cfg_version(self, client, auth_headers, registered_device):
        """After push, GET /api/devices/{id} should show new cfg_version."""
        with mock_mqtt_publish():
            client.post(f"/api/devices/{registered_device['device_id']}/config",
                       json={"sensor_type": "moisture", "freq": 1, "time1": "08:00"},
                       headers=auth_headers)
        dev_resp = client.get(f"/api/devices/{registered_device['device_id']}",
                             headers=auth_headers)
        assert dev_resp.json()["cfg_version"] == 1

    def test_push_config_appears_in_history(self, client, auth_headers, registered_device):
        with mock_mqtt_publish():
            client.post(f"/api/devices/{registered_device['device_id']}/config",
                       json={"sensor_type": "ph", "freq": 1, "time1": "09:00"},
                       headers=auth_headers)
        hist = client.get(f"/api/devices/{registered_device['device_id']}/configs",
                         headers=auth_headers)
        assert hist.status_code == 200
        assert len(hist.json()) == 1
        assert hist.json()[0]["sensor_type"] == "ph"

    def test_push_config_invalid_sensor_type_rejected(self, client, auth_headers, registered_device):
        with mock_mqtt_publish():
            resp = client.post(
                f"/api/devices/{registered_device['device_id']}/config",
                json={"sensor_type": "INVALID", "freq": 1, "time1": "10:00"},
                headers=auth_headers,
            )
        assert resp.status_code == 422

    def test_push_config_nonexistent_device_returns_404(self, client, auth_headers):
        with mock_mqtt_publish():
            resp = client.post("/api/devices/GHOST001/config",
                              json={"sensor_type": "moisture", "freq": 1, "time1": "10:00"},
                              headers=auth_headers)
        assert resp.status_code == 404


# ─────────────────────────────────────────────────────────────────────────────
# GET /api/devices/{device_id}/configs  (history)
# ─────────────────────────────────────────────────────────────────────────────

class TestConfigHistory:
    def test_empty_history_initially(self, client, auth_headers, registered_device):
        resp = client.get(f"/api/devices/{registered_device['device_id']}/configs",
                         headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json() == []

    def test_multiple_configs_ordered_newest_first(self, client, auth_headers, registered_device):
        with mock_mqtt_publish():
            for sensor in ["moisture", "temperature", "humidity"]:
                client.post(f"/api/devices/{registered_device['device_id']}/config",
                           json={"sensor_type": sensor, "freq": 1, "time1": "10:00"},
                           headers=auth_headers)
        hist = client.get(f"/api/devices/{registered_device['device_id']}/configs",
                         headers=auth_headers).json()
        assert len(hist) == 3
        # Newest config (version 3) should be first
        assert hist[0]["cfg_version"] == 3
        assert hist[-1]["cfg_version"] == 1


# ─────────────────────────────────────────────────────────────────────────────
# DELETE /api/devices/{device_id}
# ─────────────────────────────────────────────────────────────────────────────

class TestDeleteDevice:
    def test_delete_device_success(self, client, auth_headers):
        register_device(client, auth_headers, device_id="DEL001")
        resp = client.delete("/api/devices/DEL001", headers=auth_headers)
        assert resp.status_code == 204

    def test_deleted_device_not_in_list(self, client, auth_headers):
        register_device(client, auth_headers, device_id="DEL002")
        client.delete("/api/devices/DEL002", headers=auth_headers)
        devices = client.get("/api/devices", headers=auth_headers).json()
        assert not any(d["device_id"] == "DEL002" for d in devices)

    def test_delete_nonexistent_device_returns_404(self, client, auth_headers):
        resp = client.delete("/api/devices/GHOST_DEL", headers=auth_headers)
        assert resp.status_code == 404

    def test_cannot_delete_other_users_device(self, client, auth_headers):
        register_device(client, auth_headers, device_id="OWNED_DEV")
        # User B tries to delete it
        client.post("/api/auth/register", json={
            "username": "intruder",
            "email":    "intruder@test.io",
            "password": "IntruderPass123!",
            "full_name": "Intruder",
        })
        login = client.post("/api/auth/login",
                           json={"email": "intruder@test.io", "password": "IntruderPass123!"})
        headers_intruder = {"Authorization": f"Bearer {login.json()['access_token']}"}
        resp = client.delete("/api/devices/OWNED_DEV", headers=headers_intruder)
        assert resp.status_code == 404   # returns 404 (not 403) for security — don't reveal existence
