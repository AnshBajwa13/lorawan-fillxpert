-- ============================================================
-- Migration: LoRa Gateway Architecture Support
-- Run this ONCE on your existing PostgreSQL database
-- Adds LoRa gateway fields to devices table + lora_rssi to sensor_readings
-- ============================================================

-- 1. Add lora_rssi to sensor_readings (LoRa radio signal node↔gateway)
--    Distinct from rssi_dbm which is GSM/cellular signal (gateway↔cloud)
ALTER TABLE sensor_readings
    ADD COLUMN IF NOT EXISTS lora_rssi INTEGER;

-- 2. Add LoRa gateway architecture columns to devices table
ALTER TABLE devices
    ADD COLUMN IF NOT EXISTS device_type
        VARCHAR(20) NOT NULL DEFAULT 'direct_esim',   -- "gateway" | "sensor_node" | "direct_esim"
    ADD COLUMN IF NOT EXISTS gateway_device_id
        VARCHAR(50) REFERENCES devices(device_id) ON DELETE SET NULL,  -- parent gateway (sensor_node only)
    ADD COLUMN IF NOT EXISTS lora_addr
        INTEGER;                                      -- LoRa address byte (0x01, 0x02, ...) for sensor_node

-- 3. Index for quickly finding all sensor nodes belonging to a gateway
CREATE INDEX IF NOT EXISTS idx_devices_gateway ON devices (gateway_device_id)
    WHERE gateway_device_id IS NOT NULL;

-- 4. Index for device_type filtering (listing all gateways, etc.)
CREATE INDEX IF NOT EXISTS idx_devices_type ON devices (device_type);

-- 5. Existing rows: mark all current devices as "direct_esim" (old architecture)
--    They were STM32 + Quectel eSIM, directly publishing MQTT — no LoRa relay.
UPDATE devices
    SET device_type = 'direct_esim'
    WHERE device_type IS NULL OR device_type = '';

-- Verify
SELECT
    device_type,
    COUNT(*) AS device_count
FROM devices
GROUP BY device_type
ORDER BY device_type;

SELECT 'LoRa gateway migration complete' AS status;
