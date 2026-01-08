"""
Authentication API endpoints
"""
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
import random
import string

from database import get_db
from models_auth import User, PasswordResetOTP
from schemas_auth import (
    UserRegister, UserLogin, Token, UserResponse,
    PasswordReset, PasswordResetConfirm
)
from auth import (
    hash_password, verify_password, authenticate_user,
    create_access_token, create_refresh_token, get_current_user
)
from rate_limiter import limiter

router = APIRouter(prefix="/api/auth", tags=["Authentication"])


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register_user(user_data: UserRegister, db: Session = Depends(get_db)):
    """
    Register a new user.
    
    Process:
    1. Check if email already exists
    2. Check if username already exists
    3. Hash the password using bcrypt
    4. Create user in database
    5. Return user data (without password)
    """
    # Check if email exists
    existing_email = db.query(User).filter(User.email == user_data.email).first()
    if existing_email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    # Check if username exists
    existing_username = db.query(User).filter(User.username == user_data.username).first()
    if existing_username:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already taken"
        )
    
    # Hash password
    hashed_password = hash_password(user_data.password)
    
    # Create user
    new_user = User(
        username=user_data.username,
        email=user_data.email,
        hashed_password=hashed_password,
        full_name=user_data.full_name,
        is_active=True,
        is_verified=True
    )
    
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    
    return new_user


@router.post("/login", response_model=Token)
@limiter.limit("5/minute")  # 5 login attempts per minute
def login(request: Request, user_credentials: UserLogin, db: Session = Depends(get_db)):
    """
    Login with email and password.
    
    Rate Limit: 5 attempts per minute to prevent brute force attacks
    
    Process:
    1. Find user by email
    2. Verify password (compare hashes)
    3. Generate JWT access token (1 hour)
    4. Generate JWT refresh token (7 days)
    5. Return both tokens
    
    How password verification works:
    - User enters: "mypassword123"
    - Database has: "$2b$12$KIXxZq5..." (hashed with bcrypt)
    - System extracts salt from stored hash
    - System hashes entered password with SAME salt
    - System compares new hash with stored hash
    - If match → login success, generate tokens
    - If no match → login failed
    """
    user = authenticate_user(db, user_credentials.email, user_credentials.password)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Create tokens
    access_token = create_access_token(data={"sub": user.email})
    refresh_token = create_refresh_token(data={"sub": user.email})
    
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer"
    }


@router.get("/me", response_model=UserResponse)
def get_current_user_info(current_user: User = Depends(get_current_user)):
    """
    Get current authenticated user information.
    
    This endpoint is PROTECTED - requires valid JWT token.
    
    Usage:
    - Frontend sends: Authorization: Bearer <token>
    - Backend verifies token
    - Backend returns user data
    """
    return current_user


@router.post("/refresh", response_model=Token)
def refresh_token(current_user: User = Depends(get_current_user)):
    """
    Refresh access token using refresh token.
    
    When access token expires (after 1 hour):
    1. Frontend sends refresh token
    2. Backend verifies refresh token
    3. Backend generates new access token
    4. Backend generates new refresh token
    5. Frontend stores new tokens
    """
    access_token = create_access_token(data={"sub": current_user.email})
    refresh_token = create_refresh_token(data={"sub": current_user.email})
    
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer"
    }


@router.post("/password-reset/request")
@limiter.limit("3/hour")  # 3 OTP requests per hour
def request_password_reset(request: Request, data: PasswordReset, db: Session = Depends(get_db)):
    """
    Request password reset - generates OTP and sends email.
    
    Rate Limit: 3 requests per hour to prevent spam
    
    Process:
    1. Check if user exists
    2. Generate 6-digit OTP
    3. Store OTP in database with expiration (15 minutes)
    4. Send OTP via email (TODO: implement email sending)
    5. Return success message
    """
    user = db.query(User).filter(User.email == data.email).first()
    if not user:
        # Don't reveal if email exists or not (security)
        return {"message": "If the email exists, an OTP has been sent"}
    
    # Generate 6-digit OTP
    otp_code = ''.join(random.choices(string.digits, k=6))
    
    # Set expiration (15 minutes from now)
    expires_at = datetime.utcnow() + timedelta(minutes=15)
    
    # Store OTP
    otp_entry = PasswordResetOTP(
        email=data.email,
        otp_code=otp_code,
        expires_at=expires_at,
        is_used=False
    )
    db.add(otp_entry)
    db.commit()
    
    # TODO: Send OTP via email
    # For now, just print it (for testing)
    print(f"OTP for {data.email}: {otp_code}")
    
    return {"message": "If the email exists, an OTP has been sent"}


@router.post("/password-reset/confirm")
def confirm_password_reset(data: PasswordResetConfirm, db: Session = Depends(get_db)):
    """
    Confirm password reset with OTP and set new password.
    
    Process:
    1. Find OTP in database
    2. Check if OTP is valid (not expired, not used)
    3. Verify OTP code matches
    4. Hash new password
    5. Update user's password
    6. Mark OTP as used
    """
    # Find valid OTP
    otp_entry = db.query(PasswordResetOTP).filter(
        PasswordResetOTP.email == data.email,
        PasswordResetOTP.otp_code == data.otp_code,
        PasswordResetOTP.is_used == False,
        PasswordResetOTP.expires_at > datetime.utcnow()
    ).first()
    
    if not otp_entry:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired OTP"
        )
    
    # Find user
    user = db.query(User).filter(User.email == data.email).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Hash new password and update
    user.hashed_password = hash_password(data.new_password)
    
    # Mark OTP as used
    otp_entry.is_used = True
    
    db.commit()
    
    return {"message": "Password reset successful"}
