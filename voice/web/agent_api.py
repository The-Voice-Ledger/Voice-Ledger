"""
Agent REST API Router

Exposes the AgentExecutor over HTTP for the web frontend SPA.

Endpoints:
  POST /api/agent/text   — Send a text message, get agent response
  POST /api/agent/voice  — Send audio file, get agent response + optional TTS
  GET  /api/agent/health — Health check

Auth model:
  - Anonymous users can use READ-only tools (browse_rfqs, query_batches, …)
  - Authenticated (JWT Bearer) users can also use WRITE tools
  - Anonymous requests get user_id=0 (guest)
"""

import os
import time
import uuid
import json
import tempfile
import logging
from typing import Optional, List, Dict, Any

from fastapi import APIRouter, UploadFile, File, Form, Header, HTTPException
from pydantic import BaseModel, Field

from voice.logging_config import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/api/agent", tags=["Agent Chat"])

# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------

class ToolCallInfo(BaseModel):
    """Serialised record of a single tool call."""
    tool_name: str
    arguments: Dict[str, Any] = {}
    success: bool
    message: str
    duration_ms: float = 0.0


class AgentTextResponse(BaseModel):
    """Structured response from the agent chat endpoint."""
    text: str = Field(..., description="Agent reply in user's language")
    response_type: str = Field(
        "text",
        description="Typed payload hint for rich UI cards: "
        "text | rfq_list | rfq_created | offer_submitted | "
        "eudr_compliance | batch_list | dpp | blockchain_status | "
        "mass_balance | verification_list | lineage | error",
    )
    data: Dict[str, Any] = Field(
        default_factory=dict,
        description="Structured data matching response_type",
    )
    audio_base64: Optional[str] = Field(
        None, description="Base64 TTS audio (when voice requested)"
    )
    transcript: Optional[str] = Field(
        None, description="ASR transcript of the user's voice input (voice endpoint only)"
    )
    tools_used: List[ToolCallInfo] = Field(default_factory=list)
    language: str = "en"
    conversation_id: Optional[str] = None
    duration_ms: float = 0.0


class TextRequest(BaseModel):
    """Body for POST /api/agent/text."""
    text: str
    language: str = "en"
    conversation_id: Optional[str] = None
    context: Optional[Dict[str, Any]] = None
    voice: bool = Field(False, description="Set true to include TTS audio in response")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# Tools that anonymous (guest) users are allowed to call
READ_TOOLS = {
    "query_batches",
    "search_knowledge",
    "browse_rfqs",
    "list_my_offers",
    "check_eudr_compliance",
    "check_mass_balance",
    "get_dpp",
    "get_container_dpp",
    "trace_lineage",
    "validate_dpp",
    "list_pending_verifications",
    "check_blockchain_anchor",
    "get_token_info",
    "verify_batch_hash",
    "check_don_attestation",
    "get_don_provenance_metrics",
    "browse_containers",
}

# Tool name → response_type mapping for rich cards
_TOOL_RESPONSE_TYPE: Dict[str, str] = {
    "browse_rfqs": "rfq_list",
    "create_rfq": "rfq_created",
    "submit_offer": "offer_submitted",
    "accept_offer": "offer_accepted",
    "list_my_offers": "offer_list",
    "check_eudr_compliance": "eudr_compliance",
    "check_mass_balance": "mass_balance",
    "query_batches": "batch_list",
    "get_dpp": "dpp",
    "get_container_dpp": "dpp",
    "trace_lineage": "lineage",
    "validate_dpp": "dpp_validation",
    "check_blockchain_anchor": "blockchain_status",
    "get_token_info": "blockchain_status",
    "verify_batch_hash": "blockchain_status",
    "list_pending_verifications": "verification_list",
    "browse_containers": "container_list",
    "purchase_container": "container_purchase",
    "check_don_attestation": "don_attestation",
    "get_don_provenance_metrics": "don_metrics",
    "request_don_attestation": "don_request",
    "browse_pools": "pool_list",
    "commit_to_pool": "pool_commitment",
    "list_my_commitments": "commitment_list",
    "confirm_payment": "payment_confirmation",
    "check_payment_status": "payment_status",
    "record_cooperative_payout": "coop_payout",
    "confirm_payment_received": "payment_receipt",
}


def _resolve_user(authorization: Optional[str]):
    """
    Return (user_id, user_did) from JWT token, or (0, None) for guests.
    """
    if not authorization or not authorization.startswith("Bearer "):
        return 0, None

    try:
        from voice.web.auth import verify_jwt_token
        payload = verify_jwt_token(authorization.replace("Bearer ", ""))
        user_id = payload.get("user_id", 0)
        user_did = payload.get("did")
        return user_id, user_did
    except Exception:
        return 0, None


def _infer_response_type(tool_calls) -> tuple:
    """
    Infer response_type and structured data from agent tool calls.
    Returns (response_type, data_dict).
    """
    if not tool_calls:
        return "text", {}

    # Use the last successful tool call for the card type
    for tc in reversed(tool_calls):
        if tc.success:
            rtype = _TOOL_RESPONSE_TYPE.get(tc.tool_name, "text")
            return rtype, tc.result_data
    return "text", {}


