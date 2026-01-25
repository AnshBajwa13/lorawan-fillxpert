"""
Pydantic schemas for authentication requests and responses
"""
from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List
from datetime import datetime
from enum import Enum


class APIKeyExpiration(str, Enum):
    """Options for API key expiration"""
    never = "never"          # Default - best for production gateways
    one_year = "1_year"      # 365 days
    thirty_days = "30_days"  # 30 days
    seven_days = "7_days"    # 7 days (for testing)
    custom = "custom"        # User provides custom datetime


class UserRegister(BaseModel):
    """Request schema for user registration"""
    username: str = Field(..., min_length=3, max_length=50)
    email: EmailStr
    password: str = Field(..., min_length=6, max_length=100)
    full_name: Optional[str] = Field(None, max_length=100)


class UserLogin(BaseModel):
    """Request schema for user login"""
    email: EmailStr
    password: str


class Token(BaseModel):
    """Response schema for token"""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class TokenData(BaseModel):
    """Data stored in JWT token"""
    email: Optional[str] = None


class UserResponse(BaseModel):
    """Response schema for user data (no password!)"""
    id: int
    username: str
    email: str
    full_name: Optional[str]
    is_active: bool
    is_verified: bool
    created_at: datetime
    
    class Config:
        from_attributes = True


class PasswordReset(BaseModel):
    """Request schema for password reset"""
    email: EmailStr


class PasswordResetConfirm(BaseModel):
    """Request schema for password reset confirmation"""
    email: EmailStr
    otp_code: str = Field(..., min_length=6, max_length=6)
    new_password: str = Field(..., min_length=6, max_length=100)


# ============ API KEY SCHEMAS ============

class APIKeyCreate(BaseModel):
    """Request schema for creating an API key"""
    key_name: str = Field(..., min_length=1, max_length=100, description="Name for the key (e.g., 'Gateway 1')")
    expiration: APIKeyExpiration = Field(default=APIKeyExpiration.never, description="When the key expires")
    custom_expires_at: Optional[datetime] = Field(None, description="Custom expiration date (only if expiration='custom')")


class APIKeyResponse(BaseModel):
    """Response schema when creating an API key (shows full key ONCE)"""
    id: int
    key_name: str
    key_value: str  # Full key shown only at creation!
    expires_at: Optional[str]
    message: str = "Save this key! It won't be shown again."


class APIKeyListItem(BaseModel):
    """Single API key in list (hides full key)"""
    id: int
    key_name: str
    key_preview: str  # Only first 10 chars + "..."
    created_at: datetime
    last_used_at: Optional[datetime]
    expires_at: Optional[str]
    is_active: bool


class APIKeyList(BaseModel):
    """Response schema for listing API keys"""
    keys: List[APIKeyListItem]
    total: int
