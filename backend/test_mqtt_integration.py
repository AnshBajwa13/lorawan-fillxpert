#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════════════════╗
║          FillXpert — MQTT Integration Test Script                           ║
║                                                                              ║
║  What this script tests end-to-end:                                         ║
║                                                                              ║
║  TEST 1 — Telemetry Flow                                                     ║
║    Publishes a fake device payload to: chandigarh/TESTDEV001/telemetry       ║
║    Waits 3s, then verifies the backend processed it by checking:             ║
║    • sensor_readings table has a new row                                     ║
║    • devices table shows TESTDEV001 as Online with battery/rssi              ║
║                                                                              ║
║  TEST 2 — Duplicate Detection                                                ║
║    Publishes the SAME payload again (same msg_id)                            ║
║    Verifies that NO new DB row was created (dedup working)                   ║
║                                                                              ║
║  TEST 3 — Config ACK Flow                                                    ║
║    Publishes a config/ack message: device reports it applied config v1       ║
║    Verifies device.cfg_version_acked updated in DB                           ║
║                                                                              ║
║  TEST 4 — Status / LWT                                                       ║
║    Publishes an offline status message (simulates device going offline)      ║
║    Verifies device.is_online = False in DB                                   ║
║                                                                              ║
║  TEST 5 — WebSocket Live Event                                               ║
║    Connects a WebSocket to the backend                                       ║
║    Publishes a new telemetry (different msg_id)                              ║
║    Verifies the WebSocket received a new_reading event                       ║
║                                                                              ║
║  TEST 6 — Cleanup                                                            ║
║    Removes all test rows from DB (leaves real data intact)                   ║
║                                                                              ║
║  Usage:                                                                      ║
║    From host machine (containers running):                                   ║
║      python test_mqtt_integration.py                                         ║
║    Inside backend container:                                                 ║
║      docker exec -it lorawan_backend python test_mqtt_integration.py        ║
║                                                                              ║
║  Requirements (already in requirements.txt):                                 ║
║    aiomqtt, sqlalchemy, websockets, psycopg2-binary                          ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

import asyncio
import json
import os
import sys
import time
import uuid
from datetime import datetime, timezone

# ─────────────────────────────────────────────────────────────────────────────
# Configuration — all values match docker-compose.yml and config.py defaults
# Change these if your .env overrides them
# ─────────────────────────────────────────────────────────────────────────────
MQTT_HOST   = os.getenv("MQTT_BROKER_HOST", "140.245.7.35")
MQTT_PORT   = int(os.getenv("MQTT_BROKER_PORT", "1883"))
MQTT_USER   = os.getenv("MQTT_USERNAME", None)
MQTT_PASS   = os.getenv("MQTT_PASSWORD", None)

# Database — same credentials as docker-compose.yml
# When running INSIDE a container → host is "postgres"
# When running on your host machine → host is "localhost" port 5433
DB_HOST     = os.getenv("DB_HOST",  "localhost")
DB_PORT     = int(os.getenv("DB_PORT", "5433"))   # 5433 = mapped host port
DB_NAME     = os.getenv("DB_NAME",  "lorawan_db")
DB_USER     = os.getenv("DB_USER",  "lorawan_user")
DB_PASS     = os.getenv("DB_PASS",  "lorawan_pass")

# Backend WebSocket URL (when running on host)
WS_URL      = os.getenv("WS_URL",   "ws://localhost:8000/ws/realtime")

# Test device (must be registered in the dashboard before running this test)
TEST_LOCATION   = "chandigarh"        # MQTT topic level 1
TEST_DEVICE_ID  = "TESTDEV001"        # MQTT topic level 2 — must exist in devices table
TEST_MSG_ID     = f"test-{uuid.uuid4().hex[:8]}"   # unique per test run

# ─────────────────────────────────────────────────────────────────────────────
# Colours for terminal output
# ─────────────────────────────────────────────────────────────────────────────
GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
BLUE   = "\033[94m"
CYAN   = "\033[96m"
BOLD   = "\033[1m"
RESET  = "\033[0m"

PASS = f"{GREEN}[PASS]{RESET}"
FAIL = f"{RED}[FAIL]{RESET}"
INFO = f"{BLUE}[INFO]{RESET}"
WARN = f"{YELLOW}[WARN]{RESET}"
STEP = f"{CYAN}[STEP]{RESET}"

