"""
MQTT Handler — async subscriber running alongside FastAPI.

Connects to Mosquitto broker on the Oracle server.
Subscribes to all device topics using MQTT wildcards.
On message: validates payload → saves to DB → updates device status
            → broadcasts to all open browser WebSocket connections.

Topic schema agreed with firmware:
  {location}/{device_id}/telemetry    — sensor readings (device → server)
  {location}/{device_id}/config/ack  — device confirms config applied
  {location}/{device_id}/status      — online/offline (LWT)
"""

import asyncio
import json
import logging
from datetime import datetime, timezone

import aiomqtt

from config import get_settings
from database import SessionLocal
from models import SensorReading
from models_device import (
    Device, DeviceConfig,
    SENSOR_TYPE_MAP,
    _mv_to_pct, _rssi_label,
)
from websocket_manager import ws_manager

logger = logging.getLogger("mqtt_handler")

# ---------------------------------------------------------------------------
# Sensor value short-key mapping (inside v:{} from firmware)
# ---------------------------------------------------------------------------
# Values in v{} are integers × 10  (e.g. m:456 = 45.6% moisture)
# Standard columns get the float value; everything else goes to measurements{}
STANDARD_V_KEYS = {
    "m":  "moisture",      # moisture
    "h":  "humidity",      # humidity
    "tp": "temperature",   # temperature ('tp' not 't' to avoid clash with transmitter id)
}


# ---------------------------------------------------------------------------
# Message parsers
# ---------------------------------------------------------------------------
def _parse_telemetry(topic_parts: list[str], raw: str) -> dict | None:
    """
    Parse a telemetry MQTT message.

    Expected topic: {location}/{device_id}/telemetry
    Expected payload (JSON):
        {
            "t":  "SNR001",     transmitter id (same as device_id)
            "ts": 1749570780,   unix timestamp (when reading was TAKEN)
            "s":  1,            sensor type code (int or str)
            "v":  {"m": 456},   readings  (int × 10)
            "b":  372,          battery mV (int × 10 → actual 3720 mV → 3.72 V)
            "r":  -71,          RSSI dBm
            "a":  1,            attempt count
            "mid": "a3f9b2c1"   message id for dedup (optional)
        }

    Returns None on any parse error.
    """
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        logger.warning("Telemetry: invalid JSON from topic %s", "/".join(topic_parts))
        return None

    if len(topic_parts) < 2:
        return None

    location  = topic_parts[0]
    device_id = topic_parts[1]

    # Sensor type: int or string code → name
    s_raw = str(payload.get("s", "1")).zfill(2)
    sensor_type = SENSOR_TYPE_MAP.get(s_raw, "unknown")

    # Readings dict — divide each int value by 10 to get float
    v_raw: dict = payload.get("v", {})
    standard_cols = {}
    extra_measurements = {}

    for key, int_val in v_raw.items():
        float_val = round(int_val / 10, 2) if isinstance(int_val, (int, float)) else int_val
        col_name = STANDARD_V_KEYS.get(key)
        if col_name:
            standard_cols[col_name] = float_val
        else:
            # For NPK keys (n, p, k), ph, etc. — store in measurements{}
            extra_measurements[key] = float_val

    # Battery: stored as int×10 in mV
    # e.g. b=372 → 3720 mV → 3.72 V
    battery_mv_raw = payload.get("b")
    battery_mv     = battery_mv_raw * 10 if battery_mv_raw is not None else None
    battery_v      = battery_mv / 1000.0 if battery_mv else None  # voltage for existing column

    ts_unix = payload.get("ts")
    timestamp = (datetime.fromtimestamp(ts_unix, tz=timezone.utc).replace(tzinfo=None)
                 if ts_unix else datetime.utcnow())

    return {
        "location":    location,
        "device_id":   device_id,
        "sensor_type": sensor_type,
        "timestamp":   timestamp,
        "standard":    standard_cols,       # moisture, humidity, temperature
        "extra":       extra_measurements,  # npk, ph, etc. → measurements JSON
        "battery_mv":  battery_mv,
        "battery_v":   battery_v,
        "rssi_dbm":    payload.get("r"),
        "trigger":     payload.get("trigger", "schedule"),
        "attempts":    payload.get("a", 1),
        "msg_id":      payload.get("mid"),
        "cfg_ver":     payload.get("cfg_ver"),
    }


def _parse_config_ack(topic_parts: list[str], raw: str) -> dict | None:
    """
    Parse a config/ack message.
    Expected payload: {"cfg_ver": 3, "device_id": "SNR001"}
    """
    try:
        payload = json.loads(raw)
        return {
            "device_id": topic_parts[1] if len(topic_parts) >= 2 else None,
            "cfg_ver":   payload.get("cfg_ver"),
        }
    except Exception:
        return None


