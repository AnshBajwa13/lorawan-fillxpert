"""
Authentication-related database models
"""
from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, func
from database import Base


class User(Base):
    """
    User model for authentication.
    
    Table already created in database with these columns.
    """
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, nullable=False, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(100))
    is_active = Column(Boolean, default=True)
    is_verified = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    def to_dict(self):
        """Convert user to dictionary (without password!)"""
        return {
            "id": self.id,
            "username": self.username,
            "email": self.email,
            "full_name": self.full_name,
            "is_active": self.is_active,
            "is_verified": self.is_verified,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }


class PasswordResetOTP(Base):
    """
    OTP model for password reset.
    
    Table already created in database.
    """
    __tablename__ = "password_reset_otps"
    
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), nullable=False, index=True)
    otp_code = Column(String(6), nullable=False)
    is_used = Column(Boolean, default=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class APIKey(Base):
    """
    API Key model for gateway authentication.
    
    Why API Keys?
    - JWT tokens expire every hour → annoying for IoT gateways
    - API keys can be set to never expire (or custom duration)
    - Easier for friends/partners to test your system
    - Industry standard (like Thingspeak, Adafruit IO, AWS IoT)
    
    Format: lora_<44 random characters>
    Example: lora_ABC123xyz...
    """
    __tablename__ = "api_keys"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    key_name = Column(String(100), nullable=False)  # e.g., "Gateway 1", "Test Key"
    key_value = Column(String(100), unique=True, nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    last_used_at = Column(DateTime(timezone=True), nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=True)  # NULL = never expires
    is_active = Column(Boolean, default=True)
    
    def to_dict(self, show_full_key=False):
        """Convert to dictionary (hides full key by default for security)"""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "key_name": self.key_name,
            "key_preview": self.key_value[:10] + "..." if not show_full_key else self.key_value,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "last_used_at": self.last_used_at.isoformat() if self.last_used_at else None,
            "expires_at": self.expires_at.isoformat() if self.expires_at else "Never",
            "is_active": self.is_active
        }
