from sqlalchemy import (
    Column, Integer, String, Float, DateTime, Boolean,
    ForeignKey, Index, UniqueConstraint
)
from sqlalchemy.sql import func
from database import Base


# ---------------------------------------------------------------------------
# Sensor type code → name mapping (matches firmware spec)
# ---------------------------------------------------------------------------
SENSOR_TYPE_MAP = {
    "01": "moisture",
    "02": "temperature",
    "03": "npk",
    "04": "ph",
    "05": "ultrasonic",
    "06": "humidity",
}

# Reverse map: name → code
SENSOR_NAME_TO_CODE = {v: k for k, v in SENSOR_TYPE_MAP.items()}

# Short key inside v{} → standard column name
V_KEY_TO_COLUMN = {
    "m":  "moisture",
    "h":  "humidity",
    "tp": "temperature",   # 'tp' used to avoid clash with 't' = transmitter ID
}


# ---------------------------------------------------------------------------
# Device — one row per physical transmitter box
# ---------------------------------------------------------------------------
class Device(Base):
    """
    Registry of every physical transmitter (STM32 + Quectel + sensors).
    Created by admin when deploying a device to the field.
    Updated automatically when MQTT messages arrive.
    """
    __tablename__ = "devices"

    device_id   = Column(String(50),  primary_key=True)    # e.g. "SNR001"
    user_id     = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"),
                         nullable=False, index=True)

    # Human-readable metadata
    name        = Column(String(100), nullable=True)        # "Field A – North corner"
    location    = Column(String(100), nullable=True)        # "sangrur" — matches MQTT topic level
    description = Column(String(255), nullable=True)

    # Current sensor attached to this transmitter
    sensor_type = Column(String(50),  nullable=True, default="moisture")

    # Config state
    cfg_version       = Column(Integer, nullable=True, default=0)  # version dashboard pushed
    cfg_version_acked = Column(Integer, nullable=True, default=0)  # version device confirmed

    # Live status (updated on every MQTT message)
    is_online   = Column(Boolean,  nullable=False, default=False)
    last_seen   = Column(DateTime, nullable=True)
    battery_mv  = Column(Integer,  nullable=True)  # millivolts e.g. 3750
    rssi_dbm    = Column(Integer,  nullable=True)  # e.g. -71

    created_at  = Column(DateTime, server_default=func.now())
    updated_at  = Column(DateTime, server_default=func.now(), onupdate=func.now())

    def to_dict(self):
        return {
            "device_id":         self.device_id,
            "user_id":           self.user_id,
            "name":              self.name,
            "location":          self.location,
            "description":       self.description,
            "sensor_type":       self.sensor_type,
            "cfg_version":       self.cfg_version,
            "cfg_version_acked": self.cfg_version_acked,
            "config_applied":    self.cfg_version == self.cfg_version_acked,
            "is_online":         self.is_online,
            "last_seen":         self.last_seen.isoformat() if self.last_seen else None,
            "battery_mv":        self.battery_mv,
            "battery_pct":       _mv_to_pct(self.battery_mv),
            "rssi_dbm":          self.rssi_dbm,
            "signal_label":      _rssi_label(self.rssi_dbm),
            "created_at":        self.created_at.isoformat() if self.created_at else None,
        }