def _parse_status(topic_parts: list[str], raw: str) -> dict | None:
    """
    Parse a status/LWT message.
    Expected payload: {"status": "online"/"offline", "ts": 1234567890}
    """
    try:
        payload = json.loads(raw)
        return {
            "device_id": topic_parts[1] if len(topic_parts) >= 2 else None,
            "status":    payload.get("status", "online"),
        }
    except Exception:
        return None


# ---------------------------------------------------------------------------
# DB writers
# ---------------------------------------------------------------------------
def _save_telemetry(data: dict) -> SensorReading | None:
    """Write telemetry to sensor_readings table. Returns None on dup/error."""
    db = SessionLocal()
    try:
        # 1. Look up device to get user_id
        device = db.query(Device).filter(Device.device_id == data["device_id"]).first()
        if not device:
            logger.warning("Unknown device '%s' — not registered in dashboard. Skipping.",
                           data["device_id"])
            return None

        # 2. Duplicate detection by msg_id
        if data.get("msg_id"):
            existing = db.query(SensorReading).filter(
                SensorReading.msg_id == data["msg_id"]
            ).first()
            if existing:
                logger.debug("Duplicate msg_id %s — skipping.", data["msg_id"])
                return None

        # 3. Build measurements dict (all non-standard sensor values)
        measurements = data["extra"] if data["extra"] else None
        # Add sensor_type and signal info to measurements for dashboard display
        if measurements is None:
            measurements = {}
        measurements["sensor_type"] = data["sensor_type"]

        # 4. Build SensorReading row
        reading = SensorReading(
            user_id         = device.user_id,
            gateway_id      = data["location"],   # location as gateway_id
            node_id         = data["device_id"],  # device_id as node_id
            timestamp       = data["timestamp"],
            moisture        = data["standard"].get("moisture"),
            humidity        = data["standard"].get("humidity"),
            temperature     = data["standard"].get("temperature"),
            battery_voltage = data.get("battery_v"),
            measurements    = measurements,
            # New columns (will exist after migration)
            msg_id          = data.get("msg_id"),
            rssi_dbm        = data.get("rssi_dbm"),
            trigger         = data.get("trigger"),
            cfg_ver         = data.get("cfg_ver"),
        )
        db.add(reading)
        db.commit()
        db.refresh(reading)
        return reading

    except Exception as e:
        db.rollback()
        logger.error("DB error saving telemetry: %s", e)
        return None
    finally:
        db.close()


def _update_device_status(device_id: str, data: dict):
    """Update device.last_seen, battery, rssi, is_online from telemetry data."""
    db = SessionLocal()
    try:
        device = db.query(Device).filter(Device.device_id == device_id).first()
        if not device:
            return
        device.is_online  = True
        device.last_seen  = datetime.utcnow()
        if data.get("battery_mv") is not None:
            device.battery_mv = data["battery_mv"]
        if data.get("rssi_dbm") is not None:
            device.rssi_dbm = data["rssi_dbm"]
        if data.get("cfg_ver") is not None:
            device.cfg_version = max(device.cfg_version or 0, data["cfg_ver"])
        db.commit()
    except Exception as e:
        db.rollback()
        logger.error("DB error updating device status: %s", e)
    finally:
        db.close()


def _handle_config_ack(device_id: str, cfg_ver: int):
    """Mark device as having applied the config version."""
    db = SessionLocal()
    try:
        device = db.query(Device).filter(Device.device_id == device_id).first()
        if device:
            device.cfg_version_acked = cfg_ver
            db.commit()

        # Mark the DeviceConfig row as acked
        config_row = (db.query(DeviceConfig)
                        .filter(DeviceConfig.device_id == device_id,
                                DeviceConfig.cfg_version == cfg_ver)
                        .first())
        if config_row:
            config_row.ack_received = True
            config_row.ack_at = datetime.utcnow()
            db.commit()

        logger.info("Device %s ACK'd config v%d", device_id, cfg_ver)
    except Exception as e:
        db.rollback()
        logger.error("DB error handling config ack: %s", e)
    finally:
        db.close()


