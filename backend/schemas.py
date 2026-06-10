from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional, Dict, Any


class SensorDataInput(BaseModel):
    """Schema for manual sensor data entry (admin use only — devices post via MQTT)"""
    gateway_id: str = Field(..., description="Location/area identifier (maps to MQTT topic prefix)")
    node_id: str = Field(..., description="Device ID (transmitter firmware ID, e.g. SNR001)")
    timestamp: datetime = Field(..., description="Timestamp of the reading")
    
    # Standard fixed measurements (backward compatible)
    humidity: Optional[float] = Field(None, ge=0, le=100, description="Humidity percentage")
    moisture: Optional[float] = Field(None, ge=0, le=100, description="Soil moisture percentage")
    temperature: Optional[float] = Field(None, description="Temperature in Celsius")
    battery_voltage: Optional[float] = Field(None, ge=0, le=5, description="Battery voltage (0-5V)")
    
    # Dynamic measurements for custom sensors (NPK, pH, etc.)
    measurements: Optional[Dict[str, Any]] = Field(None, description="Custom sensor measurements")

    class Config:
        json_schema_extra = {
            "example": {
                "gateway_id": "chandigarh",
                "node_id": "SNR001",
                "timestamp": "2026-06-10T10:00:00Z",
                "humidity": 65.5,
                "moisture": 42.3,
                "temperature": 25.8,
                "battery_voltage": 3.7,
                "measurements": {
                    "npk_n": 45.2,
                    "npk_p": 23.1,
                    "npk_k": 38.7,
                    "ph": 6.8
                }
            }
        }


class SensorDataResponse(BaseModel):
    """Response schema after receiving data"""
    status: str
    message: str
    job_id: Optional[str] = None


class SensorReadingOutput(BaseModel):
    """Schema for sensor reading output"""
    id: int
    gateway_id: str
    node_id: str
    timestamp: datetime
    humidity: Optional[float]
    moisture: Optional[float]
    temperature: Optional[float]
    battery_voltage: Optional[float]
    measurements: Optional[Dict[str, Any]]
    created_at: datetime

    class Config:
        from_attributes = True
