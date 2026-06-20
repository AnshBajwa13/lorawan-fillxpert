-- Migration: Add time3/time4 columns and widen payload_str for dynamic config payload
-- Run this on EC2 ONCE:
--   docker exec -it lorawan_deploy-db-1 psql -U postgres -d fillxpert -f /tmp/migrate_payload_v2.sql
-- OR connect directly and paste these lines.

ALTER TABLE device_configs
    ADD COLUMN IF NOT EXISTS time3_hour INTEGER,
    ADD COLUMN IF NOT EXISTS time3_min  INTEGER,
    ADD COLUMN IF NOT EXISTS time4_hour INTEGER,
    ADD COLUMN IF NOT EXISTS time4_min  INTEGER;

ALTER TABLE device_configs
    ALTER COLUMN payload_str TYPE VARCHAR(20);
