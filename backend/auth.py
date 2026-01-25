"""
Authentication utilities for JWT token generation and password hashing
"""
from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from database import get_db
from models_auth import User

# Password hashing configuration
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# JWT configuration
SECRET_KEY = "your-secret-key-change-this-in-production-use-env-variable"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60  # 1 hour
REFRESH_TOKEN_EXPIRE_DAYS = 7  # 7 days

# Security scheme for bearer token
security = HTTPBearer()
security_optional = HTTPBearer(auto_error=False)  # For optional auth


def hash_password(password: str) -> str:
    """
    Hash a plain text password using bcrypt.
    
    Example:
    password = "mypassword123"
    hashed = hash_password(password)
    # Result: "$2b$12$KIXxZq5..."  (60 characters, random salt included)
    
    How it works:
    1. Bcrypt generates a random "salt" (random data)
    2. Combines salt + password
    3. Runs through bcrypt algorithm (very slow on purpose)
    4. Returns hash that includes: algorithm version + cost factor + salt + hash
    """
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify if a plain text password matches the hashed password.
    
    Example:
    plain = "mypassword123"
    hashed = "$2b$12$KIXxZq5..."  (from database)
    is_valid = verify_password(plain, hashed)
    # Result: True if password matches, False if not
    
    How it works:
    1. Extracts the salt from the hashed password (first 29 chars)
    2. Hashes the plain_password with the SAME salt
    3. Compares the new hash with the stored hash
    4. Returns True if they match, False otherwise
    
    Security:
    - Bcrypt is intentionally SLOW (takes ~100-300ms)
    - This prevents brute-force attacks
    - Each password has a unique salt
    - Same password creates different hashes
    """
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """
    Create a JWT access token.
    
    JWT Structure:
    - Header: {"alg": "HS256", "typ": "JWT"}
    - Payload: {"sub": "user@example.com", "exp": 1234567890}
    - Signature: HMACSHA256(header + payload, SECRET_KEY)
    
    Final token: "eyJhbGci...eyJzdWI...SflKxwRJ"
    """
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def create_refresh_token(data: dict) -> str:
    """Create a JWT refresh token (longer expiration)."""
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def decode_token(token: str) -> dict:
    """
    Decode and verify a JWT token.
    
    Verification steps:
    1. Check signature is valid (using SECRET_KEY)
    2. Check token hasn't expired
    3. Extract payload data
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> User:
    """
    Dependency to get the current authenticated user.
    
    Usage in endpoint:
    @app.get("/api/protected")
    def protected_route(current_user: User = Depends(get_current_user)):
        return {"message": f"Hello {current_user.username}"}
    
    Flow:
    1. Extract token from Authorization header: "Bearer <token>"
    2. Decode and verify token
    3. Get user email from token payload
    4. Query database for user
    5. Return user object
    """
    token = credentials.credentials
    payload = decode_token(token)
    email: str = payload.get("sub")
    
    if email is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials"
        )
    
    user = db.query(User).filter(User.email == email).first()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found"
        )
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive user"
        )
    
    return user


def get_current_user_optional(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_optional),
    db: Session = Depends(get_db)
) -> Optional[User]:
    """
    Optional version of get_current_user.
    Returns None instead of raising an exception if no token is provided.
    Used for endpoints that accept either API key OR Bearer token.
    """
    if credentials is None:
        return None
    
    try:
        token = credentials.credentials
        payload = decode_token(token)
        email: str = payload.get("sub")
        
        if email is None:
            return None
        
        user = db.query(User).filter(User.email == email).first()
        if user is None or not user.is_active:
            return None
        
        return user
    except:
        return None


def authenticate_user(db: Session, email: str, password: str) -> Optional[User]:
    """
    Authenticate a user with email and password.
    
    Process:
    1. Find user by email in database
    2. If user not found, return None
    3. If user found, verify password:
       - Get hashed_password from database
       - Hash the entered password with the SAME salt
       - Compare the hashes
    4. Return user if password matches, None otherwise
    
    Security Note:
    - We don't tell the user "wrong password" vs "email not found"
    - Both cases return None
    - This prevents attackers from knowing if an email exists
    """
    user = db.query(User).filter(User.email == email).first()
    if not user:
        return None
    if not verify_password(password, user.hashed_password):
        return None
    return user