# ─────────────────────────────────────────────────────────────────────────────
# Test result tracker
# ─────────────────────────────────────────────────────────────────────────────
results: list[tuple[str, bool, str]] = []  # (test_name, passed, detail)

def record(name: str, passed: bool, detail: str = ""):
    results.append((name, passed, detail))
    icon = PASS if passed else FAIL
    print(f"  {icon} {name}" + (f" — {detail}" if detail else ""))

# ─────────────────────────────────────────────────────────────────────────────
# Database helpers (direct SQL via psycopg2 — no ORM dependency in test)
# ─────────────────────────────────────────────────────────────────────────────
def get_db_connection():
    """
    Returns a psycopg2 connection.
    We use raw SQL here so the test script has no dependency on the backend
    package structure — it can run standalone.
    """
    try:
        import psycopg2
        conn = psycopg2.connect(
            host     = DB_HOST,
            port     = DB_PORT,
            dbname   = DB_NAME,
            user     = DB_USER,
            password = DB_PASS,
        )
        return conn
    except ImportError:
        print(f"{WARN} psycopg2 not available — DB checks will be skipped")
        print(f"      Install: pip install psycopg2-binary")
        return None
    except Exception as e:
        print(f"{WARN} Cannot connect to DB at {DB_HOST}:{DB_PORT} — {e}")
        print(f"      DB checks will be skipped. Is Docker running?")
        return None


def db_query_one(sql: str, params: tuple = ()) -> dict | None:
    """Execute a SELECT and return the first row as a dict."""
    conn = get_db_connection()
    if not conn:
        return None
    try:
        cur = conn.cursor()
        cur.execute(sql, params)
        cols = [d[0] for d in cur.description]
        row = cur.fetchone()
        return dict(zip(cols, row)) if row else None
    except Exception as e:
        print(f"{WARN} DB query failed: {e}")
        return None
    finally:
        conn.close()


def db_query_count(sql: str, params: tuple = ()) -> int | None:
    """Execute a COUNT query and return the integer result."""
    conn = get_db_connection()
    if not conn:
        return None
    try:
        cur = conn.cursor()
        cur.execute(sql, params)
        return cur.fetchone()[0]
    except Exception as e:
        print(f"{WARN} DB count failed: {e}")
        return None
    finally:
        conn.close()


def db_execute(sql: str, params: tuple = ()):
    """Execute a DML statement (DELETE, UPDATE)."""
    conn = get_db_connection()
    if not conn:
        return
    try:
        cur = conn.cursor()
        cur.execute(sql, params)
        conn.commit()
    except Exception as e:
        print(f"{WARN} DB execute failed: {e}")
    finally:
        conn.close()


# ─────────────────────────────────────────────────────────────────────────────
# MQTT publish helper
# ─────────────────────────────────────────────────────────────────────────────
async def mqtt_publish(topic: str, payload: dict | str, retain: bool = False):
    """
    Open a short-lived MQTT connection, publish one message, disconnect.

    Why a fresh connection per publish?
    — In tests we want each action isolated. The backend's permanent subscriber
      (`mqtt_handler.py`) already holds the long-lived connection. This is the
      same pattern the backend uses in `routers/devices.py` for config push.
    """
    try:
        import aiomqtt
    except ImportError:
        print(f"{RED}[ERROR]{RESET} aiomqtt not installed. Run: pip install aiomqtt")
        sys.exit(1)

    msg = payload if isinstance(payload, str) else json.dumps(payload)
    kwargs = dict(
        hostname = MQTT_HOST,
        port     = MQTT_PORT,
    )
    if MQTT_USER:
        kwargs["username"] = MQTT_USER
        kwargs["password"] = MQTT_PASS

    try:
        async with aiomqtt.Client(**kwargs) as client:
            await client.publish(topic, payload=msg, qos=1, retain=retain)
        print(f"  {INFO} Published → {BOLD}{topic}{RESET}")
        print(f"       Payload: {msg[:120]}{'...' if len(msg) > 120 else ''}")
    except Exception as e:
        print(f"  {RED}[ERROR]{RESET} MQTT publish failed: {e}")
        raise