async def _generate_tts(text: str, language: str) -> Optional[str]:
    """Generate TTS audio and return base64 string, or None on failure."""
    try:
        from voice.tts.tts_provider import TTSProvider
        import base64

        provider = TTSProvider()
        audio_bytes = await provider.text_to_speech(text, language)
        if audio_bytes:
            return base64.b64encode(audio_bytes).decode("utf-8")
    except Exception as e:
        logger.warning(f"TTS generation failed: {e}")
    return None


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/health")
async def agent_health():
    """Health check for the agent chat subsystem."""
    from voice.agent.executor import AgentExecutor
    try:
        _ = AgentExecutor()
        return {"status": "ok", "agent": "ready"}
    except Exception as e:
        return {"status": "degraded", "error": str(e)}


@router.post("/text", response_model=AgentTextResponse)
async def agent_text(
    body: TextRequest,
    authorization: Optional[str] = Header(None),
):
    """
    Send a text message to the agent and receive a structured response.

    Anonymous users can call READ tools; authenticated users get full access.
    Set `voice: true` in the body to receive base64 TTS audio alongside text.
    """
    from voice.agent.executor import AgentExecutor
    import asyncio

    user_id, user_did = _resolve_user(authorization)
    conversation_id = body.conversation_id or str(uuid.uuid4())

    start = time.time()

    executor = AgentExecutor()

    # Run sync executor in a thread so we don't block the event loop
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(
        None,
        lambda: executor.run(
            transcript=body.text,
            user_id=user_id,
            user_did=user_did,
            language=body.language,
            context=body.context,
        ),
    )

    # Build tool call summaries
    tools_used = [
        ToolCallInfo(
            tool_name=tc.tool_name,
            arguments=tc.arguments,
            success=tc.success,
            message=tc.result_message,
            duration_ms=tc.duration_ms,
        )
        for tc in result.tool_calls
    ]

    response_type, data = _infer_response_type(result.tool_calls)

    # Optional TTS
    audio_b64 = None
    if body.voice:
        audio_b64 = await _generate_tts(result.response, body.language)

    elapsed = (time.time() - start) * 1000

    return AgentTextResponse(
        text=result.response,
        response_type=response_type,
        data=data,
        audio_base64=audio_b64,
        tools_used=tools_used,
        language=body.language,
        conversation_id=conversation_id,
        duration_ms=elapsed,
    )


@router.post("/voice", response_model=AgentTextResponse)
async def agent_voice(
    audio: UploadFile = File(...),
    language: str = Form("en"),
    conversation_id: Optional[str] = Form(None),
    context: Optional[str] = Form(None),
    authorization: Optional[str] = Header(None),
):
    """
    Send an audio recording to the agent.

    Pipeline: ASR → Agent → TTS (always returns audio for voice mode).
    """
    from voice.agent.executor import AgentExecutor
    from voice.asr.asr_infer import run_asr_with_user_preference
    from voice.audio_utils import validate_and_convert_audio, cleanup_temp_file
    import asyncio

    user_id, user_did = _resolve_user(authorization)
    conversation_id = conversation_id or str(uuid.uuid4())

    start = time.time()

    # --- 1. Save uploaded audio to a temp file ---
    suffix = os.path.splitext(audio.filename or "audio.webm")[1] or ".webm"
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    try:
        content = await audio.read()
        tmp.write(content)
        tmp.close()

        # --- 2. Convert & validate audio ---
        wav_path = validate_and_convert_audio(tmp.name)

        # --- 3. ASR (sync, in thread) ---
        loop = asyncio.get_event_loop()
        asr_result = await loop.run_in_executor(
            None,
            lambda: run_asr_with_user_preference(wav_path, language),
        )
        transcript = asr_result.get("transcript", "")
        detected_lang = asr_result.get("language", language)

        if not transcript.strip():
            return AgentTextResponse(
                text="I couldn't understand the audio. Could you try again?",
                response_type="error",
                language=language,
                conversation_id=conversation_id,
                duration_ms=(time.time() - start) * 1000,
            )

        # --- 4. Agent (sync, in thread) ---
        ctx = json.loads(context) if context else None
        executor = AgentExecutor()
        result = await loop.run_in_executor(
            None,
            lambda: executor.run(
                transcript=transcript,
                user_id=user_id,
                user_did=user_did,
                language=detected_lang,
                context=ctx,
            ),
        )

        # --- 5. TTS ---
        audio_b64 = await _generate_tts(
            result.response_spoken or result.response,
            detected_lang,
        )

        # Build response
        tools_used = [
            ToolCallInfo(
                tool_name=tc.tool_name,
                arguments=tc.arguments,
                success=tc.success,
                message=tc.result_message,
                duration_ms=tc.duration_ms,
            )
            for tc in result.tool_calls
        ]
        response_type, data = _infer_response_type(result.tool_calls)
        elapsed = (time.time() - start) * 1000

        return AgentTextResponse(
            text=result.response,
            response_type=response_type,
            data=data,
            audio_base64=audio_b64,
            transcript=transcript,
            tools_used=tools_used,
            language=detected_lang,
            conversation_id=conversation_id,
            duration_ms=elapsed,
        )

    finally:
        # Clean up temp files
        cleanup_temp_file(tmp.name)
        if "wav_path" in dir() and wav_path != tmp.name:
            cleanup_temp_file(wav_path)
