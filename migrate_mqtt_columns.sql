-- ============================================================
-- Migration: Add MQTT columns + Device tables
-- Run this ONCE on your existing PostgreSQL database
-- ============================================================

-- 1. Add new columns to sensor_readings (safe: IF NOT EXISTS)
ALTER TABLE sensor_readings
    ADD COLUMN IF NOT EXISTS msg_id   VARCHAR(24),
    ADD COLUMN IF NOT EXISTS rssi_dbm INTEGER,
    ADD COLUMN IF NOT EXISTS trigger  VARCHAR(20),
    ADD COLUMN IF NOT EXISTS cfg_ver  INTEGER;

-- 2. Index on msg_id for fast duplicate checks
CREATE INDEX IF NOT EXISTS idx_msg_id ON sensor_readings (msg_id);

-- 3. Create devices table
CREATE TABLE IF NOT EXISTS devices (
    device_id           VARCHAR(50)  PRIMARY KEY,
    user_id             INTEGER      NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name                VARCHAR(100),
    location            VARCHAR(100),
    description         VARCHAR(255),
    sensor_type         VARCHAR(50)  DEFAULT 'moisture',
    cfg_version         INTEGER      DEFAULT 0,
    cfg_version_acked   INTEGER      DEFAULT 0,
    is_online           BOOLEAN      NOT NULL DEFAULT FALSE,
    last_seen           TIMESTAMP,
    battery_mv          INTEGER,
    rssi_dbm            INTEGER,
    created_at          TIMESTAMP    DEFAULT NOW(),
    updated_at          TIMESTAMP    DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_devices_user_id ON devices (user_id);

-- 4. Create device_configs table
CREATE TABLE IF NOT EXISTS device_configs (
    id           SERIAL PRIMARY KEY,
    device_id    VARCHAR(50) NOT NULL REFERENCES devices(device_id) ON DELETE CASCADE,
    user_id      INTEGER     NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    cfg_version  INTEGER     NOT NULL,
    sensor_type  VARCHAR(50) NOT NULL,
    freq         INTEGER     NOT NULL DEFAULT 2,
    time1_hour   INTEGER     NOT NULL DEFAULT 10,
    time1_min    INTEGER     NOT NULL DEFAULT 0,
    time2_hour   INTEGER,
    time2_min    INTEGER,
    payload_str  VARCHAR(12) NOT NULL,
    published_at TIMESTAMP   DEFAULT NOW(),
    ack_received BOOLEAN     NOT NULL DEFAULT FALSE,
    ack_at       TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_device_cfg_version ON device_configs (device_id, cfg_version);

-- Done!
SELECT 'Migration complete' AS status;
