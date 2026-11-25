import os
import time
import datetime
from typing import Optional
import bcrypt
import jwt
from fastapi import HTTPException, Security, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

SECRET_KEY = os.getenv("JWT_SECRET", "pulsetask-saas-enterprise-secret-key-2026")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_DAYS = 30

security = HTTPBearer(auto_error=False)

def hash_password(password: str) -> str:
    """Hash a plaintext password using bcrypt with automatic salt"""
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plaintext password against the stored bcrypt hash"""
    try:
        return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))
    except Exception:
        return False

def create_access_token(user_id: str, email: str, name: Optional[str] = None) -> str:
    """Generate a JWT access token expiring in 30 days"""
    expire = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=ACCESS_TOKEN_EXPIRE_DAYS)
    payload = {
        "sub": user_id,
        "email": email,
        "name": name or "",
        "exp": expire,
        "iat": datetime.datetime.now(datetime.timezone.utc)
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

def decode_access_token(token: str) -> Optional[dict]:
    """Decode and validate a JWT access token"""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except Exception:
        return None

def get_current_user_optional(credentials: Optional[HTTPAuthorizationCredentials] = Security(security)) -> Optional[dict]:
    """Extract current user if Authorization: Bearer token is provided, otherwise None"""
    if not credentials or not credentials.credentials:
        return None
    payload = decode_access_token(credentials.credentials)
    if not payload or "sub" not in payload:
        return None
    return {
        "id": payload["sub"],
        "email": payload.get("email"),
        "name": payload.get("name")
    }

def get_current_user_required(credentials: Optional[HTTPAuthorizationCredentials] = Security(security)) -> dict:
    """Extract current user, raising HTTP 401 Unauthorized if not authenticated"""
    user = get_current_user_optional(credentials)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required. Please log in.",
            headers={"WWW-Authenticate": "Bearer"}
        )
    return user
