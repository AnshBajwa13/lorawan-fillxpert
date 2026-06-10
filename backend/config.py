from pydantic_settings import BaseSettings
from functools import lru_cache
from typing import Optional


class Settings(BaseSettings):
    # Database
    DATABASE_URL: str = "postgresql://lorawan_user:lorawan_pass@localhost:5432/lorawan_db"
    
    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"
    
    # Server
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    
    # Security
    SECRET_KEY: str = "your-secret-key-change-in-production"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    
    # Environment
    ENVIRONMENT: str = "development"
    
    # CORS
    ALLOWED_ORIGINS: str = "http://localhost:3000"
    
    # Email (optional)
    FROM_EMAIL: Optional[str] = None
    SENDGRID_API_KEY: Optional[str] = None

    # MQTT Broker (Mosquitto on Oracle server)
    MQTT_BROKER_HOST: str = "140.245.7.35"
    MQTT_BROKER_PORT: int = 1883
    MQTT_USERNAME: Optional[str] = None   # set in .env if Mosquitto auth enabled
    MQTT_PASSWORD: Optional[str] = None   # set in .env if Mosquitto auth enabled
    MQTT_CLIENT_ID: str = "iot-dashboard-backend"
    MQTT_RECONNECT_INTERVAL: int = 5      # seconds between reconnect attempts

    class Config:
        env_file = ".env"
        extra = "ignore"  # Ignore extra fields in .env


@lru_cache()
def get_settings():
    return Settings()