# ─────────────────────────────────────────────────────────────────────────────
# WebSocket helper
# ─────────────────────────────────────────────────────────────────────────────
async def ws_listen_for_event(event_name: str, timeout: float = 6.0) -> dict | None:
    """
    Connect to /ws/realtime (no auth for test — backend accepts unauthenticated WS).
    Listen for up to `timeout` seconds.
    Returns the first message matching event_name, or None if timed out.

    NOTE: Our backend's WebSocket endpoint at /ws/realtime does NOT currently
    enforce JWT for WebSocket connections — it accepts all connections.
    The `?token=...` in App.js is just future-proofing.
    """
    try:
        import websockets  # type: ignore
    except ImportError:
        print(f"{WARN} websockets package not installed — WS test will be skipped")
        print(f"      Install: pip install websockets")
        return None

    try:
        async with websockets.connect(WS_URL, ping_interval=None) as ws:
            # Wait for messages until timeout or target event found
            deadline = asyncio.get_event_loop().time() + timeout
            while asyncio.get_event_loop().time() < deadline:
                remaining = deadline - asyncio.get_event_loop().time()
                try:
                    raw = await asyncio.wait_for(ws.recv(), timeout=min(1.0, remaining))
                    msg = json.loads(raw)
                    if msg.get("event") == event_name:
                        return msg
                except asyncio.TimeoutError:
                    continue
            return None
    except Exception as e:
        print(f"  {WARN} WebSocket connection failed: {e}")
        print(f"       Is the backend running at {WS_URL.replace('ws://', 'http://'[:-1])}?")
        return None


# ─────────────────────────────────────────────────────────────────────────────
# Pre-flight check: verify TESTDEV001 is registered
# ─────────────────────────────────────────────────────────────────────────────
def preflight_check() -> bool:
    """
    WHY THIS CHECK EXISTS:
    The mqtt_handler skips telemetry if the device isn't in the devices table
    (line 163-167 of mqtt_handler.py: "Unknown device — not registered. Skipping.")

    So before running any tests, we verify TESTDEV001 exists. If not, we print
    exact instructions to register it via the dashboard.
    """
    global TEST_LOCATION   # declared first — Python requires global before any use

    print(f"\n{STEP} Pre-flight: Checking device '{TEST_DEVICE_ID}' is registered...")
    row = db_query_one(
        "SELECT device_id, user_id, location FROM devices WHERE device_id = %s",
        (TEST_DEVICE_ID,)
    )
    if row is None:
        print(f"\n  {RED}[BLOCKED]{RESET} Device '{TEST_DEVICE_ID}' not found in the database.")
        print(f"""
  {YELLOW}Action required:{RESET}
  1. Open the dashboard → Devices page
  2. Click "Register Device"
  3. Fill in:
       Device ID  : {TEST_DEVICE_ID}
       Name       : Test Device 001
       Location   : {TEST_LOCATION}        <- must match MQTT topic prefix exactly
       Sensor Type: moisture
  4. Click Register, then re-run this script.

  {YELLOW}Or run test_setup_auto.py:{RESET}
      python test_setup_auto.py
""")
        return False

    if row["location"] != TEST_LOCATION:
        print(f"  {WARN} Device found but location='{row['location']}' != '{TEST_LOCATION}'")
        print(f"       MQTT topic will be: {row['location']}/{TEST_DEVICE_ID}/telemetry")
        print(f"       Test will use location: {row['location']}")
        TEST_LOCATION = row["location"]   # correct the global

    print(f"  {PASS} Device '{TEST_DEVICE_ID}' found (user_id={row['user_id']}, location='{TEST_LOCATION}')")
    return True


