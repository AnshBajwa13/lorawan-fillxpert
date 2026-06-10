# IoT Software Spec — Answers + Complete Software Contract for Hardware

---

## Q1: Why "soil" at the Start of Topic?

**Short answer: You don't have to use it. I added it as a namespace. Skip it if you want.**

Here's the only reason to have it:

```
Without prefix:   sangrur/SNR001/config
With prefix:      soil/sangrur/SNR001/config
```

If you ONLY have one project on this broker (soil monitoring), `sangrur/SNR001/config` is perfectly fine.

The prefix `soil` only helps if later you add a **different project** on the same broker:
```
soil/sangrur/SNR001/config    ← soil sensors
water/sangrur/WR001/config    ← water level sensors  (different project)
```

**Decision: For now, use:**
```
sangrur/SNR001/telemetry
sangrur/SNR001/config
sangrur/SNR001/status
```
Exactly matching your original idea. Clean and simple.

---

## Q2: Your Config Understanding — Confirmed Correct ✅

You asked:
> "SNR001 is same, we just update it from config — new sensor attached at port of SNR001 and now it's moisture — we send from dashboard new config right?"

**Yes. 100% correct. This is exactly how it works.**

```
Same transmitter box (SNR001) stays in the field
    ↓
User physically disconnects temperature sensor
User physically connects moisture sensor
    ↓
Admin opens dashboard
Finds SNR001 in device list
Changes sensor_type from "temperature" to "moisture"
Clicks "Push Config"
    ↓
Dashboard publishes new config to topic:
    sangrur/SNR001/config   (with retain=true)
    ↓
Next time SNR001 wakes up:
    → Connects to broker
    → Subscribes to sangrur/SNR001/config
    → Gets new config INSTANTLY (retained message)
    → Reads moisture sensor
    → Sends moisture readings
Done. No firmware change. No hardware change. Just a config push.
```

---

## Q3: Your Binary Format `021000140001` — Analysis

You proposed:
```
sangrur1/sensor1config    021000140001
```

And you said: "for temperature it can be 02"

**Let me decode what you're thinking:**

```
02   10   00   14   00   01
│    │    │    │    │    │
│    │    │    │    │    └─ something (freq? readings count?)
│    │    │    │    └────── minute of 2nd reading time (00 = :00)
│    │    │    └─────────── hour of 2nd reading time (14 = 2PM)
│    │    └──────────────── minute of 1st reading time (00 = :00)
│    └───────────────────── hour of 1st reading time (10 = 10AM)
└────────────────────────── sensor type code (02 = temperature, 01 = moisture?)
```

**This is actually a smart compact format.** Each pair of digits = one value.

### Proposed Sensor Type Codes
```
01 = moisture
02 = temperature
03 = NPK
04 = pH
05 = ultrasonic (water level)
06 = humidity
```

### Full Format Definition (Fixed 12-character string)

```
Position  Length  Meaning          Example
0-1       2 chars sensor_type      01 = moisture, 02 = temperature
2-3       2 chars time1_hour       10 = 10AM, 08 = 8AM
4-5       2 chars time1_minute     00 = :00 minutes
6-7       2 chars time2_hour       14 = 2PM
8-9       2 chars time2_minute     00 = :00 minutes
10-11     2 chars readings_per_day 02 = 2 readings per day
```

### Examples

| Config | Meaning |
|---|---|
| `011000140002` | Moisture sensor, read at 10:00 and 14:00, twice per day |
| `021000140002` | Temperature sensor, read at 10:00 and 14:00, twice per day |
| `030800180001` | NPK sensor, read at 08:00 only (1 reading per day) |
| `010700190003` | Moisture sensor, read at 07:00, 13:00(?), 3 times per day |

> [!IMPORTANT]
> **Problem with 1 reading per day**: Your format has 2 time slots hardcoded. If freq=1, what to do with time2_hour/time2_minute? Proposal: set time2 to `9999` as a sentinel value meaning "no second reading".
>
> `011000999901` = Moisture, only read at 10:00, once per day

