"""
Unit tests for MQTT message parsing — mqtt_handler._parse_telemetry()
and the helper functions _mv_to_pct, _rssi_label from models_device.

These tests require NO database, NO network, NO MQTT broker.
They run in < 0.1 seconds.

Run:
    pytest tests/test_unit_parsing.py -v
"""

import json
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from datetime import datetime, timezone

# Import the functions under test directly
from mqtt_handler import _parse_telemetry, _parse_config_ack
from models_device import _mv_to_pct, _rssi_label, SENSOR_TYPE_MAP


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def make_payload(**overrides) -> str:
    """Build a minimal valid telemetry JSON payload string."""
    base = {
        "t":   "SNR001",
        "ts":  1749570780,      # 2025-06-10 10:33:00 UTC
        "s":   1,               # moisture
        "v":   {"m": 456},      # 45.6%
        "b":   372,             # battery raw → 3720 mV
        "r":   -71,             # rssi
        "a":   1,
        "mid": "abc123",
    }
    base.update(overrides)
    return json.dumps(base)

TOPIC_PARTS = ["chandigarh", "SNR001"]


# ─────────────────────────────────────────────────────────────────────────────
# _parse_telemetry — Happy path
# ─────────────────────────────────────────────────────────────────────────────

class TestParseTelemetryHappyPath:
    def test_returns_dict(self):
        result = _parse_telemetry(TOPIC_PARTS, make_payload())
        assert isinstance(result, dict)

    def test_location_extracted_from_topic(self):
        result = _parse_telemetry(TOPIC_PARTS, make_payload())
        assert result["location"] == "chandigarh"

    def test_device_id_extracted_from_topic(self):
        result = _parse_telemetry(TOPIC_PARTS, make_payload())
        assert result["device_id"] == "SNR001"

    def test_moisture_reading_divided_by_10(self):
        """v: {m: 456} → moisture = 45.6"""
        result = _parse_telemetry(TOPIC_PARTS, make_payload())
        assert result["standard"]["moisture"] == 45.6

    def test_humidity_reading_divided_by_10(self):
        payload = make_payload(v={"h": 650})
        result = _parse_telemetry(TOPIC_PARTS, payload)
        assert result["standard"]["humidity"] == 65.0

    def test_temperature_reading_key_tp(self):
        """Firmware uses 'tp' not 't' to avoid clash with transmitter ID."""
        payload = make_payload(v={"tp": 285})
        result = _parse_telemetry(TOPIC_PARTS, payload)
        assert result["standard"]["temperature"] == 28.5

    def test_multiple_standard_readings(self):
        payload = make_payload(v={"m": 400, "h": 600, "tp": 250})
        result = _parse_telemetry(TOPIC_PARTS, payload)
        assert result["standard"]["moisture"]    == 40.0
        assert result["standard"]["humidity"]    == 60.0
        assert result["standard"]["temperature"] == 25.0

    def test_battery_mv_calculation(self):
        """b=372 → battery_mv = 372 × 10 = 3720 mV"""
        result = _parse_telemetry(TOPIC_PARTS, make_payload())
        assert result["battery_mv"] == 3720

    def test_battery_voltage_from_mv(self):
        """3720 mV → 3.72 V"""
        result = _parse_telemetry(TOPIC_PARTS, make_payload())
        assert abs(result["battery_v"] - 3.72) < 0.001

    def test_rssi_dbm_extracted(self):
        result = _parse_telemetry(TOPIC_PARTS, make_payload())
        assert result["rssi_dbm"] == -71

    def test_msg_id_extracted(self):
        result = _parse_telemetry(TOPIC_PARTS, make_payload())
        assert result["msg_id"] == "abc123"

    def test_timestamp_is_datetime(self):
        result = _parse_telemetry(TOPIC_PARTS, make_payload())
        assert isinstance(result["timestamp"], datetime)

    def test_timestamp_correct_utc_value(self):
        """ts=1749570780 should parse to 2025-06-10 10:33:00 UTC (timezone-naive)."""
        result = _parse_telemetry(TOPIC_PARTS, make_payload())
        # Convert back to UTC epoch to verify correctness
        epoch = result["timestamp"].replace(tzinfo=timezone.utc).timestamp()
        assert abs(epoch - 1749570780) < 1  # within 1 second

    def test_sensor_type_code_1_is_moisture(self):
        result = _parse_telemetry(TOPIC_PARTS, make_payload(s=1))
        assert result["sensor_type"] == "moisture"

    def test_sensor_type_code_2_is_temperature(self):
        result = _parse_telemetry(TOPIC_PARTS, make_payload(s=2))
        assert result["sensor_type"] == "temperature"

    def test_sensor_type_code_3_is_npk(self):
        result = _parse_telemetry(TOPIC_PARTS, make_payload(s=3))
        assert result["sensor_type"] == "npk"

    def test_all_sensor_type_codes_present(self):
        """SENSOR_TYPE_MAP must cover codes 01–06."""
        expected = {"01", "02", "03", "04", "05", "06"}
        assert expected.issubset(set(SENSOR_TYPE_MAP.keys()))

    def test_extra_measurements_go_to_extra_dict(self):
        """NPK keys (n, p, k) are not standard columns → go to extra{}."""
        payload = make_payload(v={"n": 120, "p": 85, "k": 200})
        result = _parse_telemetry(TOPIC_PARTS, payload)
        assert "n" in result["extra"]
        assert "p" in result["extra"]
        assert "k" in result["extra"]
        # Should NOT be in standard cols
        assert "n" not in result["standard"]

    def test_trigger_defaults_to_schedule(self):
        result = _parse_telemetry(TOPIC_PARTS, make_payload())
        assert result["trigger"] == "schedule"

    def test_trigger_manual_when_set(self):
        payload = make_payload(trigger="manual")
        result = _parse_telemetry(TOPIC_PARTS, payload)
        assert result["trigger"] == "manual"