# ─────────────────────────────────────────────────────────────────────────────
# TEST 1 — Full Telemetry Flow
# ─────────────────────────────────────────────────────────────────────────────
async def test_telemetry_flow():
    """
    WHAT IT TESTS:
    This is the primary happy path — a real device waking up and sending data.

    Payload explanation (matches mqtt_handler.py _parse_telemetry):
      t   : transmitter ID (device_id string)
      ts  : unix timestamp of when reading was taken (not when it was sent)
      s   : sensor type code — "01" = moisture (see SENSOR_TYPE_MAP)
      v   : readings dict — keys use short codes, values are int × 10
            "m": 435 → 435/10 = 43.5% soil moisture
            "tp": 287 → 287/10 = 28.7°C temperature
      b   : battery in raw units × 10 → b=375 → 375*10=3750 mV → 3.75V → ~62%
      r   : RSSI in dBm (negative integer) → -68 = "good" signal
      a   : attempt count (how many times device tried to send this reading)
      mid : unique message ID for duplicate detection (hex string)

    VERIFICATION:
    1. Publish the payload
    2. Wait 3 seconds for mqtt_handler to process it
    3. Query sensor_readings table — should have a new row with msg_id = TEST_MSG_ID
    4. Query devices table — should show is_online=True, battery_mv=3750
    """
    print(f"\n{STEP} TEST 1 — Telemetry Flow (moisture + temperature reading)")
    print(f"       Topic: {TEST_LOCATION}/{TEST_DEVICE_ID}/telemetry")

    telemetry_payload = {
        "t":   TEST_DEVICE_ID,
        "ts":  int(time.time()),
        "s":   1,                  # sensor code 01 = moisture
        "v": {
            "m":  435,             # 43.5% soil moisture
            "tp": 287,             # 28.7°C temperature
            "h":  628,             # 62.8% humidity
        },
        "b":   375,                # 375 × 10 = 3750 mV battery
        "r":   -68,                # -68 dBm GSM signal (good)
        "a":   1,                  # first attempt
        "mid": TEST_MSG_ID,        # unique message ID
    }

    await mqtt_publish(
        topic   = f"{TEST_LOCATION}/{TEST_DEVICE_ID}/telemetry",
        payload = telemetry_payload,
    )

    print(f"  {INFO} Waiting 3s for mqtt_handler to process...")
    await asyncio.sleep(3)

    # Check 1: Did the row appear in sensor_readings?
    row = db_query_one(
        "SELECT id, gateway_id, node_id, moisture, temperature, humidity, battery_voltage, rssi_dbm, msg_id "
        "FROM sensor_readings WHERE msg_id = %s",
        (TEST_MSG_ID,)
    )

    if row:
        record(
            "Telemetry saved to DB",
            True,
            f"id={row['id']} | moisture={row['moisture']}% | temp={row['temperature']}°C | battery={row['battery_voltage']}V"
        )
        # Validate values parsed correctly
        record("Moisture parsed correctly",  abs((row['moisture']   or 0) - 43.5) < 0.1, f"got {row['moisture']}")
        record("Temperature parsed correctly",abs((row['temperature'] or 0) - 28.7) < 0.1, f"got {row['temperature']}")
        record("Battery voltage correct",    abs((row['battery_voltage'] or 0) - 3.75) < 0.05, f"got {row['battery_voltage']}V")
    else:
        record("Telemetry saved to DB", False,
               "Row not found — check that backend is running and TESTDEV001 is registered")
        return  # No point checking derived fields if base failed

    # Check 2: Did device status update?
    device = db_query_one(
        "SELECT is_online, battery_mv, rssi_dbm, last_seen FROM devices WHERE device_id = %s",
        (TEST_DEVICE_ID,)
    )
    if device:
        record("Device marked Online",    device['is_online'] is True,   f"is_online={device['is_online']}")
        record("Battery mV updated",      device['battery_mv'] == 3750,  f"battery_mv={device['battery_mv']}")
        record("RSSI updated",            device['rssi_dbm'] == -68,      f"rssi_dbm={device['rssi_dbm']}")
        record("last_seen updated",       device['last_seen'] is not None, f"last_seen={device['last_seen']}")
    else:
        record("Device status updated", False, "Device row not found")


