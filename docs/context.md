# FillXpert / SensorVault — Codebase Context & Architecture Analysis

> **Last updated**: 2026-08-02 16:42 IST  
> **Conversation**: Deep architecture analysis for LoRa gateway migration

---

## 1. Current Architecture (AS-IS)

### Hardware Topology: One eSIM Per Node (Direct-to-Cloud)

```
┌──────────────────────┐       ┌──────────────────┐       ┌──────────────┐
│ Node (STM32 + Quectel│       │ Mosquitto MQTT   │       │ FastAPI      │
│ eSIM + Sensor)       │──4G──▶│ Broker on Oracle │──────▶│ Backend      │
│ e.g. D001            │       │ VM 140.245.7.35  │       │ (mqtt_handler│
└──────────────────────┘       │                  │       │  .py)        │
                               │                  │       └──────┬───────┘
┌──────────────────────┐       │                  │              │
│ Node D002            │──4G──▶│                  │              ▼
│ (STM32 + Quectel)    │       └──────────────────┘       ┌──────────────┐
└──────────────────────┘                                  │ PostgreSQL   │
                                                          │ + React      │
                                                          │ Dashboard    │
                                                          └──────────────┘
```

**Each node = STM32 MCU + Quectel 4G/LTE modem + eSIM + sensor.**  
Every node independently connects to the cellular network and publishes MQTT messages.

### MQTT Topic Schema

```
{location}/{device_id}/telemetry     ← sensor readings
{location}/{device_id}/config        ← dashboard → device (retained)
{location}/{device_id}/config/ack    ← device → dashboard (config applied)
{location}/{device_id}/status        ← online/offline (LWT)
```

### Telemetry Payload (JSON — sent by firmware)

```json
{
  "t":   "D001",          // transmitter id = device_id
  "ts":  1749570780,      // unix timestamp
  "s":   1,               // sensor type code
  "v":   {"m": 456},      // readings (int × 10)
  "b":   372,             // battery mV (int × 10)
  "r":   -71,             // RSSI dBm
  "a":   1,               // attempt count
  "mid": "a3f9b2c1"       // message id for dedup
}
```

### Backend Stack