def _handle_status(device_id: str, status: str):
    """Update device online/offline from LWT or status message."""
    db = SessionLocal()
    try:
        device = db.query(Device).filter(Device.device_id == device_id).first()
        if device:
            device.is_online = (status == "online")
            if status == "online":
                device.last_seen = datetime.utcnow()
            db.commit()
    except Exception as e:
        db.rollback()
        logger.error("DB error updating device online status: %s", e)
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Main async MQTT loop — runs as a background task in FastAPI lifespan
# ---------------------------------------------------------------------------
async def run(settings):
    """
    Infinite loop: connect → subscribe → handle messages → reconnect on error.
    Uses aiomqtt which is fully async and integrates cleanly with FastAPI.
    """
    reconnect_interval = settings.MQTT_RECONNECT_INTERVAL

    while True:
        try:
            logger.info(
                "Connecting to MQTT broker %s:%d ...",
                settings.MQTT_BROKER_HOST,
                settings.MQTT_BROKER_PORT,
            )

            async with aiomqtt.Client(
                hostname  = settings.MQTT_BROKER_HOST,
                port      = settings.MQTT_BROKER_PORT,
                username  = settings.MQTT_USERNAME,
                password  = settings.MQTT_PASSWORD,
                identifier= settings.MQTT_CLIENT_ID,
                keepalive = 60,
            ) as client:

                # Subscribe to all device topics (wildcard: + matches one level)
                # Catches: sangrur/SNR001/telemetry, punjab/SNR002/telemetry, etc.
                await client.subscribe("+/+/telemetry",   qos=1)
                await client.subscribe("+/+/config/ack",  qos=1)
                await client.subscribe("+/+/status",      qos=1)

                logger.info("MQTT connected. Subscribed to +/+/telemetry, /config/ack, /status")

                async for message in client.messages:
                    topic_str   = str(message.topic)
                    topic_parts = topic_str.split("/")
                    payload_str = message.payload.decode("utf-8", errors="replace")

                    await _dispatch(topic_parts, payload_str)

        except aiomqtt.MqttError as e:
            logger.warning(
                "MQTT connection lost: %s — reconnecting in %ds...",
                e, reconnect_interval
            )
            await asyncio.sleep(reconnect_interval)
        except asyncio.CancelledError:
            logger.info("MQTT handler cancelled — shutting down.")
            break
        except Exception as e:
            logger.error("Unexpected MQTT error: %s — reconnecting in %ds...",
                         e, reconnect_interval)
            await asyncio.sleep(reconnect_interval)


async def _dispatch(topic_parts: list[str], payload_str: str):
    """Route incoming MQTT message to correct handler based on topic suffix."""
    if len(topic_parts) < 3:
        return

    suffix = topic_parts[-1]

    # ── Telemetry: {location}/{device_id}/telemetry ──
    if suffix == "telemetry":
        data = _parse_telemetry(topic_parts, payload_str)
        if not data:
            return

        # Save to DB (blocking, run in thread pool to not block event loop)
        loop = asyncio.get_running_loop()
        reading = await loop.run_in_executor(None, _save_telemetry, data)

        # Update device status regardless of whether reading was saved
        await loop.run_in_executor(None, _update_device_status, data["device_id"], data)

        # Broadcast to all open browser WebSocket connections
        ws_payload = {
            "event":      "new_reading",
            "device_id":  data["device_id"],
            "location":   data["location"],
            "sensor_type":data["sensor_type"],
            "timestamp":  data["timestamp"].isoformat() + "Z",
            "readings":   {**data["standard"], **data["extra"]},
            "battery_mv": data.get("battery_mv"),
            "battery_pct":_mv_to_pct(data.get("battery_mv")),
            "rssi_dbm":   data.get("rssi_dbm"),
            "signal":     _rssi_label(data.get("rssi_dbm")),
            "trigger":    data.get("trigger", "schedule"),
            "saved":      reading is not None,
        }
        await ws_manager.broadcast(ws_payload)
        logger.debug("Telemetry from %s saved=%s", data["device_id"], reading is not None)

    # ── Config ACK: {location}/{device_id}/config/ack ──
    elif len(topic_parts) >= 4 and topic_parts[-2] == "config" and suffix == "ack":
        ack = _parse_config_ack(topic_parts, payload_str)
        if ack and ack["device_id"] and ack["cfg_ver"] is not None:
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(None, _handle_config_ack,
                                       ack["device_id"], ack["cfg_ver"])
            await ws_manager.broadcast({
                "event":     "config_acked",
                "device_id": ack["device_id"],
                "cfg_ver":   ack["cfg_ver"],
            })

    # ── Status / LWT: {location}/{device_id}/status ──
    elif suffix == "status":
        st = _parse_status(topic_parts, payload_str)
        if st and st["device_id"]:
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(None, _handle_status,
                                       st["device_id"], st["status"])
            await ws_manager.broadcast({
                "event":     "device_status",
                "device_id": st["device_id"],
                "status":    st["status"],
            })