# ─────────────────────────────────────────────────────────────────────────────
# TEST 2 — Duplicate Detection
# ─────────────────────────────────────────────────────────────────────────────
async def test_duplicate_detection():
    """
    WHAT IT TESTS:
    The mqtt_handler has dedup logic (lines 170-176):
      if msg_id already exists in sensor_readings → skip, do not insert.

    This is critical for eSIM/GSM devices which may retry transmissions if the
    first attempt didn't get a TCP ACK from the broker (even though the broker
    received it). Without dedup, you'd get double readings.

    We publish the EXACT SAME payload (same TEST_MSG_ID) a second time.
    The DB count for that msg_id should still be 1 after waiting.
    """
    print(f"\n{STEP} TEST 2 — Duplicate Detection (same msg_id should NOT create new row)")

    count_before = db_query_count(
        "SELECT COUNT(*) FROM sensor_readings WHERE msg_id = %s",
        (TEST_MSG_ID,)
    )
    print(f"  {INFO} DB count before re-publish: {count_before}")

    # Republish identical payload
    telemetry_payload = {
        "t":   TEST_DEVICE_ID,
        "ts":  int(time.time()),
        "s":   1,
        "v":   {"m": 435, "tp": 287},
        "b":   375,
        "r":   -68,
        "a":   2,               # attempt 2 (device retried)
        "mid": TEST_MSG_ID,     # SAME msg_id — must be rejected by dedup
    }
    await mqtt_publish(
        topic   = f"{TEST_LOCATION}/{TEST_DEVICE_ID}/telemetry",
        payload = telemetry_payload,
    )

    print(f"  {INFO} Waiting 3s...")
    await asyncio.sleep(3)

    count_after = db_query_count(
        "SELECT COUNT(*) FROM sensor_readings WHERE msg_id = %s",
        (TEST_MSG_ID,)
    )
    print(f"  {INFO} DB count after re-publish: {count_after}")

    record(
        "Duplicate rejected (dedup working)",
        count_before is not None and count_after == count_before,
        f"count stayed at {count_after} (expected {count_before})"
    )


# ─────────────────────────────────────────────────────────────────────────────
# TEST 3 — Config ACK Flow
# ─────────────────────────────────────────────────────────────────────────────
async def test_config_ack():
    """
    WHAT IT TESTS:
    When you push a config from the dashboard, the device receives it via MQTT
    retained message and replies on the {location}/{device_id}/config/ack topic.

    The mqtt_handler handles this in _handle_config_ack():
    1. Sets device.cfg_version_acked = cfg_ver
    2. Sets device_configs row: ack_received = True, ack_at = now()

    We simulate the device sending ACK for config version 1.
    Then verify device.cfg_version_acked updated.

    NOTE: For this test to show "Applied" on the DeviceConfig page, a config
    must have been pushed first. We only test the DB update here.
    """
    print(f"\n{STEP} TEST 3 — Config ACK (device confirms it applied config)")
    print(f"       Topic: {TEST_LOCATION}/{TEST_DEVICE_ID}/config/ack")

    # Get current cfg_version_acked before test
    device_before = db_query_one(
        "SELECT cfg_version, cfg_version_acked FROM devices WHERE device_id = %s",
        (TEST_DEVICE_ID,)
    )
    current_ver = (device_before['cfg_version'] or 1) if device_before else 1

    ack_payload = {
        "cfg_ver":   current_ver,
        "device_id": TEST_DEVICE_ID,
    }
    await mqtt_publish(
        topic   = f"{TEST_LOCATION}/{TEST_DEVICE_ID}/config/ack",
        payload = ack_payload,
    )

    print(f"  {INFO} Waiting 2s...")
    await asyncio.sleep(2)

    device_after = db_query_one(
        "SELECT cfg_version, cfg_version_acked FROM devices WHERE device_id = %s",
        (TEST_DEVICE_ID,)
    )

    if device_after:
        acked = device_after['cfg_version_acked']
        record(
            "Config ACK saved (cfg_version_acked updated)",
            acked == current_ver,
            f"cfg_version_acked={acked} (expected {current_ver})"
        )
    else:
        record("Config ACK saved", False, "Device row not found")