# ─────────────────────────────────────────────────────────────────────────────
# _parse_telemetry — LoRa gateway architecture (new fields)
# ─────────────────────────────────────────────────────────────────────────────

class TestParseTelemetryLoRaFields:
    def test_lora_rssi_extracted_when_present(self):
        """Gateway includes 'lr' key for LoRa radio signal node↔gateway."""
        payload = make_payload(lr=-85)
        result = _parse_telemetry(TOPIC_PARTS, payload)
        assert result["lora_rssi"] == -85

    def test_lora_rssi_is_none_when_absent(self):
        """Direct eSIM nodes don't include 'lr' → lora_rssi = None."""
        result = _parse_telemetry(TOPIC_PARTS, make_payload())
        assert result["lora_rssi"] is None

    def test_lora_rssi_independent_of_rssi_dbm(self):
        """LoRa RSSI (node↔gateway) is separate from GSM RSSI (gateway↔cloud)."""
        payload = make_payload(r=-70, lr=-95)
        result = _parse_telemetry(TOPIC_PARTS, payload)
        assert result["rssi_dbm"]  == -70
        assert result["lora_rssi"] == -95


# ─────────────────────────────────────────────────────────────────────────────
# _parse_telemetry — Error / edge cases
# ─────────────────────────────────────────────────────────────────────────────

class TestParseTelemetryErrors:
    def test_invalid_json_returns_none(self):
        result = _parse_telemetry(TOPIC_PARTS, "not-json{{{")
        assert result is None

    def test_empty_string_returns_none(self):
        result = _parse_telemetry(TOPIC_PARTS, "")
        assert result is None

    def test_topic_too_short_returns_none(self):
        """Topic must have at least [location, device_id]."""
        result = _parse_telemetry(["only_one"], make_payload())
        assert result is None

    def test_missing_battery_gives_none(self):
        payload = json.dumps({"t": "SNR001", "ts": 1749570780, "s": 1, "v": {"m": 400}})
        result = _parse_telemetry(TOPIC_PARTS, payload)
        assert result["battery_mv"] is None
        assert result["battery_v"]  is None

    def test_missing_rssi_gives_none(self):
        payload = json.dumps({"t": "SNR001", "ts": 1749570780, "s": 1, "v": {}})
        result = _parse_telemetry(TOPIC_PARTS, payload)
        assert result["rssi_dbm"] is None

    def test_missing_timestamp_uses_utcnow(self):
        payload = json.dumps({"s": 1, "v": {"m": 400}})
        result = _parse_telemetry(TOPIC_PARTS, payload)
        # Should return a datetime close to now (within 5 seconds)
        assert result is not None
        diff = abs((datetime.utcnow() - result["timestamp"]).total_seconds())
        assert diff < 5, f"Timestamp too far from now: {diff}s"

    def test_zero_battery_gives_none_voltage(self):
        """b=0 edge case: battery_mv=0, battery_v=None (avoid divide-by-zero display)."""
        payload = make_payload(b=0)
        result = _parse_telemetry(TOPIC_PARTS, payload)
        # b=0 → battery_mv_raw=0, *10=0, battery_v=None (falsy check in code)
        assert result["battery_mv"] == 0
        assert result["battery_v"]  is None


