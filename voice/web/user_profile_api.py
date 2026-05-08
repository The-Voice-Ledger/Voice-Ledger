"""
User Profile API

Provides endpoints for:
- Fetching user profile (with language preference)
- Updating language preference
- User settings management

Date: December 24, 2025
Lab 17: Bilingual Voice UI - Track 2
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from database.connection import get_db
from database.models import UserIdentity, PendingRegistration
from voice.web.auth import get_current_user, get_current_user_flexible
import logging

logger = logging.getLogger(__name__)

router = APIRouter()


# ============================================================
# PYDANTIC MODELS
# ============================================================

class UserProfileResponse(BaseModel):
    id: int
    name: str
    phone_number: Optional[str]
    role: str
    preferred_language: str
    is_approved: bool
    organization: Optional[str]
    telegram_user_id: Optional[str]


class LanguageUpdateRequest(BaseModel):
    language: str  # 'en' or 'am'


class LanguageUpdateResponse(BaseModel):
    success: bool
    message: str
    language: str


# ============================================================
# USER PROFILE
# ============================================================

@router.get("/api/users/me/profile", response_model=UserProfileResponse)
def get_my_profile(user: UserIdentity = Depends(get_current_user_flexible)):
    """
    Get current user's profile including language preference.
    
    Supports both JWT (web) and Telegram ID (mini apps) authentication.
    Used by voice UI to know which provider to use (AddisAI vs OpenAI).
    """
    # Get organization from UserIdentity.organization first, then fallback to PendingRegistration
    organization_name = None
    if user.organization:
        organization_name = user.organization.name
    else:
        # Try to get organization from PendingRegistration (for farmers who haven't been linked to Organization yet)
        with get_db() as db:
            try:
                # Handle both numeric and string telegram_user_id
                telegram_id_int = int(user.telegram_user_id)
                pending_reg = db.query(PendingRegistration).filter(
                    PendingRegistration.telegram_user_id == telegram_id_int
                ).first()
                if pending_reg and pending_reg.organization_name:
                    organization_name = pending_reg.organization_name
            except (ValueError, TypeError):
                # If not numeric, skip PendingRegistration lookup
                pass
    
    return UserProfileResponse(
        id=user.id,
        name=f"{user.telegram_first_name} {user.telegram_last_name or ''}".strip(),
        phone_number=user.phone_number,
        role=user.role,
        preferred_language=user.preferred_language,
        is_approved=user.is_approved,
        organization=organization_name,
        telegram_user_id=str(user.telegram_user_id) if user.telegram_user_id else None
    )


@router.patch("/api/users/me/language", response_model=LanguageUpdateResponse)
def update_my_language(
    request: LanguageUpdateRequest,
    user: UserIdentity = Depends(get_current_user)
):
    """
    Update user's language preference.
    
    This affects:
    - Voice provider routing (AddisAI for 'am', OpenAI for 'en')
    - Telegram bot responses
    - Web UI text direction and content
    
    Args:
        language: 'en' (English) or 'am' (Amharic)
    """
    if request.language not in ['en', 'am']:
        raise HTTPException(
            status_code=400,
            detail="Invalid language. Must be 'en' or 'am'"
        )
    
    with get_db() as db:
        # Re-fetch user in this session
        db_user = db.query(UserIdentity).filter_by(id=user.id).first()
        if not db_user:
            raise HTTPException(status_code=404, detail="User not found")
        
        old_language = db_user.preferred_language
        db_user.preferred_language = request.language
        db_user.language_set_at = datetime.utcnow()
        db.commit()
        
        logger.info(
            f"User {user.id} changed language: {old_language} → {request.language}"
        )
        
        return LanguageUpdateResponse(
            success=True,
            message=f"Language updated to {'English' if request.language == 'en' else 'Amharic'}",
            language=request.language
        )


@router.get("/api/users/{user_id}/profile", response_model=UserProfileResponse)
def get_user_profile(
    user_id: int,
    current_user: UserIdentity = Depends(get_current_user)
):
    """
    Get another user's profile (admin or self only).
    """
    # Allow admins to view any profile, or users to view their own
    if current_user.role != 'ADMIN' and current_user.id != user_id:
        raise HTTPException(
            status_code=403,
            detail="You can only view your own profile"
        )
    
    with get_db() as db:
        user = db.query(UserIdentity).filter_by(id=user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        # Get organization from UserIdentity.organization first, then fallback to PendingRegistration
        organization_name = None
        if user.organization:
            organization_name = user.organization.name
        else:
            # Try to get organization from PendingRegistration (for farmers who haven't been linked to Organization yet)
            try:
                # Handle both numeric and string telegram_user_id
                telegram_id_int = int(user.telegram_user_id)
                pending_reg = db.query(PendingRegistration).filter(
                    PendingRegistration.telegram_user_id == telegram_id_int
                ).first()
                if pending_reg and pending_reg.organization_name:
                    organization_name = pending_reg.organization_name
            except (ValueError, TypeError):
                # If not numeric, skip PendingRegistration lookup
                pass
        
        return UserProfileResponse(
            id=user.id,
            name=f"{user.telegram_first_name} {user.telegram_last_name or ''}".strip(),
            phone_number=user.phone_number,
            role=user.role,
            preferred_language=user.preferred_language,
            is_approved=user.is_approved,
            organization=organization_name,
            telegram_user_id=str(user.telegram_user_id) if user.telegram_user_id else None
        )