---

## Q4: How Does the Device Parse This? (C Code for STM32)

When Quectel receives an MQTT message, it sends this to STM32 via UART:

```
+QMTRECV: 0,0,"sangrur/SNR001/config","021000140002"
```

Your STM32 firmware receives this string and parses it:

```c
// ---- STEP 1: Find the payload inside the QMTRECV response ----
// Input from UART: +QMTRECV: 0,0,"sangrur/SNR001/config","021000140002"

char uart_buf[] = "+QMTRECV: 0,0,\"sangrur/SNR001/config\",\"021000140002\"";

// Find start of payload (after last comma + quote)
char *payload_start = strrchr(uart_buf, '\"');  // Find last "
// Go backwards one more to find opening quote
// Simple: find last ," pattern
char *p = strstr(uart_buf, ",\"");
while (strstr(p+1, ",\"") != NULL) {
    p = strstr(p+1, ",\"");
}
p += 2;  // Skip ,"
// p now points to: 021000140002"

// ---- STEP 2: Parse the 12-character config string ----
char payload[13];
strncpy(payload, p, 12);
payload[12] = '\0';
// payload = "021000140002"

// ---- STEP 3: Extract each field ----
char temp[3];
temp[2] = '\0';

// sensor_type
strncpy(temp, payload + 0, 2);
int sensor_type = atoi(temp);   // 02

// time1 hour
strncpy(temp, payload + 2, 2);
int time1_hour = atoi(temp);    // 10

// time1 minute
strncpy(temp, payload + 4, 2);
int time1_min = atoi(temp);     // 00

// time2 hour
strncpy(temp, payload + 6, 2);
int time2_hour = atoi(temp);    // 14

// time2 minute
strncpy(temp, payload + 8, 2);
int time2_min = atoi(temp);     // 00

// readings per day
strncpy(temp, payload + 10, 2);
int freq = atoi(temp);          // 02

// ---- STEP 4: Apply config ----
current_config.sensor_type = sensor_type;  // Save to struct
current_config.time1_hour  = time1_hour;
current_config.time1_min   = time1_min;
current_config.time2_hour  = time2_hour;
current_config.time2_min   = time2_min;
current_config.freq        = freq;

// ---- STEP 5: Save to flash so it survives power off ----
save_config_to_flash(&current_config);

// ---- STEP 6: Update RTC alarm to new schedule ----
RTC_SetAlarm(time1_hour, time1_min);  // Wake at 10:00
if (freq == 2) {
    RTC_SetAlarm2(time2_hour, time2_min);  // Wake at 14:00
}
```

**That's it. No JSON library needed. Simple string indexing. Works perfectly on STM32.**

---

## Q5: What Telemetry Does Device SEND Back?

This is the data the device publishes **to** the broker **from** the sensor.

### Topic
```
sangrur/SNR001/telemetry
```

### Payload — Two Options

**Option A: Your compact style (binary-like string)**
```
01|1000|456|372|0918|01
│   │    │    │    │   │
│   │    │    │    │   └── attempts (how many tries to send)
│   │    │    │    └────── timestamp: 09:18 (time reading was taken)
│   │    │    └─────────── battery: 372 = 3.72V
│   │    └──────────────── moisture reading: 45.6% (456 = 45.6)
│   └───────────────────── time: 10:00 (when it was supposed to read)
└────────────────────────── sensor_type: 01 = moisture
```

**Problem**: When different sensors have different reading types and counts, compact format breaks. Temperature sensor would have `temp` value. NPK sensor would have 3 values (N, P, K). Hard to extend.

**Option B: JSON (Recommended for telemetry)**
```json
{"t":"SNR001","ts":1749570780,"s":1,"v":{"m":456},"b":372,"r":-71,"a":1}
```