# ─────────────────────────────────────────────────────────────────────────────
# _parse_config_ack
# ─────────────────────────────────────────────────────────────────────────────

class TestParseConfigAck:
    def test_valid_ack_returns_dict(self):
        raw = json.dumps({"cfg_ver": 3})
        result = _parse_config_ack(["chandigarh", "SNR001", "config", "ack"], raw)
        assert isinstance(result, dict)
        assert result["cfg_ver"] == 3

    def test_invalid_json_returns_none(self):
        result = _parse_config_ack(["chandigarh", "SNR001", "config", "ack"], "bad")
        assert result is None


# ─────────────────────────────────────────────────────────────────────────────
# Helper functions
# ─────────────────────────────────────────────────────────────────────────────

class TestBatteryPercentHelper:
    """
    Tests for _mv_to_pct — battery millivolt → percentage conversion.

    Actual formula: pct = int((mv - 3000) / 12), clamped to [0, 100].
    So: 3000 mV = 0%, 4200 mV = 100%, range = 1200 mV.
    """

    def test_full_battery_4200mv(self):
        # (4200-3000)/12 = 100
        assert _mv_to_pct(4200) == 100

    def test_min_voltage_3000mv_is_0pct(self):
        # (3000-3000)/12 = 0
        assert _mv_to_pct(3000) == 0

    def test_3300mv_is_25pct(self):
        # (3300-3000)/12 = 25
        assert _mv_to_pct(3300) == 25

    def test_half_battery_3600mv(self):
        # (3600-3000)/12 = 50
        assert _mv_to_pct(3600) == 50

    def test_none_input_returns_none(self):
        assert _mv_to_pct(None) is None

    def test_above_full_clamped_to_100(self):
        """Overvoltage reading should not exceed 100%."""
        pct = _mv_to_pct(4500)
        assert pct <= 100

    def test_below_min_clamped_to_0(self):
        """Undervoltage reading should not go below 0%."""
        pct = _mv_to_pct(2800)
        assert pct >= 0


class TestRSSILabelHelper:
    """
    Tests for _rssi_label — RSSI dBm → signal quality label.

    Actual thresholds:
      >= -70  → "excellent"
      >= -85  → "good"
      >= -100 → "fair"
      < -100  → "poor"
      None    → "unknown"
    """

    def test_excellent_signal_strong(self):
        # -50 >= -70 → excellent
        assert _rssi_label(-50) == "excellent"

    def test_excellent_signal_at_threshold(self):
        # exactly -70 → excellent (>= -70)
        assert _rssi_label(-70) == "excellent"

    def test_good_signal(self):
        # -71 → not excellent, >= -85 → good
        assert _rssi_label(-71) == "good"

    def test_good_signal_at_threshold(self):
        # exactly -85 → good (>= -85)
        assert _rssi_label(-85) == "good"

    def test_fair_signal(self):
        # -86 → not good, >= -100 → fair
        assert _rssi_label(-86) == "fair"

    def test_fair_signal_at_threshold(self):
        # exactly -100 → fair (>= -100)
        assert _rssi_label(-100) == "fair"

    def test_poor_signal(self):
        # -101 → below all thresholds → poor
        assert _rssi_label(-101) == "poor"

    def test_none_input_returns_unknown(self):
        """_rssi_label returns 'unknown' for None (not None object)."""
        assert _rssi_label(None) == "unknown"

    def test_boundary_values_are_consistent(self):
        """Ensure boundaries don't produce KeyError or crash."""
        for rssi in [-30, -60, -70, -71, -85, -86, -100, -101, -120]:
            label = _rssi_label(rssi)
            assert label in {"excellent", "good", "fair", "poor"}, \
                f"Unexpected label '{label}' for rssi={rssi}"
