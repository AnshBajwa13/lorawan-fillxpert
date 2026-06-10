from sqlalchemy import Column, Integer, String, Float, DateTime, Index, JSON, ForeignKey
from sqlalchemy.sql import func
from database import Base
from datetime import datetime


class SensorReading(Base):
    """Model for storing sensor readings from eSIM field transmitter devices"""
    __tablename__ = "sensor_readings"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    gateway_id = Column(String(50), nullable=False, index=True)  # = device location (MQTT topic prefix)
    node_id = Column(String(50), nullable=False, index=True)      # = device_id (transmitter firmware ID)
    timestamp = Column(DateTime, nullable=False, index=True)
    
    # Fixed standard fields (backward compatible)
    humidity = Column(Float, nullable=True)
    moisture = Column(Float, nullable=True)
    temperature = Column(Float, nullable=True)
    battery_voltage = Column(Float, nullable=True)  # Battery monitoring (volts)

    # Dynamic measurements stored as JSON
    # Example: {"npk_n": 45.2, "npk_p": 23.1, "npk_k": 38.7, "ph": 6.8}
    measurements = Column(JSON, nullable=True)

    # MQTT-specific fields (added for device telemetry)
    msg_id   = Column(String(24), nullable=True)    # dedup: unique per message (indexed below)
    rssi_dbm = Column(Integer,    nullable=True)     # GSM signal strength dBm
    trigger  = Column(String(20), nullable=True)     # schedule / manual / buffered
    cfg_ver  = Column(Integer,    nullable=True)     # config version active on device

    created_at = Column(DateTime, server_default=func.now())

    # Composite index for faster queries
    __table_args__ = (
        Index('idx_user_gateway_node_timestamp', 'user_id', 'gateway_id', 'node_id', 'timestamp'),
        Index('idx_user_timestamp', 'user_id', 'timestamp'),
        Index('idx_msg_id', 'msg_id'),
    )

    def to_dict(self):
        """Convert model to dictionary"""
        result = {
            "id": self.id,
            "user_id": self.user_id,
            "gateway_id": self.gateway_id,
            "node_id": self.node_id,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "humidity": self.humidity,
            "moisture": self.moisture,
            "temperature": self.temperature,
            "battery_voltage": self.battery_voltage,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }
        
        # Add dynamic measurements if present
        if self.measurements:
            result["measurements"] = self.measurements
        
        return result