Compact JSON with short keys:
- `t` = transmitter ID
- `ts` = Unix timestamp
- `s` = sensor type code (1=moisture, 2=temp, 3=NPK)
- `v` = values object (flexible, add any sensor readings)
- `b` = battery millivolts (372 = 3720mv = 3.72V)
- `r` = RSSI signal strength (-71 dBm)
- `a` = attempt count (1=first try, 2=retry)

For NPK sensor:
```json
{"t":"SNR001","ts":1749570780,"s":3,"v":{"n":452,"p":231,"k":387},"b":372,"r":-71,"a":1}
```

**Recommendation: Use JSON for telemetry, compact string for config.**

Why the difference?
- **Config** → fixed format, same 6 fields always → compact string is perfect
- **Telemetry** → different sensors have different data → JSON handles it cleanly

JSON on STM32 with `cJSON` library (from ST's own examples, ~2KB flash footprint):
```c
cJSON *root = cJSON_CreateObject();
cJSON_AddStringToObject(root, "t", device_id);
cJSON_AddNumberToObject(root, "ts", unix_timestamp);
cJSON_AddNumberToObject(root, "s", sensor_type);
cJSON *vals = cJSON_CreateObject();
cJSON_AddNumberToObject(vals, "m", moisture_raw);  // 456 = 45.6%
cJSON_AddItemToObject(root, "v", vals);
cJSON_AddNumberToObject(root, "b", battery_mv);
cJSON_AddNumberToObject(root, "r", rssi);
cJSON_AddNumberToObject(root, "a", attempts);

char *json_str = cJSON_PrintUnformatted(root);
// json_str = {"t":"SNR001","ts":1749570780,"s":1,"v":{"m":456},"b":372,"r":-71,"a":1}
// Publish this string to MQTT topic
cJSON_Delete(root);
```

---

## Full Quectel AT Command Sequence (for Hardware Person)

This is the EXACT sequence the STM32 firmware sends via UART to the Quectel module:

```
──────────────── DEVICE WAKES UP ────────────────

STM32 → Quectel: AT
Quectel → STM32: OK

STM32 → Quectel: AT+QMTCFG="recv/mode",0,0,1
Quectel → STM32: OK
(Sets receive mode: payload delivered via URC directly)

STM32 → Quectel: AT+QMTOPEN=0,"140.245.7.35",1883
Quectel → STM32: OK
                  +QMTOPEN: 0,0   (0 = success)

STM32 → Quectel: AT+QMTCONN=0,"SNR001","","" 
Quectel → STM32: OK
                  +QMTCONN: 0,0,0   (success)
(Client ID = SNR001, no username/password yet)

──────────────── SUBSCRIBE TO CONFIG FIRST ────────────────

STM32 → Quectel: AT+QMTSUB=0,1,"sangrur/SNR001/config",1
Quectel → STM32: OK
                  +QMTSUB: 0,1,0,1  (success, QoS 1)

  *** BROKER IMMEDIATELY DELIVERS RETAINED CONFIG ***
  Quectel → STM32: +QMTRECV: 0,0,"sangrur/SNR001/config","021000140002"

  STM32 firmware: parse payload "021000140002"
  Apply config if different from stored version
  Save to flash

──────────────── READ SENSOR ────────────────

  STM32: reads sensor via ADC/I2C/UART
  STM32: constructs telemetry JSON string
  STM32: gets current time from RTC

──────────────── PUBLISH TELEMETRY ────────────────

STM32 → Quectel: AT+QMTPUBEX=0,1,1,"sangrur/SNR001/telemetry",47
  (47 = length of JSON string below)
Quectel → STM32: >   (prompt, ready for data)
STM32 → Quectel: {"t":"SNR001","ts":1749570780,"s":1,"v":{"m":456},"b":372,"r":-71,"a":1}
Quectel → STM32: OK
                  +QMTPUB: 0,1,0   (0 = success, message delivered to broker)

──────────────── DISCONNECT AND SLEEP ────────────────

STM32 → Quectel: AT+QMTDISC=0
Quectel → STM32: OK
                  +QMTDISC: 0,0

STM32: Power off Quectel module (GPIO)
STM32: Enter deep sleep, RTC alarm set for next reading time
```

---

## What "No Config Available" Means

You asked: if no config update, device gets `00` and goes to sleep?

**With retained messages — there is ALWAYS a config.**

- When device is first provisioned, dashboard pushes an initial config with `retain=true`
- That config stays on broker forever (until replaced)
- Every time device subscribes, it gets that retained config
- If config hasn't changed since last time → device checks `cfg_ver` field → version same → skip applying → continue

**What if device has NEVER received a config?**
- Device uses hardcoded default config in firmware flash
- Default: `sensor_type=01 (moisture), time1=10:00, time2=14:00, freq=2`
- Dashboard must push initial config during setup/provisioning step

---

## Software Spec for Hardware Person

This is the contract. Hardware firmware must implement:

### 1. Config Structure (store in flash)
```c
typedef struct {
    uint8_t  sensor_type;    // 01=moisture, 02=temp, 03=NPK, 04=pH
    uint8_t  time1_hour;     // 0-23
    uint8_t  time1_min;      // 0-59
    uint8_t  time2_hour;     // 0-23, or 99 if no second reading
    uint8_t  time2_min;      // 0-59
    uint8_t  freq;           // 1 or 2
    uint8_t  cfg_ver;        // increments each time config changes
} DeviceConfig;
```

### 2. Config Topic (subscribe)
```
Topic:   sangrur/SNR001/config
QoS:     1
Retain:  delivered by broker automatically
```

### 3. Config Payload (receive and parse)
```
Format:  12 ASCII digits, each 2 digits = 1 field
Example: 021000140002
Fields:  [sensor_type][time1_H][time1_M][time2_H][time2_M][freq]
```

### 4. Telemetry Topic (publish)
```
Topic:   sangrur/SNR001/telemetry
QoS:     1
Retain:  false
```

### 5. Telemetry Payload (build and send)
```json
{"t":"SNR001","ts":1749570780,"s":1,"v":{"m":456},"b":372,"r":-71,"a":1}
```
Values always integers (no floats over MQTT to save space):
- moisture: 456 = 45.6% (multiply by 10, server divides by 10)
- temperature: 281 = 28.1°C
- battery: 372 = 3720 mV

### 6. Wake Cycle Logic
```
Wake up (RTC interrupt)
→ Power on Quectel
→ Wait for GSM registration (timeout: 60 seconds)
→ MQTT connect to 140.245.7.35:1883
→ Subscribe to config topic
→ Wait max 3 seconds for retained config delivery
→ Parse and apply config if cfg_ver changed
→ Read sensor
→ Build telemetry JSON
→ Publish telemetry (QoS 1, wait PUBACK, max 10 seconds)
→ If PUBACK timeout: save to flash buffer
→ MQTT disconnect
→ Power off Quectel
→ Deep sleep until next RTC alarm
```

### 7. Flash Buffer (missed readings)
```
On next wake: before reading sensor, drain flash buffer first
Max buffer: 20 readings (4KB flash)
Send oldest first (FIFO)
```

### 8. Button Press (10 second hold)
```
External interrupt → wake from sleep
→ Connect
→ Read sensor
→ Publish with "trigger":"manual" flag (or add field a=99 to distinguish)
→ Repeat every 10 seconds for 5 minutes
→ Return to normal schedule
```

---

## Summary: Your Topic Design (Final)

```
sangrur/SNR001/config       ← Dashboard → Device (retain=true, QoS 1)
sangrur/SNR001/telemetry    ← Device → Dashboard (no retain, QoS 1)
sangrur/SNR001/status       ← LWT: device online/offline (retain=true, QoS 1)
```

**Config format:**  `021000140002`  (12 char string)
**Telemetry format:** `{"t":"SNR001","ts":...,"s":...,"v":{...},"b":...,"r":...}`