# ─────────────────────────────────────────────────────────────────────────────
# TEST 4 — Status / LWT (Last Will and Testament)
# ─────────────────────────────────────────────────────────────────────────────
async def test_device_status():
    """
    WHAT IT TESTS:
    MQTT Last Will and Testament (LWT) is a message the broker automatically
    sends when a client disconnects unexpectedly. For our devices, we configure
    the LWT to publish {"status": "offline"} to {location}/{device_id}/status.

    The mqtt_handler handles this in _handle_status():
    - "offline" → device.is_online = False
    - "online"  → device.is_online = True, last_seen = now()

    We simulate:
    1. Device going offline (LWT fires)
    2. Verify DB shows is_online = False
    3. Device coming back online
    4. Verify DB shows is_online = True again
    """
    print(f"\n{STEP} TEST 4 — Device Status / LWT (online ↔ offline toggle)")
    print(f"       Topic: {TEST_LOCATION}/{TEST_DEVICE_ID}/status")

    # Step 4a: Simulate device going OFFLINE (LWT)
    await mqtt_publish(
        topic   = f"{TEST_LOCATION}/{TEST_DEVICE_ID}/status",
        payload = {"status": "offline", "ts": int(time.time())},
    )
    await asyncio.sleep(2)

    device = db_query_one(
        "SELECT is_online FROM devices WHERE device_id = %s", (TEST_DEVICE_ID,)
    )
    record(
        "Device set Offline via LWT",
        device is not None and device['is_online'] is False,
        f"is_online={device['is_online'] if device else 'not found'}"
    )

    # Step 4b: Simulate device coming back ONLINE
    await mqtt_publish(
        topic   = f"{TEST_LOCATION}/{TEST_DEVICE_ID}/status",
        payload = {"status": "online", "ts": int(time.time())},
    )
    await asyncio.sleep(2)

    device = db_query_one(
        "SELECT is_online FROM devices WHERE device_id = %s", (TEST_DEVICE_ID,)
    )
    record(
        "Device set Online via status message",
        device is not None and device['is_online'] is True,
        f"is_online={device['is_online'] if device else 'not found'}"
    )


# ─────────────────────────────────────────────────────────────────────────────
# TEST 5 — WebSocket Live Event
# ─────────────────────────────────────────────────────────────────────────────
async def test_websocket_event():
    """
    WHAT IT TESTS:
    The WebSocket bridge: Device → MQTT → Backend → WebSocket → Browser.

    We connect a WebSocket client to /ws/realtime BEFORE publishing.
    Then publish a new telemetry message (different msg_id to avoid dedup).
    Then verify the WebSocket client received a "new_reading" event.

    This proves the full chain works end-to-end without needing an open browser.

    The event shape we expect (from mqtt_handler.py lines 360-373):
    {
        "event":       "new_reading",
        "device_id":   "TESTDEV001",
        "location":    "chandigarh",
        "sensor_type": "moisture",
        "timestamp":   "2026-06-11T...",
        "readings":    {"moisture": 51.2, "temperature": 27.3},
        "battery_mv":  3750,
        "battery_pct": 62,
        "rssi_dbm":    -71,
        "signal":      "good",
        "trigger":     "schedule",
        "saved":       true
    }
    """
    print(f"\n{STEP} TEST 5 — WebSocket Live Event (MQTT → WS bridge)")
    print(f"       Connecting WebSocket to: {WS_URL}")

    ws2_msg_id = f"ws-test-{uuid.uuid4().hex[:8]}"
    ws_payload = {
        "t":   TEST_DEVICE_ID,
        "ts":  int(time.time()),
        "s":   1,
        "v":   {"m": 512, "tp": 273},  # 51.2% moisture, 27.3°C
        "b":   375,
        "r":   -71,
        "a":   1,
        "mid": ws2_msg_id,             # NEW msg_id — will not be deduped
    }

    # Start WS listener BEFORE publishing (otherwise we miss the event)
    async def publish_after_delay():
        await asyncio.sleep(0.5)
        await mqtt_publish(
            topic   = f"{TEST_LOCATION}/{TEST_DEVICE_ID}/telemetry",
            payload = ws_payload,
        )

    # Run both concurrently: listen for 8s, publish after 0.5s
    listen_task  = asyncio.create_task(ws_listen_for_event("new_reading", timeout=8.0))
    publish_task = asyncio.create_task(publish_after_delay())

    await publish_task
    event = await listen_task

    if event is None:
        record("WebSocket received new_reading event", False,
               "Timed out — check if backend is running at localhost:8000")
    else:
        record("WebSocket received new_reading event",    True,
               f"event.device_id={event.get('device_id')}")
        record("Event device_id matches",                 event.get("device_id") == TEST_DEVICE_ID,
               f"got: {event.get('device_id')}")
        record("Event has readings dict",                 isinstance(event.get("readings"), dict),
               f"readings={event.get('readings')}")
        record("Event has battery_pct",                   event.get("battery_pct") is not None,
               f"battery_pct={event.get('battery_pct')}%")
        record("saved=True (row written to DB)",          event.get("saved") is True,
               f"saved={event.get('saved')}")

        # Clean up the ws test reading too
        db_execute(
            "DELETE FROM sensor_readings WHERE msg_id = %s", (ws2_msg_id,)
        )