# ---------------------------------------------------------------------------
# DeviceConfig — history of every config pushed to a device
# ---------------------------------------------------------------------------
class DeviceConfig(Base):
    """
    Every time dashboard pushes a new config, a row is created here.
    When device sends config/ack, we mark ack_received=True.
    """
    __tablename__ = "device_configs"

    id          = Column(Integer, primary_key=True, index=True)
    device_id   = Column(String(50), ForeignKey("devices.device_id", ondelete="CASCADE"),
                         nullable=False, index=True)
    user_id     = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"),
                         nullable=False)

    # Config values (human-readable)
    cfg_version = Column(Integer, nullable=False)
    sensor_type = Column(String(50), nullable=False)
    freq        = Column(Integer, nullable=False, default=2)   # readings per day
    time1_hour  = Column(Integer, nullable=False, default=10)
    time1_min   = Column(Integer, nullable=False, default=0)
    time2_hour  = Column(Integer, nullable=True,  default=14)  # NULL = only 1 reading
    time2_min   = Column(Integer, nullable=True,  default=0)

    # Compact payload string sent to device via MQTT (dynamic length)
    # 10 chars (1×), 14 chars (2×), 18 chars (3×), 22 chars (4×)
    # Format: [sensor:2][freq:2][timeN:4×freq][cfg_ver:2]
    # e.g. "010210001400"  → old format, now "0102100014000" + ver
    payload_str = Column(String(22), nullable=False)

    # Delivery tracking
    published_at  = Column(DateTime, server_default=func.now())
    ack_received  = Column(Boolean, nullable=False, default=False)
    ack_at        = Column(DateTime, nullable=True)

    # Extended time slots (time3/time4 for 3×/4×/day configs)
    time3_hour  = Column(Integer, nullable=True)
    time3_min   = Column(Integer, nullable=True)
    time4_hour  = Column(Integer, nullable=True)
    time4_min   = Column(Integer, nullable=True)

    __table_args__ = (
        Index("idx_device_cfg_version", "device_id", "cfg_version"),
    )

    def to_dict(self):
        def fmt(h, m):
            return f"{h:02d}:{m:02d}" if h is not None else None
        return {
            "id":           self.id,
            "device_id":    self.device_id,
            "cfg_version":  self.cfg_version,
            "sensor_type":  self.sensor_type,
            "freq":         self.freq,
            "time1":        fmt(self.time1_hour, self.time1_min),
            "time2":        fmt(self.time2_hour, self.time2_min),
            "time3":        fmt(self.time3_hour, self.time3_min),
            "time4":        fmt(self.time4_hour, self.time4_min),
            "payload_str":  self.payload_str,
            "published_at": self.published_at.isoformat() if self.published_at else None,
            "ack_received": self.ack_received,
            "ack_at":       self.ack_at.isoformat() if self.ack_at else None,
        }


# ---------------------------------------------------------------------------
# Helper utilities
# ---------------------------------------------------------------------------
def _mv_to_pct(mv: int | None) -> int | None:
    """Convert battery millivolts to rough percentage (3.0V=0%, 4.2V=100%)."""
    if mv is None:
        return None
    pct = int((mv - 3000) / 12)   # 1200 mV range → 100%
    return max(0, min(100, pct))


def _rssi_label(rssi: int | None) -> str:
    """Human-readable GSM signal label from RSSI dBm."""
    if rssi is None:
        return "unknown"
    if rssi >= -70:
        return "excellent"
    if rssi >= -85:
        return "good"
    if rssi >= -100:
        return "fair"
    return "poor"


def build_config_payload(sensor_type: str, freq: int,
                          times: list[tuple[int | None, int | None]],
                          cfg_ver: int = 0) -> str:
    """
    Build dynamic config string for device firmware.

    Format: [sensor_code:2][freq:2][timeN:4 × freq][cfg_ver:2]
    Each time slot is HHMM (4 chars). Only `freq` slots are appended.
    cfg_ver allows firmware to extract and echo back the version in ACK.

    Examples:
      freq=1, v1  → "0101100001"              (10 chars)
      freq=2, v2  → "01021000140002"           (14 chars)
      freq=3, v6  → "010310001400080006"       (18 chars)
      freq=4, v7  → "0104100014000800160007"   (22 chars)
    """
    code = SENSOR_NAME_TO_CODE.get(sensor_type, "01")
    parts = [code, f"{freq:02d}"]
    for i in range(freq):
        h, m = times[i] if i < len(times) else (None, None)
        if h is None or m is None:
            parts.append("0000")   # fallback: 00:00 if slot missing
        else:
            parts.append(f"{h:02d}{m:02d}")
    parts.append(f"{cfg_ver:02d}")  # always last 2 chars — version stamp
    return "".join(parts)
