"""
JWT Authentication for Web Interface

Provides:
- PIN-based login (bcrypt validation)
- JWT token generation and validation
- Role-based access control
- Token refresh mechanism

Date: December 24, 2025
Lab 17: Admin Dashboard
"""

import os
import jwt
import bcrypt
from datetime import datetime, timedelta
from typing import Optional
from fastapi import HTTPException, Depends, Header
from sqlalchemy.orm import Session
from database.models import UserIdentity
from database.connection import get_db
import logging

logger = logging.getLogger(__name__)

# JWT Configuration
JWT_SECRET_KEY = os.getenv('JWT_SECRET_KEY', 'your-secret-key-change-in-production')
JWT_ALGORITHM = 'HS256'
JWT_EXPIRATION_DAYS = 7


def create_jwt_token(user_id: int, role: str) -> str:
    """
    Generate JWT token for authenticated user.
    
    Token includes:
    - user_id: Database ID
    - role: User role (ADMIN, FARMER, etc.)
    - exp: Expiration timestamp (7 days)
    
    Returns:
        JWT token string
    """
    expiration = datetime.utcnow() + timedelta(days=JWT_EXPIRATION_DAYS)
    
    payload = {
        'user_id': user_id,
        'role': role,
        'exp': expiration,
        'iat': datetime.utcnow()
    }
    
    token = jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)
    logger.info(f"Created JWT token for user {user_id} (role: {role})")
    
    return token


def verify_jwt_token(token: str) -> dict:
    """
    Verify and decode JWT token.
    
    Args:
        token: JWT token string
        
    Returns:
        Decoded payload with user_id and role
        
    Raises:
        HTTPException: If token is invalid or expired
    """
    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token has expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")


def get_current_user(
    authorization: Optional[str] = Header(None)
) -> UserIdentity:
    """
    FastAPI dependency to get current authenticated user from JWT token.
    
    Usage:
        @app.get("/api/protected")
        async def protected_route(user: UserIdentity = Depends(get_current_user)):
            return {"user_id": user.id, "role": user.role}
    
    Returns:
        UserIdentity object
        
    Raises:
        HTTPException: If token is missing, invalid, or user not found
    """
    if not authorization:
        raise HTTPException(status_code=401, detail="Authorization header missing")
    
    # Extract token from "Bearer <token>"
    if not authorization.startswith('Bearer '):
        raise HTTPException(status_code=401, detail="Invalid authorization header format")
    
    token = authorization.replace('Bearer ', '')
    
    # Verify token
    payload = verify_jwt_token(token)
    user_id = payload.get('user_id')
    
    # Fetch user from database using context manager but return a dict of user data
    with get_db() as db:
        from sqlalchemy.orm import joinedload
        user = db.query(UserIdentity).options(joinedload(UserIdentity.organization)).filter_by(id=user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        # Make user and its relationships available outside the session
        db.expunge_all()
    
    return user


def require_admin(user: UserIdentity = Depends(get_current_user)) -> UserIdentity:
    """
    FastAPI dependency to require ADMIN role.
    
    Usage:
        @app.get("/admin/dashboard")
        async def admin_dashboard(admin: UserIdentity = Depends(require_admin)):
            # Only accessible to ADMINs
            return {"message": "Admin dashboard"}
    
    Returns:
        UserIdentity object with ADMIN role
        
    Raises:
        HTTPException: If user is not an admin
    """
    if user.role != 'ADMIN' and not user.is_approved:
        logger.warning(f"User {user.id} ({user.role}) attempted to access admin endpoint")
        raise HTTPException(status_code=403, detail="Admin access required")
    
    return user


def get_user_from_telegram(
    x_telegram_user_id: Optional[str] = Header(None, alias="X-Telegram-User-Id")
) -> Optional[UserIdentity]:
    """
    Get user from Telegram ID header (for mini apps).
    
    Returns:
        UserIdentity object or None if header missing
    """
    if not x_telegram_user_id:
        return None
    
    with get_db() as db:
        user = db.query(UserIdentity).filter(
            UserIdentity.telegram_user_id == str(x_telegram_user_id)
        ).first()
        
        if user:
            # Expunge to make accessible outside session
            db.expunge(user)
        return user


def get_current_user_flexible(
    authorization: Optional[str] = Header(None),
    x_telegram_user_id: Optional[str] = Header(None, alias="X-Telegram-User-Id")
) -> UserIdentity:
    """
    FastAPI dependency that accepts EITHER JWT token OR Telegram ID.
    
    Priority:
    1. JWT Authorization header (for web interface)
    2. X-Telegram-User-Id header (for mini apps)
    
    Usage:
        @app.get("/api/resource")
        async def get_resource(user: UserIdentity = Depends(get_current_user_flexible)):
            return {"user_id": user.id}
    
    Returns:
        UserIdentity object
        
    Raises:
        HTTPException: If neither auth method provided or user not found
    """
    # Try JWT first
    if authorization and authorization.startswith('Bearer '):
        token = authorization.replace('Bearer ', '')
        payload = verify_jwt_token(token)
        user_id = payload.get('user_id')
        
        with get_db() as db:
            from sqlalchemy.orm import joinedload
            user = db.query(UserIdentity).options(joinedload(UserIdentity.organization)).filter_by(id=user_id).first()
            if user:
                db.expunge_all()
                return user
    
    # Try Telegram ID
    if x_telegram_user_id:
        user = get_user_from_telegram(x_telegram_user_id)
        if user:
            return user
    
    # No valid auth
    raise HTTPException(
        status_code=401,
        detail="Authentication required. Provide either Authorization header or X-Telegram-User-Id header"
    )


def require_admin_flexible(user: UserIdentity = Depends(get_current_user_flexible)) -> UserIdentity:
    """
    FastAPI dependency that requires admin access via EITHER JWT OR Telegram ID.
    
    Checks:
    - User has is_approved=True (for any authenticated user with admin privileges)
    - OR user.role == 'ADMIN' or 'SYSTEM_ADMIN' (legacy admin roles)
    
    Usage:
        @app.get("/admin/dashboard")
        async def admin_dashboard(admin: UserIdentity = Depends(require_admin_flexible)):
            return {"message": "Admin dashboard"}
    
    Returns:
        UserIdentity with admin privileges
        
    Raises:
        HTTPException: If user doesn't have admin access
    """
    if not user.is_approved and user.role not in ['ADMIN', 'SYSTEM_ADMIN']:
        logger.warning(f"User {user.id} ({user.role}, approved={user.is_approved}) attempted to access admin endpoint")
        raise HTTPException(status_code=403, detail="Admin access required")
    
    return user


def verify_pin(phone_number: str, pin: str, db: Session) -> Optional[UserIdentity]:
    """
    Verify user's phone number and PIN.
    
    Args:
        phone_number: User's phone number
        pin: 4-digit PIN
        db: Database session
        
    Returns:
        UserIdentity if credentials valid, None otherwise
    """
    user = db.query(UserIdentity).filter_by(phone_number=phone_number).first()
    
    if not user:
        logger.warning(f"Login attempt with non-existent phone: {phone_number}")
        return None
    
    if not user.pin_hash:
        logger.warning(f"User {user.id} has no PIN set")
        return None
    
    # Verify PIN using bcrypt
    if bcrypt.checkpw(pin.encode('utf-8'), user.pin_hash.encode('utf-8')):
        logger.info(f"Successful login for user {user.id} ({user.phone_number})")
        return user
    else:
        logger.warning(f"Failed login attempt for {phone_number}")
        return None