# ─────────────────────────────────────────────────────────────────────────────
# TEST 6 — Cleanup
# ─────────────────────────────────────────────────────────────────────────────
async def test_cleanup():
    """
    WHAT IT DOES:
    Removes all test-generated rows from sensor_readings.
    Does NOT touch:
    - The device registration (TESTDEV001 stays, useful for future tests)
    - Real device readings from other devices
    - Any other table

    Leaves the DB in a clean state where only real production data remains.
    """
    print(f"\n{STEP} TEST 6 — Cleanup (removing test rows from DB)")

    # Note: psycopg2 uses %s for params — LIKE patterns need %% for literal %
    # We avoid this by using a prefix search approach
    count = db_query_count(
        "SELECT COUNT(*) FROM sensor_readings WHERE node_id = %s AND msg_id LIKE %s",
        (TEST_DEVICE_ID, "test-%")
    )
    print(f"  {INFO} Found {count} test rows to delete")

    db_execute(
        "DELETE FROM sensor_readings WHERE node_id = %s AND msg_id LIKE %s",
        (TEST_DEVICE_ID, "test-%")
    )

    remaining = db_query_count(
        "SELECT COUNT(*) FROM sensor_readings WHERE node_id = %s AND msg_id LIKE %s",
        (TEST_DEVICE_ID, "test-%")
    )
    record("Test rows cleaned up", remaining == 0, f"{remaining} rows remaining")



# ─────────────────────────────────────────────────────────────────────────────
# Final Summary
# ─────────────────────────────────────────────────────────────────────────────
def print_summary():
    passed = sum(1 for _, p, _ in results if p)
    total  = len(results)
    failed = total - passed

    print(f"\n{'═'*60}")
    print(f"  {BOLD}TEST RESULTS{RESET}  {passed}/{total} passed")
    print(f"{'═'*60}")

    if failed == 0:
        print(f"\n  {GREEN}{BOLD}ALL TESTS PASSED ✓{RESET}")
        print(f"  The full pipeline is working:")
        print(f"  Device → MQTT → Backend → WebSocket → Dashboard\n")
    else:
        print(f"\n  {RED}{BOLD}{failed} TEST(S) FAILED{RESET}")
        print(f"\n  Failed tests:")
        for name, passed, detail in results:
            if not passed:
                print(f"    {FAIL} {name} — {detail}")
        print()

    print("  ┌─────────────────────────────────────────────────────┐")
    print("  │  Next steps:                                        │")
    print("  │  1. Open the dashboard — you should see TESTDEV001  │")
    print("  │     Online, battery ~62%, signal Good               │")
    print("  │  2. Check the data table for test readings          │")
    print("  │  3. If all passed → start docker-compose rebuild    │")
    print("  └─────────────────────────────────────────────────────┘\n")


# ─────────────────────────────────────────────────────────────────────────────
# ENTRY POINT
# ─────────────────────────────────────────────────────────────────────────────
async def main():
    print(f"""
{BOLD}{'═'*60}{RESET}
{BOLD}  FillXpert — MQTT Integration Test{RESET}
{'═'*60}
  MQTT Broker : {MQTT_HOST}:{MQTT_PORT}
  Database    : {DB_HOST}:{DB_PORT}/{DB_NAME}
  WebSocket   : {WS_URL}
  Test Device : {TEST_LOCATION}/{TEST_DEVICE_ID}
  Msg ID      : {TEST_MSG_ID}
{'═'*60}
""")

    # Pre-flight check — cannot run tests without a registered device
    ok = preflight_check()
    if not ok:
        sys.exit(1)

    # Run all tests sequentially
    await test_telemetry_flow()
    await test_duplicate_detection()
    await test_config_ack()
    await test_device_status()
    await test_websocket_event()
    await test_cleanup()

    print_summary()

    # Exit code: 0 if all passed, 1 if any failed
    failed = sum(1 for _, p, _ in results if not p)
    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    asyncio.run(main())