| File | Purpose |
|------|---------|
| [app.py](file:///c:/Users/Anshd/lorawan_deploy/backend/app.py) | FastAPI main — lifespan starts MQTT, routes, WebSocket |
| [mqtt_handler.py](file:///c:/Users/Anshd/lorawan_deploy/backend/mqtt_handler.py) | Async MQTT subscriber → parse → DB → WebSocket broadcast |
| [models.py](file:///c:/Users/Anshd/lorawan_deploy/backend/models.py) | `SensorReading` table: `gateway_id` (location), `node_id` (device_id) |
| [models_device.py](file:///c:/Users/Anshd/lorawan_deploy/backend/models_device.py) | `Device` + `DeviceConfig` tables, sensor type maps |
| [routers/devices.py](file:///c:/Users/Anshd/lorawan_deploy/backend/routers/devices.py) | CRUD for devices, config push via MQTT retained |
| [config.py](file:///c:/Users/Anshd/lorawan_deploy/backend/config.py) | Settings: MQTT broker 140.245.7.35:1883 |
| [websocket_manager.py](file:///c:/Users/Anshd/lorawan_deploy/backend/websocket_manager.py) | Broadcasts JSON to all connected browser tabs |
| [schemas.py](file:///c:/Users/Anshd/lorawan_deploy/backend/schemas.py) | Pydantic input/output schemas for REST API |

### Frontend Stack

| File | Purpose |
|------|---------|
| [App.js](file:///c:/Users/Anshd/lorawan_deploy/frontend/src/App.js) | State root — data fetch, WebSocket, filters, CSV export |
| [Dashboard.js](file:///c:/Users/Anshd/lorawan_deploy/frontend/src/pages/Dashboard.js) | Filter panel + SensorChart + DataTable composition |
| [DataTable.js](file:///c:/Users/Anshd/lorawan_deploy/frontend/src/components/DataTable.js) | Readings table with sparklines |
| [SensorChart.js](file:///c:/Users/Anshd/lorawan_deploy/frontend/src/components/SensorChart.js) | Recharts time-series with toggleable metrics |
| [Stats.js](file:///c:/Users/Anshd/lorawan_deploy/frontend/src/components/Stats.js) | 4 stat cards (readings, locations, devices, last reading) |
| [Devices.js](file:///c:/Users/Anshd/lorawan_deploy/frontend/src/pages/Devices.js) | Device fleet management + registration |
| [DeviceConfig.js](file:///c:/Users/Anshd/lorawan_deploy/frontend/src/pages/DeviceConfig.js) | Per-device config push UI |
| [ManualEntry.js](file:///c:/Users/Anshd/lorawan_deploy/frontend/src/pages/ManualEntry.js) | Manual data entry form |

### Database Schema (PostgreSQL)

```sql
sensor_readings:
  id (PK), user_id (FK→users), gateway_id, node_id, timestamp,
  humidity, moisture, temperature, battery_voltage,
  measurements (JSON), msg_id, rssi_dbm, trigger, cfg_ver, created_at

devices:
  device_id (PK), user_id (FK→users), name, location, description,
  sensor_type, cfg_version, cfg_version_acked,
  is_online, last_seen, battery_mv, rssi_dbm, created_at, updated_at

device_configs:
  id (PK), device_id (FK→devices), user_id (FK→users),
  cfg_version, sensor_type, freq, time1_hour/min, time2_hour/min,
  time3_hour/min, time4_hour/min, payload_str, published_at,
  ack_received, ack_at
```

---

## 2. Proposed Architecture (TO-BE): LoRa Star Topology

### New Hardware Topology: One eSIM Gateway + Multiple LoRa Nodes

```
┌────────────┐                    ┌──────────────────────────┐
│ Sensor Node│                    │   eSIM Gateway           │
│ (STM32     │ ──── LoRa ────▶  │   (STM32 + Quectel eSIM  │
│ + LoRa TX  │   915MHz/868MHz   │    + LoRa RX module)     │
│ + Sensor)  │                    │                          │
│ e.g. D001  │                    │  Responsibilities:       │    ┌──────────────┐
└────────────┘                    │  1. Receive LoRa packets │    │ MQTT Broker  │
                                  │  2. Parse node ID from   │───▶│ (Mosquitto)  │
┌────────────┐                    │     packet header        │4G  │              │
│ Sensor Node│ ──── LoRa ────▶  │  3. Construct JSON       │    └──────┬───────┘
│ D002       │                    │  4. Publish to MQTT via  │           │
└────────────┘                    │     Quectel AT commands  │           ▼
                                  └──────────────────────────┘    ┌──────────────┐
┌────────────┐                                                    │ FastAPI      │
│ Sensor Node│ ──── LoRa ────▶  (same gateway)                  │ Backend      │
│ D003       │                                                    └──────────────┘
└────────────┘
```

### How Node Identification Works (LoRa P2P Star Network)

In a **LoRa P2P (point-to-point)** star network (not full LoRaWAN), there is **no standardized protocol** for node identification. The developer must implement a **custom packet header**. This is how The Things Network (TTN) and similar systems do it at a simplified level:

#### LoRa Packet Structure (Firmware-Level)

```
┌─────────┬─────────┬──────┬─────────────────────────┬─────┐
│ Dest ID │ Src ID  │ Seq# │ Payload (JSON/binary)   │ CRC │
│ 1 byte  │ 1 byte  │ 1 B  │ variable                │ 2 B │
└─────────┴─────────┴──────┴─────────────────────────┴─────┘
```

| Field | Size | Description |
|-------|------|-------------|
| **Dest ID** | 1 byte | Target address (0xFF = broadcast, 0x00 = gateway) |
| **Src ID** | 1 byte | Sender's unique node address (0x01 = D001, 0x02 = D002, etc.) |
| **Seq#** | 1 byte | Packet sequence number for dedup & ordering |
| **Payload** | variable | The actual sensor data (same JSON or binary-packed format) |
| **CRC** | 2 bytes | Integrity check (prevents garbage data from being accepted) |

#### Gateway-Side Processing

The gateway's LoRa receiver:
1. Receives the raw LoRa packet
2. Validates CRC
3. Extracts `Src ID` → maps to device_id (e.g., `0x01` → `"D001"`)
4. Extracts payload data
5. Constructs JSON telemetry payload
6. Publishes to MQTT: `{location}/{device_id}/telemetry`

**Key insight**: The MQTT topic structure and JSON payload format remain IDENTICAL to the current system. The gateway just acts as a transparent bridge.

### What This Means for Software Changes

> [!IMPORTANT]
> **The good news: The server-side software (backend + frontend) needs MINIMAL changes.**
> The gateway takes care of node identification and publishes to the SAME MQTT topic schema.
> From the backend's perspective, the data looks identical whether it came directly from a node's eSIM or was relayed through a LoRa gateway.

---

## 3. Identified Dashboard Bugs

### Bug 1: Random Large IDs (e.g., `1785668838292`)

**Visible in**: Screenshot 1 — the ID column shows numbers like `1785668838292`

**Root Cause**: In [App.js line 175](file:///c:/Users/Anshd/lorawan_deploy/frontend/src/App.js#L175):
```javascript
id: Date.now(),        // temp id for key
```
When a reading arrives via **WebSocket** (live), the frontend creates a temporary ID using `Date.now()` (epoch milliseconds). This gives huge numbers like `1785668838292`.

When the same reading is fetched from the **REST API** (after refresh), it has the database integer ID (e.g., `1608`).

**The two IDs are shown inconsistently:**
- Before refresh: WebSocket reading with `Date.now()` ID → `1785668838292`
- After refresh: DB reading with actual `id` → `1608`

### Bug 2: Data Disappears on Refresh

**Visible in**: Screenshot 2 — after refreshing the page, 0 readings shown

**Root Cause**: The time filter defaults to `'24'` (Last 24 Hours) which triggers a server-side `?hours=24` API call. BUT:

1. **Time Zone Mismatch**: The backend uses `datetime.utcnow()` to calculate the cutoff:
   ```python
   cutoff_time = datetime.utcnow() - timedelta(hours=hours)  # app.py line 266
   ```
   But the `SensorReading.timestamp` field stores values that came from the firmware's unix timestamp, which ARE already in UTC. However, if some readings were saved with timezone-naive timestamps that were actually IST (UTC+5:30), they'd appear to be in the future or outside the time window.

2. **Stale WebSocket state**: When the page refreshes, the component remounts, `data` starts as `[]`, the `fetchData` effect runs with `timeRange='24'`. If the API returns no data for "last 24 hours" (e.g., data is actually from months ago, or timezone mismatch), the dashboard shows empty.

3. **Real issue in Screenshot 2**: The filter shows "Last 1 Hour" but the PAU001 readings in Screenshot 1 have `timestamp` values from `4:35-4:37 PM` on `8/2/2026` — if the page was refreshed more than 1 hour later, those readings fall outside the 1-hour window. When switching to "Last 24 Hours" (Screenshot 3), D001 data from CHANDIGARH with `2:56 PM` timestamps appears.

   **Actual bug**: The `fetchData` function is called without arguments on refresh button click ([App.js line 358](file:///c:/Users/Anshd/lorawan_deploy/frontend/src/App.js#L358)):
   ```javascript
   <button onClick={fetchData} disabled={loading}>
   ```
   This calls `fetchData()` with NO `hoursParam`, so it uses the stale `timeRange` value from the closure. But `fetchData` is wrapped in `useCallback` that depends on `timeRange`, so if `timeRange` changed but `fetchData` wasn't re-created yet, the wrong time range is sent.

### Bug 3: Filter Issues

**Multiple problems identified:**

1. **Location/Device dropdowns are populated from data, not from API**: [App.js lines 129-130](file:///c:/Users/Anshd/lorawan_deploy/frontend/src/App.js#L129-L130):
   ```javascript
   setLocations([...new Set(readings.map(r => r.gateway_id))]);
   setDeviceIds([...new Set(readings.map(r => r.node_id))]);
   ```
   This means if the current time range returns NO data, the dropdowns are EMPTY. The user can't select a location or device to filter by because the lists were wiped.

   **SOTA fix**: Filter options should come from the `/api/gateways` and `/api/nodes` endpoints (which already exist!) and persist independently of the data result.

2. **Device filter not cascaded by location**: When you select a location, the device dropdown still shows ALL devices across all locations — it doesn't filter to only devices at that location. The `selectedLocation` change resets `selectedDevice` to `''` ([Dashboard.js line 64](file:///c:/Users/Anshd/lorawan_deploy/frontend/src/pages/Dashboard.js#L64)), but the device list itself is not filtered.

3. **No URL persistence**: Filters are in React state only. Refreshing the page resets all filters. SOTA: use URL search params (`?location=chandigarh&device=D001&hours=24`).

---

## 4. Changes Required for LoRa Gateway Architecture

### 4.1 Firmware-Level Changes (Hardware Team — NOT in this codebase)

| Change | Details |
|--------|---------|
| **Sensor nodes**: Remove Quectel modem, add LoRa TX module | STM32 + LoRa SX1276/SX1262 + Sensor |
| **Sensor nodes**: Implement custom LoRa packet with node ID header | `[DestAddr][SrcAddr][SeqNum][Payload][CRC]` |
| **Gateway node**: New device — STM32 + LoRa RX + Quectel eSIM | Receives LoRa, extracts node ID, publishes MQTT |
| **Gateway firmware**: Map node addresses to device IDs | Address `0x01` → `D001`, Address `0x02` → `D002`, etc. |
| **Gateway firmware**: Publish to same MQTT topic schema | `{location}/{device_id}/telemetry` — identical JSON payload |

### 4.2 Backend Changes (This Codebase)

> [!NOTE]
> **MINIMAL backend changes needed.** The MQTT topic schema and JSON payload format are designed to be gateway-agnostic. The gateway simply relays.

| File | Change | Reason |
|------|--------|--------|
| [models_device.py](file:///c:/Users/Anshd/lorawan_deploy/backend/models_device.py) | Add `device_type` field to `Device` model | Distinguish "gateway" vs "sensor_node" devices |
| [models_device.py](file:///c:/Users/Anshd/lorawan_deploy/backend/models_device.py) | Add `gateway_device_id` FK field to `Device` model | Link sensor nodes to their parent gateway |
| [routers/devices.py](file:///c:/Users/Anshd/lorawan_deploy/backend/routers/devices.py) | Update `DeviceCreate` schema | Add `device_type` and optional `gateway_device_id` |
| [mqtt_handler.py](file:///c:/Users/Anshd/lorawan_deploy/backend/mqtt_handler.py) | Add `lora_rssi` field extraction from payload | Gateway should include LoRa RSSI (not just GSM RSSI) |
| [models.py](file:///c:/Users/Anshd/lorawan_deploy/backend/models.py) | Add `lora_rssi` column (optional) | Track LoRa signal quality separate from cellular |

### 4.3 Frontend Changes (Dashboard Bugs)

| File | Change | Priority |
|------|--------|----------|
| [App.js](file:///c:/Users/Anshd/lorawan_deploy/frontend/src/App.js#L175) | Fix `id: Date.now()` → use actual DB ID from WebSocket payload | **HIGH** |
| [App.js](file:///c:/Users/Anshd/lorawan_deploy/frontend/src/App.js#L129-L130) | Load filter options from `/api/gateways` + `/api/nodes` independently | **HIGH** |
| [Dashboard.js](file:///c:/Users/Anshd/lorawan_deploy/frontend/src/pages/Dashboard.js) | Cascade device filter by selected location | **MEDIUM** |
| [App.js](file:///c:/Users/Anshd/lorawan_deploy/frontend/src/App.js#L358) | Fix refresh button to pass `timeRange` explicitly | **HIGH** |
| [Devices.js](file:///c:/Users/Anshd/lorawan_deploy/frontend/src/pages/Devices.js) | Add `device_type` indicator (Gateway vs Sensor Node) | **LOW** (post-migration) |
| [Devices.js](file:///c:/Users/Anshd/lorawan_deploy/frontend/src/pages/Devices.js) | Show gateway→node relationships | **LOW** (post-migration) |

---

## 5. What Does NOT Need to Change

| Component | Why It's Already Compatible |
|-----------|---------------------------|
| MQTT topic schema (`{location}/{device_id}/telemetry`) | Gateway publishes to the exact same topics |
| JSON payload format | Gateway constructs identical JSON |
| `mqtt_handler.py` message parsing | No changes to `_parse_telemetry()` — same payload format |
| `sensor_readings` DB table | `gateway_id` = location, `node_id` = device_id — unchanged |
| WebSocket broadcasting | Same events, same format |
| SensorChart / DataTable | Read from same data shape |
| Stats component | Counts readings/locations/devices — unchanged |
| Config push via MQTT retained | Same topic: `{location}/{device_id}/config` |
| Auth system (JWT + API keys) | Unrelated to transport |
| Manual Entry page | Uses device picker → sends to REST API — unchanged |
| Data Export page | Reads from same DB — unchanged |

---

## 6. SOTA Comparison & Recommendations

### vs. The Things Network (TTN) / ChirpStack

| Feature | TTN/ChirpStack | Our System | Gap |
|---------|---------------|------------|-----|
| Device identification | DevEUI (64-bit globally unique) | Custom node ID in LoRa header | ✅ OK for our scale |
| Network Server | Full LoRaWAN NS (Class A/B/C) | Custom gateway firmware | ✅ Simpler, fine for P2P |
| Security | AES-128 session keys | CRC only (add encryption later) | ⚠️ Consider AES |
| OTA Join | OTAA/ABP | Pre-configured node IDs | ✅ OK for field deployment |
| Dashboard | Grafana/ThingsBoard | Custom React dashboard | ✅ Better UX control |

### vs. ThingsBoard / Ubidots / Datacake

| Feature | SOTA Dashboards | Our Dashboard | Gap |
|---------|----------------|---------------|-----|
| Filter persistence | URL-based + saved views | In-memory only | ❌ Fix needed |
| Real-time updates | WebSocket with reconciliation | WebSocket but IDs break | ❌ Fix needed |
| Device hierarchy | Gateway → Node grouping | Flat list only | ⚠️ Add post-migration |
| Time-series charts | Multi-axis, zoomable | Basic recharts | ✅ OK for now |
| Alerting | Threshold alerts + email | Reference line only | ⚠️ Future feature |

---

## 7. Summary of Immediate Action Items

### Priority 1: Fix Dashboard Bugs (Pre-Migration)

1. **Fix WebSocket ID** — replace `Date.now()` with actual reading ID or a monotonically increasing counter that doesn't clash
2. **Fix filter persistence** — load locations/devices from API endpoints, not from data array
3. **Fix refresh** — ensure `fetchData()` always uses current `timeRange`
4. **Cascade device filter** — when location is selected, show only devices at that location

### Priority 2: Backend Prep for LoRa Architecture

1. Add `device_type` ("gateway" | "sensor_node") to `Device` model
2. Add `gateway_device_id` FK (nullable) to link sensor nodes to their gateway
3. Add optional `lora_rssi` to telemetry parsing
4. Update device registration API to accept new fields

### Priority 3: Frontend Updates for Gateway Architecture

1. Devices page: show gateway vs sensor node distinction
2. Devices page: show which nodes belong to which gateway
3. DeviceConfig page: config push now goes to gateway (which relays to node)

---

## 8. Glossary

| Term | Meaning |
|------|---------|
| **eSIM** | Embedded SIM — Quectel LTE module for cellular connectivity |
| **LoRa** | Long Range radio (Sub-GHz: 868/915 MHz), low power, 1-15 km range |
| **LoRaWAN** | Standardized LoRa protocol with Network Server — we use P2P instead |
| **P2P (LoRa)** | Point-to-point LoRa — custom protocol, no Network Server needed |
| **Gateway** | The one device with both LoRa receiver AND Quectel eSIM |
| **Sensor Node** | Field device with STM32 + LoRa transmitter + sensor (no eSIM) |
| **Quectel** | Manufacturer of the cellular modem module on the gateway |
| **MQTT** | Message broker protocol — Mosquitto on Oracle VM |
| **DevEUI** | LoRaWAN standard 64-bit device identifier (we use custom IDs instead) |
| **CRC** | Cyclic Redundancy Check — validates packet integrity |
