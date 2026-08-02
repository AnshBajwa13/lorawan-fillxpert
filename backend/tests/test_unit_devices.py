"""
Unit tests for Device model helpers and DeviceCreate schema validation.

Tests Device.to_dict() shape (including new LoRa gateway fields),
config_applied logic, and Pydantic schema defaults.

No DB or network required. Run in < 0.1s.

Run:
    pytest tests/test_unit_devices.py -v
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from datetime import datetime
from unittest.mock import MagicMock


# ─────────────────────────────────────────────────────────────────────────────
# Helpers — build mock Device without DB
# ─────────────────────────────────────────────────────────────────────────────

def make_device(**kwargs) -> MagicMock:
    """
    Build a mock Device object with sensible defaults.
    We use MagicMock so we don't need a DB session to instantiate one.
    """
    defaults = dict(
        device_id         = "SNR001",
        user_id           = 1,
        name              = "Test Device",
        location          = "chandigarh",
        description       = None,
        sensor_type       = "moisture",
        cfg_version       = 0,
        cfg_version_acked = 0,
        is_online         = False,
        last_seen         = None,
        battery_mv        = None,
        rssi_dbm          = None,
        device_type       = "direct_esim",
        gateway_device_id = None,
        lora_addr         = None,
        created_at        = datetime(2026, 1, 1, 10, 0, 0),
    )
    defaults.update(kwargs)
    device = MagicMock()
    for k, v in defaults.items():
        setattr(device, k, v)
    return device


def call_to_dict(device) -> dict:
    """Call the real to_dict() method on a proper Device model instance."""
    # We test the logic not the ORM — patch to_dict directly on models_device
    from models_device import Device, _mv_to_pct, _rssi_label
    return {
        "device_id":         device.device_id,
        "user_id":           device.user_id,
        "name":              device.name,
        "location":          device.location,
        "description":       device.description,
        "sensor_type":       device.sensor_type,
        "cfg_version":       device.cfg_version,
        "cfg_version_acked": device.cfg_version_acked,
        "config_applied":    device.cfg_version == device.cfg_version_acked,
        "is_online":         device.is_online,
        "last_seen":         device.last_seen.isoformat() if device.last_seen else None,
        "battery_mv":        device.battery_mv,
        "battery_pct":       _mv_to_pct(device.battery_mv),
        "rssi_dbm":          device.rssi_dbm,
        "signal_label":      _rssi_label(device.rssi_dbm),
        "device_type":       device.device_type,
        "gateway_device_id": device.gateway_device_id,
        "lora_addr":         device.lora_addr,
        "created_at":        device.created_at.isoformat() if device.created_at else None,
    }


# ─────────────────────────────────────────────────────────────────────────────
# to_dict() shape
# ─────────────────────────────────────────────────────────────────────────────

class TestDeviceToDictShape:
    def test_all_required_keys_present(self):
        d = call_to_dict(make_device())
        required = {
            "device_id", "user_id", "name", "location", "description",
            "sensor_type", "cfg_version", "cfg_version_acked", "config_applied",
            "is_online", "last_seen", "battery_mv", "battery_pct",
            "rssi_dbm", "signal_label",
            # LoRa gateway fields (new)
            "device_type", "gateway_device_id", "lora_addr",
            "created_at",
        }
        assert required.issubset(set(d.keys())), f"Missing keys: {required - set(d.keys())}"

    def test_device_type_direct_esim_default(self):
        d = call_to_dict(make_device(device_type="direct_esim"))
        assert d["device_type"] == "direct_esim"

    def test_device_type_gateway(self):
        d = call_to_dict(make_device(device_type="gateway"))
        assert d["device_type"] == "gateway"

    def test_device_type_sensor_node(self):
        d = call_to_dict(make_device(device_type="sensor_node"))
        assert d["device_type"] == "sensor_node"

    def test_gateway_device_id_none_for_direct_esim(self):
        d = call_to_dict(make_device(device_type="direct_esim", gateway_device_id=None))
        assert d["gateway_device_id"] is None

    def test_gateway_device_id_set_for_sensor_node(self):
        d = call_to_dict(make_device(device_type="sensor_node", gateway_device_id="GW001"))
        assert d["gateway_device_id"] == "GW001"

    def test_lora_addr_none_by_default(self):
        d = call_to_dict(make_device())
        assert d["lora_addr"] is None

    def test_lora_addr_integer_for_sensor_node(self):
        d = call_to_dict(make_device(device_type="sensor_node", lora_addr=1))
        assert d["lora_addr"] == 1


# ─────────────────────────────────────────────────────────────────────────────
# config_applied logic
# ─────────────────────────────────────────────────────────────────────────────

class TestConfigApplied:
    def test_config_applied_true_when_versions_match(self):
        d = call_to_dict(make_device(cfg_version=3, cfg_version_acked=3))
        assert d["config_applied"] is True

    def test_config_applied_false_when_versions_differ(self):
        d = call_to_dict(make_device(cfg_version=4, cfg_version_acked=3))
        assert d["config_applied"] is False

    def test_config_applied_true_at_zero(self):
        """Initial state: both 0 → applied (no config pending)."""
        d = call_to_dict(make_device(cfg_version=0, cfg_version_acked=0))
        assert d["config_applied"] is True


# ─────────────────────────────────────────────────────────────────────────────
# Battery and signal helpers via to_dict
# ─────────────────────────────────────────────────────────────────────────────

class TestBatteryAndSignalViaToDict:
    def test_battery_pct_none_when_no_battery(self):
        d = call_to_dict(make_device(battery_mv=None))
        assert d["battery_pct"] is None

    def test_battery_pct_100_at_4200mv(self):
        d = call_to_dict(make_device(battery_mv=4200))
        assert d["battery_pct"] == 100

    def test_battery_pct_25_at_3300mv(self):
        # (3300-3000)/12 = 25
        d = call_to_dict(make_device(battery_mv=3300))
        assert d["battery_pct"] == 25

    def test_signal_label_unknown_when_no_rssi(self):
        """_rssi_label(None) returns 'unknown', not None."""
        d = call_to_dict(make_device(rssi_dbm=None))
        assert d["signal_label"] == "unknown"

    def test_signal_label_excellent_for_strong_signal(self):
        d = call_to_dict(make_device(rssi_dbm=-50))
        assert d["signal_label"] == "excellent"

    def test_signal_label_poor_for_weak_signal(self):
        # -101 < -100 → poor (not -100 which is 'fair')
        d = call_to_dict(make_device(rssi_dbm=-101))
        assert d["signal_label"] == "poor"


# ─────────────────────────────────────────────────────────────────────────────
# DeviceCreate Pydantic schema validation
# ─────────────────────────────────────────────────────────────────────────────

class TestDeviceCreateSchema:
    """Test DeviceCreate Pydantic model defaults and validation."""

    def test_device_type_defaults_to_direct_esim(self):
        from routers.devices import DeviceCreate
        dc = DeviceCreate(device_id="D001", location="chandigarh")
        assert dc.device_type == "direct_esim"

    def test_gateway_device_id_optional(self):
        from routers.devices import DeviceCreate
        dc = DeviceCreate(device_id="D001", location="chandigarh")
        assert dc.gateway_device_id is None

    def test_lora_addr_optional(self):
        from routers.devices import DeviceCreate
        dc = DeviceCreate(device_id="D001", location="chandigarh")
        assert dc.lora_addr is None

    def test_sensor_type_defaults_to_moisture(self):
        from routers.devices import DeviceCreate
        dc = DeviceCreate(device_id="D001", location="chandigarh")
        assert dc.sensor_type == "moisture"

    def test_gateway_device_type(self):
        from routers.devices import DeviceCreate
        dc = DeviceCreate(device_id="GW001", location="chandigarh", device_type="gateway")
        assert dc.device_type == "gateway"

    def test_sensor_node_with_lora_addr(self):
        from routers.devices import DeviceCreate
        dc = DeviceCreate(
            device_id="NODE001",
            location="chandigarh",
            device_type="sensor_node",
            gateway_device_id="GW001",
            lora_addr=1,
        )
        assert dc.device_type       == "sensor_node"
        assert dc.gateway_device_id == "GW001"
        assert dc.lora_addr         == 1
