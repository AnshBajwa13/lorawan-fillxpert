"""
Device management API endpoints.

All routes require a logged-in user (Bearer JWT).
Devices are scoped to the authenticated user — user can only see/manage their own devices.
"""

import aiomqtt
import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from auth import get_current_user
from config import get_settings
from database import get_db
from models_auth import User
from models_device import Device, DeviceConfig, build_config_payload, SENSOR_TYPE_MAP

logger = logging.getLogger("routers.devices")
router = APIRouter(prefix="/api/devices", tags=["devices"])
settings = get_settings()


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------
class DeviceCreate(BaseModel):
    device_id:   str
    name:        Optional[str] = None
    location:    str            # e.g. "sangrur" — must match MQTT topic level
    sensor_type: str = "moisture"
    description: Optional[str] = None


class DeviceConfigPush(BaseModel):
    sensor_type: str
    freq:        int = 2         # 1 or 2 readings per day
    time1:       str = "10:00"   # "HH:MM"
    time2:       Optional[str] = "14:00"  # "HH:MM" or None if freq=1


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------
def _parse_time(t: str) -> tuple[int, int]:
    """Parse "HH:MM" → (hour, minute). Raises ValueError on bad format."""
    try:
        h, m = t.strip().split(":")
        return int(h), int(m)
    except Exception:
        raise ValueError(f"Invalid time format '{t}' — expected HH:MM")


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@router.get("")
def list_devices(
    db:           Session = Depends(get_db),
    current_user: User    = Depends(get_current_user),
):
    """List all devices registered to the current user."""
    devices = (
        db.query(Device)
        .filter(Device.user_id == current_user.id)
        .order_by(Device.created_at.desc())
        .all()
    )
    return [d.to_dict() for d in devices]


@router.post("", status_code=status.HTTP_201_CREATED)
def register_device(
    body:         DeviceCreate,
    db:           Session = Depends(get_db),
    current_user: User    = Depends(get_current_user),
):
    """Register a new transmitter device under the current user's account."""
    existing = db.query(Device).filter(Device.device_id == body.device_id).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Device '{body.device_id}' is already registered.",
        )
    device = Device(
        device_id   = body.device_id,
        user_id     = current_user.id,
        name        = body.name or body.device_id,
        location    = body.location,
        sensor_type = body.sensor_type,
        description = body.description,
        cfg_version = 0,
        cfg_version_acked = 0,
        is_online   = False,
    )
    db.add(device)
    db.commit()
    db.refresh(device)
    logger.info("Registered device %s for user %d", body.device_id, current_user.id)
    return device.to_dict()


@router.get("/{device_id}")
def get_device(
    device_id:    str,
    db:           Session = Depends(get_db),
    current_user: User    = Depends(get_current_user),
):
    """Get full details for one device including latest config."""
    device = _get_owned_device(device_id, db, current_user)
    latest_config = (
        db.query(DeviceConfig)
        .filter(DeviceConfig.device_id == device_id)
        .order_by(DeviceConfig.cfg_version.desc())
        .first()
    )
    result = device.to_dict()
    result["latest_config"] = latest_config.to_dict() if latest_config else None
    return result


@router.post("/{device_id}/config")
async def push_config(
    device_id:    str,
    body:         DeviceConfigPush,
    db:           Session = Depends(get_db),
    current_user: User    = Depends(get_current_user),
):
    """
    Push a new configuration to a device via MQTT (retained message).
    The device will receive this config the next time it wakes up and connects.
    """
    device = _get_owned_device(device_id, db, current_user)

    # Validate sensor type
    if body.sensor_type not in list(SENSOR_TYPE_MAP.values()) + list(SENSOR_TYPE_MAP.keys()):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Unknown sensor_type '{body.sensor_type}'. "
                   f"Valid: {list(SENSOR_TYPE_MAP.values())}",
        )

    # Parse times
    try:
        t1h, t1m = _parse_time(body.time1)
        t2h, t2m = (_parse_time(body.time2) if body.time2 and body.freq == 2
                    else (None, None))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                            detail=str(e))

    # Build compact 12-char payload string
    payload_str = build_config_payload(
        sensor_type=body.sensor_type,
        time1_h=t1h, time1_m=t1m,
        time2_h=t2h, time2_m=t2m,
        freq=body.freq,
    )

    # Increment config version
    new_version = (device.cfg_version or 0) + 1

    # Publish to MQTT with retain=True
    # Topic: {location}/{device_id}/config
    topic = f"{device.location}/{device_id}/config"
    try:
        async with aiomqtt.Client(
            hostname  = settings.MQTT_BROKER_HOST,
            port      = settings.MQTT_BROKER_PORT,
            username  = settings.MQTT_USERNAME,
            password  = settings.MQTT_PASSWORD,
        ) as client:
            await client.publish(
                topic   = topic,
                payload = payload_str,
                qos     = 1,
                retain  = True,   # KEY: device gets this the moment it connects
            )
    except aiomqtt.MqttError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"MQTT publish failed: {e}",
        )

    # Save config record to DB
    config_row = DeviceConfig(
        device_id   = device_id,
        user_id     = current_user.id,
        cfg_version = new_version,
        sensor_type = body.sensor_type,
        freq        = body.freq,
        time1_hour  = t1h,
        time1_min   = t1m,
        time2_hour  = t2h,
        time2_min   = t2m,
        payload_str = payload_str,
        ack_received= False,
    )
    db.add(config_row)

    # Update device cfg_version and sensor_type
    device.cfg_version  = new_version
    device.sensor_type  = body.sensor_type
    db.commit()

    logger.info(
        "Config v%d pushed to device %s (topic: %s, payload: %s)",
        new_version, device_id, topic, payload_str,
    )

    return {
        "status":      "published",
        "device_id":   device_id,
        "topic":       topic,
        "payload_str": payload_str,
        "cfg_version": new_version,
        "message":     (
            f"Config v{new_version} sent to {topic} (retained). "
            "Device will apply it on next wakeup."
        ),
    }


@router.get("/{device_id}/configs")
def get_config_history(
    device_id:    str,
    db:           Session = Depends(get_db),
    current_user: User    = Depends(get_current_user),
):
    """Full config push history for a device."""
    _get_owned_device(device_id, db, current_user)
    configs = (
        db.query(DeviceConfig)
        .filter(DeviceConfig.device_id == device_id)
        .order_by(DeviceConfig.cfg_version.desc())
        .limit(20)
        .all()
    )
    return [c.to_dict() for c in configs]


@router.delete("/{device_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_device(
    device_id:    str,
    db:           Session = Depends(get_db),
    current_user: User    = Depends(get_current_user),
):
    """Remove a device from the registry (does not delete historical readings)."""
    device = _get_owned_device(device_id, db, current_user)
    db.delete(device)
    db.commit()
    logger.info("Device %s deleted by user %d", device_id, current_user.id)


# ---------------------------------------------------------------------------
# Internal helper
# ---------------------------------------------------------------------------
def _get_owned_device(device_id: str, db: Session, user: User) -> Device:
    device = (
        db.query(Device)
        .filter(Device.device_id == device_id, Device.user_id == user.id)
        .first()
    )
    if not device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Device '{device_id}' not found.",
        )
    return device
