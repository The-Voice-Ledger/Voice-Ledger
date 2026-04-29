"""
LiveKit Token Endpoint — issues signed JWTs for web frontend voice sessions.

The frontend calls POST /api/livekit/token to get a room token + URL.
The token endpoint can optionally create an explicit AgentDispatch so the
voice-agent worker is guaranteed to join the room.

Use LIVEKIT_FORCE_EXPLICIT_DISPATCH=true to enable this behavior.
"""

from __future__ import annotations

import json
import logging
import os
import time
from datetime import timedelta
from typing import Optional, Union

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/livekit", tags=["LiveKit Voice"])

LIVEKIT_URL = os.getenv("LIVEKIT_URL", "")
LIVEKIT_API_KEY = os.getenv("LIVEKIT_API_KEY", "")
LIVEKIT_API_SECRET = os.getenv("LIVEKIT_API_SECRET", "")
LIVEKIT_FORCE_EXPLICIT_DISPATCH = (
    os.getenv("LIVEKIT_FORCE_EXPLICIT_DISPATCH", "false").lower() in ("1", "true", "yes")
)


async def _dispatch_agent(room_name: str) -> None:
    """Explicitly dispatch the voice-agent worker into the room."""
    try:
        from livekit.api import LiveKitAPI
        from livekit.protocol.agent_dispatch import CreateAgentDispatchRequest

        api = LiveKitAPI(
            url=LIVEKIT_URL,
            api_key=LIVEKIT_API_KEY,
            api_secret=LIVEKIT_API_SECRET,
        )
        try:
            await api.agent_dispatch.create_dispatch(
                CreateAgentDispatchRequest(room=room_name, agent_name="")
            )
            logger.info("Agent dispatched to room %s", room_name)
        finally:
            await api.aclose()
    except Exception as e:
        logger.warning("Agent dispatch failed (will rely on auto-dispatch): %s", e)


def _map_telegram_user_id(telegram_user_id: Union[str, int]) -> int:
    """Map Telegram user_id to internal UserIdentity.id.."""
    if telegram_user_id == "anonymous" or not telegram_user_id:
        return None
    
    try:
        from database.connection import get_db
        from database.models import UserIdentity
        
        with get_db() as db:
            user = db.query(UserIdentity).filter(
                UserIdentity.telegram_user_id == str(telegram_user_id)
            ).first()
            return user.id if user else None
    except Exception as e:
        logger.warning("Failed to map Telegram user_id %s: %s", telegram_user_id, e)
        return None


# ── Request / Response models ────────────────────────────────────────

class TokenRequest(BaseModel):
    user_id: Optional[Union[str, int]] = "anonymous"
    user_name: Optional[str] = "Guest"
    user_role: Optional[str] = "user"
    user_did: Optional[str] = None


class TokenResponse(BaseModel):
    token: str
    url: str
    room: str


# ── Endpoints ────────────────────────────────────────────────────────

@router.post("/token", response_model=TokenResponse)
async def create_token(req: TokenRequest):
    """Generate a signed LiveKit room token for web frontend."""
    try:
        body = req.json()
        print(f"DEBUG: Request body: {body}")
    except Exception as e:
        print(f"ERROR: Failed to parse JSON: {e}")
        raise HTTPException(422, f"Invalid JSON: {e}")
    
    # Check if request is from Telegram or not
    is_telegram = "X-Telegram-User-Id" in req.headers
    
    if not LIVEKIT_API_KEY or not LIVEKIT_API_SECRET:
        raise HTTPException(503, "LiveKit not configured")

    # Lazy import — livekit-api is only needed for token signing
    from livekit.api import AccessToken, VideoGrants  # pyright: ignore[reportMissingImports]

    # Map Telegram user_id to internal user_id
    if is_telegram:
        internal_user_id = _map_telegram_user_id(req.user_id)
    else:
        internal_user_id = req.user_id
    
    # Unique room per user session
    room_name = f"voice-{req.user_id}-{int(time.time())}"

    # Metadata the agent reads to identify the user
    # Use internal user_id for database operations, original for identity
    metadata = json.dumps({
        "name": req.user_name,
        "role": req.user_role,
        "user_id": internal_user_id,  # Use mapped internal user_id
        "original_user_id": req.user_id,  # Keep original for reference
        "user_did": req.user_did,
    })

    token = (
        AccessToken(LIVEKIT_API_KEY, LIVEKIT_API_SECRET)
        .with_identity(str(req.user_id))
        .with_name(req.user_name or "Guest")
        .with_metadata(metadata)
        .with_grants(VideoGrants(room_join=True, room=room_name))
        .with_ttl(timedelta(hours=1))
    )

    logger.info("LiveKit token issued: room=%s user=%s", room_name, req.user_id)

    # Optional dispatch mode for environments where LiveKit auto-assignment
    # is not reliably bringing the agent into newly created rooms.
    if LIVEKIT_FORCE_EXPLICIT_DISPATCH:
        await _dispatch_agent(room_name)

    return TokenResponse(
        token=token.to_jwt(),
        url=LIVEKIT_URL,
        room=room_name,
    )


@router.get("/health")
async def health():
    """Check if LiveKit credentials are configured."""
    configured = bool(LIVEKIT_API_KEY and LIVEKIT_API_SECRET and LIVEKIT_URL)
    return {"configured": configured, "url": LIVEKIT_URL if configured else None}
