"""
LiveKit Voice Agent Worker for Voice Ledger.

Runs as a standalone process that connects to LiveKit Cloud and handles
real-time voice sessions for the web frontend.

Usage:
  python -m voice.livekit_agent dev    # local development
  python -m voice.livekit_agent start  # production (Railway)
"""

from __future__ import annotations

# ── Railway / container environment fixes ────────────────────────────
# Must be set BEFORE any LiveKit imports to prevent thread/OTEL crashes
import os

if os.environ.get("RAILWAY_ENVIRONMENT") or os.environ.get("RAILWAY_SERVICE_NAME"):
    os.environ.setdefault("LIVEKIT_WORKERS", "1")
    os.environ.setdefault("OTEL_SDK_DISABLED", "true")
    os.environ.setdefault("OTEL_EXPORTER_OTLP_ENDPOINT", "")
    os.environ.setdefault("LIVEKIT_OTEL_ENABLED", "false")
    os.environ.setdefault("PYTHONUNBUFFERED", "1")
    os.environ.setdefault("TOKIO_WORKER_THREADS", "1")
    os.environ.setdefault("RAYON_NUM_THREADS", "1")
    os.environ.setdefault("NUMBA_NUM_THREADS", "1")

import json
import logging
import time
import uuid
from typing import Annotated

from dotenv import load_dotenv
from openai import OpenAI as OpenAIClient

load_dotenv()

from livekit import agents  # pyright: ignore[reportMissingImports]
from livekit.agents import (  # pyright: ignore[reportMissingImports]
    Agent,
    AgentSession,
    RunContext,
    cli,
    function_tool,
    room_io,
)
from livekit.plugins import deepgram, openai, silero  # pyright: ignore[reportMissingImports]

try:
    from livekit.plugins import google as lk_google  # pyright: ignore[reportMissingImports]
except Exception:  # pragma: no cover - optional dependency in some environments
    lk_google = None

logger = logging.getLogger("voice-ledger-agent")

# ── Action card topic ────────────────────────────────────────────────
ACTION_TOPIC = "vl.action"


# ── LLM/TTS provider selection (OpenAI primary, Gemini fallback) ─────
_GEMINI_OPENAI_BASE_URL = os.getenv(
    "GEMINI_OPENAI_BASE_URL",
    "https://generativelanguage.googleapis.com/v1beta/openai/",
)

_OPENAI_CIRCUIT_OPEN_UNTIL = 0.0


def _openai_healthcheck_enabled() -> bool:
    return os.getenv("LIVEKIT_OPENAI_HEALTHCHECK", "true").lower() in ("1", "true", "yes")


def _fallback_enabled() -> bool:
    return os.getenv("LLM_FALLBACK_ENABLED", "true").lower() in ("1", "true", "yes")


def _livekit_llm_provider_mode() -> str:
    """
    Provider selection mode for LiveKit sessions.
    Supported: auto (default), openai, gemini.
    """
    mode = os.getenv("LIVEKIT_LLM_PROVIDER", "auto").strip().lower()
    if mode in {"auto", "openai", "gemini"}:
        return mode
    logger.warning("Invalid LIVEKIT_LLM_PROVIDER=%s, falling back to auto", mode)
    return "auto"


def _livekit_tts_provider_mode() -> str:
    """
    TTS provider mode for LiveKit sessions.
    Supported: auto (default), openai, deepgram.
    """
    mode = os.getenv("LIVEKIT_TTS_PROVIDER", "auto").strip().lower()
    if mode in {"auto", "openai", "deepgram"}:
        return mode
    logger.warning("Invalid LIVEKIT_TTS_PROVIDER=%s, falling back to auto", mode)
    return "auto"


def _openai_circuit_open() -> bool:
    return time.time() < _OPENAI_CIRCUIT_OPEN_UNTIL


def _trip_openai_circuit(reason: str) -> None:
    global _OPENAI_CIRCUIT_OPEN_UNTIL
    ttl_sec = int(os.getenv("LIVEKIT_OPENAI_CIRCUIT_TTL_SEC", "900"))
    _OPENAI_CIRCUIT_OPEN_UNTIL = time.time() + max(1, ttl_sec)
    logger.warning(
        "OpenAI circuit opened for %ss (%s). New sessions will prefer Gemini.",
        ttl_sec,
        reason,
    )


def _clear_openai_circuit() -> None:
    global _OPENAI_CIRCUIT_OPEN_UNTIL
    _OPENAI_CIRCUIT_OPEN_UNTIL = 0.0


def _is_retryable_openai_error(exc: Exception) -> bool:
    text = str(exc).lower()
    status_code = getattr(exc, "status_code", None)
    if isinstance(status_code, int):
        if status_code in (408, 409, 429):
            return True
        if status_code >= 500:
            return True
    keywords = (
        "insufficient_quota",
        "quota",
        "billing",
        "rate limit",
        "timeout",
        "connection",
        "service unavailable",
        "internal server error",
    )
    return any(k in text for k in keywords)


def _openai_llm_healthy() -> bool:
    """
    Lightweight health check to decide whether to route LiveKit LLM to OpenAI.
    If OpenAI is down/quota-limited, session falls back to Gemini.
    """
    openai_key = os.getenv("OPENAI_API_KEY")
    if not openai_key:
        return False
    if _openai_circuit_open():
        logger.info("OpenAI circuit is open; treating OpenAI as unhealthy for this session")
        return False
    if not _openai_healthcheck_enabled():
        return True

    model = os.getenv("LIVEKIT_OPENAI_HEALTHCHECK_MODEL", "gpt-4o-mini")
    try:
        client = OpenAIClient(api_key=openai_key, timeout=8.0, max_retries=0)
        client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": "ok"}],
            max_tokens=1,
            temperature=0,
        )
        _clear_openai_circuit()
        return True
    except Exception as e:
        if _is_retryable_openai_error(e):
            logger.warning("OpenAI health check failed (retryable): %s", e)
            return False
        # Non-retryable errors should still fail closed for safety.
        logger.warning("OpenAI health check failed (non-retryable): %s", e)
        return False


def _build_livekit_llm():
    """
    Returns: (llm_instance, provider_name, model_name)
    """
    openai_model = os.getenv("LIVEKIT_OPENAI_MODEL", "gpt-4o-mini")
    gemini_model = os.getenv("LIVEKIT_GEMINI_MODEL", "gemini-2.5-flash")
    temperature = float(os.getenv("LIVEKIT_LLM_TEMPERATURE", "0.2"))
    mode = _livekit_llm_provider_mode()

    logger.info("LiveKit LLM provider mode=%s", mode)

    if mode == "gemini":
        if os.getenv("GEMINI_API_KEY"):
            if lk_google is not None:
                llm = lk_google.LLM(
                    model=gemini_model,
                    api_key=os.getenv("GEMINI_API_KEY"),
                    temperature=temperature,
                )
                return llm, "gemini", gemini_model

            logger.warning("livekit.plugins.google unavailable; using OpenAI-compatible Gemini endpoint")
            llm = openai.LLM(
                model=gemini_model,
                api_key=os.getenv("GEMINI_API_KEY"),
                base_url=_GEMINI_OPENAI_BASE_URL,
                temperature=temperature,
            )
            return llm, "gemini", gemini_model
        logger.warning("LIVEKIT_LLM_PROVIDER=gemini but GEMINI_API_KEY is missing; using OpenAI")

    if mode == "openai":
        llm = openai.LLM(model=openai_model, temperature=temperature)
        return llm, "openai", openai_model

    if _openai_llm_healthy():
        llm = openai.LLM(model=openai_model, temperature=temperature)
        return llm, "openai", openai_model

    if _fallback_enabled() and os.getenv("GEMINI_API_KEY"):
        if lk_google is not None:
            llm = lk_google.LLM(
                model=gemini_model,
                api_key=os.getenv("GEMINI_API_KEY"),
                temperature=temperature,
            )
        else:
            logger.warning("livekit.plugins.google unavailable; using OpenAI-compatible Gemini endpoint")
            llm = openai.LLM(
                model=gemini_model,
                api_key=os.getenv("GEMINI_API_KEY"),
                base_url=_GEMINI_OPENAI_BASE_URL,
                temperature=temperature,
            )
        return llm, "gemini", gemini_model

    # Last-resort path if Gemini key is absent: keep OpenAI configured.
    llm = openai.LLM(model=openai_model, temperature=temperature)
    return llm, "openai", openai_model


def _build_livekit_tts(provider_name: str):
    """
    Keep voice output functional during Gemini fallback by using Deepgram TTS.
    """
    tts_mode = _livekit_tts_provider_mode()
    deepgram_key = os.getenv("DEEPGRAM_API_KEY")
    deepgram_tts_model = os.getenv("LIVEKIT_DEEPGRAM_TTS_MODEL", "aura-2-andromeda-en")

    use_deepgram = False
    if tts_mode == "deepgram":
        use_deepgram = True
    elif tts_mode == "auto":
        # In fallback-capable deployments, keep voice output independent from OpenAI credits.
        use_deepgram = bool(deepgram_key) and (provider_name == "gemini" or _fallback_enabled())

    if use_deepgram:
        if deepgram_key:
            return deepgram.TTS(model=deepgram_tts_model, api_key=deepgram_key)
        logger.warning("Deepgram TTS selected but DEEPGRAM_API_KEY missing; falling back to OpenAI TTS")

    openai_tts_model = os.getenv("LIVEKIT_OPENAI_TTS_MODEL", "tts-1")
    openai_tts_voice = os.getenv("LIVEKIT_OPENAI_TTS_VOICE", "nova")
    return openai.TTS(model=openai_tts_model, voice=openai_tts_voice)


def _maybe_trip_openai_circuit_from_exception(exc: Exception, llm_provider: str) -> None:
    if llm_provider != "openai" or not _fallback_enabled() or not os.getenv("GEMINI_API_KEY"):
        return
    if _is_retryable_openai_error(exc):
        _trip_openai_circuit(str(exc))


async def _send_action_card(ctx: RunContext, card: dict) -> None:
    """Push a visual action card to the frontend via LiveKit text stream."""
    try:
        room = ctx.session.room_io.room
        await room.local_participant.send_text(
            json.dumps(card),
            topic=ACTION_TOPIC,
        )
    except Exception as e:
        logger.warning("Failed to send action card: %s", e)


async def _send_assistant_transcript(ctx: agents.JobContext, text: str) -> None:
    """
    Emit assistant transcript chunks on lk.transcription so web clients can
    render text even when server-side transcription is unavailable.
    """
    try:
        await ctx.room.local_participant.send_text(
            text,
            topic="lk.transcription",
            attributes={
                "lk.transcribed_track_id": "assistant",
                "lk.transcription_final": "true",
                "lk.segment_id": str(uuid.uuid4()),
            },
        )
    except Exception as e:
        logger.warning("Failed to send assistant transcript: %s", e)


# ── Helpers ──────────────────────────────────────────────────────────

def _get_db():
    """Lazy import + create a DB session."""
    from database.connection import get_db
    return get_db()


def _uid(ctx: RunContext) -> int | None:
    """Extract numeric user_id from session userdata."""
    v = ctx.userdata.get("user_id")
    return int(v) if v and str(v).isdigit() else None


def _did(ctx: RunContext) -> str | None:
    return ctx.userdata.get("user_did")


def _registry():
    """Lazy-load the tool registry singleton."""
    from voice.agent.registry import get_tool_registry
    return get_tool_registry()


# Tools that anonymous / guest users may call (read-only)
READ_ONLY_TOOL_NAMES = {
    "query_batches", "search_knowledge",
    "browse_rfqs", "list_my_offers",
    "check_eudr_compliance", "check_mass_balance",
    "get_dpp", "get_container_dpp",
    "trace_lineage", "validate_dpp",
    "list_pending_verifications",
    "check_blockchain_anchor", "get_token_info",
    "verify_batch_hash",
    "check_don_attestation", "get_don_provenance_metrics",
    "browse_containers", "browse_pools",
    "list_my_commitments", "check_payment_status",
    "check_financing_pool", "check_trade_financing", 
    "confirm_trade_delivery", "cancel_trade", "mark_default",
}


async def _exec(ctx: RunContext, tool_name: str, args: dict) -> str:
    """
    Call a registry handler and push an action card with the result data.
    Returns the voice-friendly message string.
    """
    # ── Anonymous / guest hard gate ──
    uid = _uid(ctx)
    if (uid is None or uid == 0) and tool_name not in READ_ONLY_TOOL_NAMES:
        return (
            f"Sorry, {tool_name.replace('_', ' ')} requires a signed-in account. "
            "You can sign in from the navigation bar, or register via Telegram "
            "at t.me/voice_ledger_bot. Is there anything else I can look up for you?"
        )

    handler = _registry().get(tool_name)
    if not handler:
        return f"Tool '{tool_name}' is not available."

    with _get_db() as db:
        message, data = handler(db, args, user_id=uid, user_did=_did(ctx))

    # Send a visual card unless it's an error-only response
    if data and not data.get("error"):
        await _send_action_card(ctx, {"type": tool_name, **data})

    return message


# =====================================================================
# 1. CORE SUPPLY-CHAIN TOOLS (record, ship, receive, transform, pack)
# =====================================================================

@function_tool(description=(
    "Create a NEW coffee batch. Use when a farmer reports a harvest, "
    "a new lot, or says they have coffee to register. "
    "Do NOT use if they reference an existing batch ID."
))
async def record_commission(
    ctx: RunContext,
    quantity_kg: Annotated[float, "Weight in kg. If user says bags, multiply by 60"],
    origin: Annotated[str, "Farm name, region, or location"],
    variety: Annotated[str | None, "Coffee variety e.g. Sidama, Yirgacheffe, Arabica"] = None,
    grade: Annotated[str | None, "Quality grade: A, B, C, Grade 1, Grade 2"] = "A",
) -> str:
    return await _exec(ctx, "record_commission", {
        "quantity_kg": quantity_kg, "origin": origin,
        "variety": variety, "grade": grade,
    })


@function_tool(description=(
    "Ship an EXISTING batch to a destination. Use when user says "
    "'ship', 'send', 'deliver', 'dispatch' and references a batch."
))
async def record_shipment(
    ctx: RunContext,
    batch_id: Annotated[str, "Batch ID or GTIN to ship"],
    destination: Annotated[str, "Shipping destination"],
    carrier: Annotated[str | None, "Carrier or transport company"] = None,
    transport_mode: Annotated[str | None, "Transport mode: truck, ship, air, rail"] = None,
) -> str:
    return await _exec(ctx, "record_shipment", {
        "batch_id": batch_id, "destination": destination,
        "carrier": carrier, "transport_mode": transport_mode,
    })


@function_tool(description=(
    "Record receipt of an existing batch. Use when user says "
    "'received', 'got', 'accepted', 'arrived' and references a batch."
))
async def record_receipt(
    ctx: RunContext,
    batch_id: Annotated[str, "Batch ID or GTIN of the received batch"],
    condition: Annotated[str | None, "Condition on arrival: good, damaged, partial"] = "good",
    location: Annotated[str | None, "Receiving location or warehouse"] = None,
) -> str:
    return await _exec(ctx, "record_receipt", {
        "batch_id": batch_id, "condition": condition, "location": location or "",
    })


@function_tool(description=(
    "Process coffee — roasting, milling, drying, hulling. "
    "Changes the physical/chemical properties of the batch."
))
async def record_transformation(
    ctx: RunContext,
    batch_id: Annotated[str, "Batch ID or GTIN of the input batch"],
    transformation_type: Annotated[str, "Type: roasting, milling, drying, hulling, washing"],
    output_quantity_kg: Annotated[float, "Output quantity in kg (typically 10-30% less than input)"],
    output_variety: Annotated[str | None, "Output product description e.g. Roasted Sidama"] = None,
) -> str:
    return await _exec(ctx, "record_transformation", {
        "batch_id": batch_id, "transformation_type": transformation_type,
        "output_quantity_kg": output_quantity_kg, "output_variety": output_variety,
    })


@function_tool(description=(
    "Pack / aggregate multiple batches into a single container or pallet. "
    "Use when user says 'pack', 'combine', 'load into container'."
))
async def pack_batches(
    ctx: RunContext,
    batch_ids_json: Annotated[str, "JSON array of batch IDs or GTINs to pack, e.g. '[\"BATCH-001\", \"BATCH-002\"]'"],
    container_id: Annotated[str | None, "Container or pallet ID (auto-generated if omitted)"] = None,
    container_type: Annotated[str | None, "Container type: pallet, container, bag"] = "pallet",
) -> str:
    import json as _json
    try:
        batch_ids = _json.loads(batch_ids_json)
    except Exception:
        batch_ids = [b.strip() for b in batch_ids_json.split(",")]
    return await _exec(ctx, "pack_batches", {
        "batch_ids": batch_ids, "container_id": container_id,
        "container_type": container_type,
    })


@function_tool(description=(
    "Unpack / disaggregate a container to release its batches. "
    "Use when user says 'unpack', 'unload', 'open container'."
))
async def unpack_batches(
    ctx: RunContext,
    container_id: Annotated[str, "Container or pallet ID to unpack"],
) -> str:
    return await _exec(ctx, "unpack_batches", {"container_id": container_id})


@function_tool(description=(
    "Split one batch into multiple smaller portions. "
    "Use when user says 'split', 'divide', 'separate'. "
    "NOT for processing — use record_transformation for that."
))
async def split_batch(
    ctx: RunContext,
    batch_id: Annotated[str, "Parent batch ID or GTIN to split"],
    splits_json: Annotated[str, "JSON array of split portions, e.g. '[{\"quantity_kg\": 50, \"destination\": \"Addis\"}, {\"quantity_kg\": 30, \"destination\": \"Djibouti\"}]'"],
) -> str:
    import json as _json
    try:
        splits = _json.loads(splits_json)
    except (ValueError, TypeError):
        return "Invalid splits format. Provide a JSON array of {quantity_kg, destination} objects."
    return await _exec(ctx, "split_batch", {"batch_id": batch_id, "splits": splits})


@function_tool(description=(
    "Look up coffee batches in the database. Use when the user asks "
    "'show my batches', 'find batch X', 'how many batches', 'what batches', "
    "'status of batch'. This is a READ-ONLY operation."
))
async def query_batches(
    ctx: RunContext,
    batch_id: Annotated[str | None, "Specific batch ID or GTIN to look up"] = None,
    status: Annotated[str | None, "Filter: PENDING_VERIFICATION, VERIFIED, SHIPPED, RECEIVED"] = None,
    origin: Annotated[str | None, "Filter by origin region"] = None,
    limit: Annotated[int, "Max results (default 10)"] = 10,
) -> str:
    """Query batches and push a visual card with results."""
    from services.batch_service import query_batches as svc_query_batches

    with _get_db() as db:
        result = svc_query_batches(
            db, batch_id=batch_id, status=status,
            origin=origin, user_id=_uid(ctx), limit=limit,
        )

    if result["single"] and result["found"]:
        await _send_action_card(ctx, {"type": "batch_detail", **result["batch"]})
        b = result["batch"]
        return (
            f"Found batch {b['batch_id']}: {b['variety'] or 'coffee'} from "
            f"{b['origin'] or 'unknown origin'}, {b['quantity_kg']}kg, "
            f"status {b['status']}."
        )
    if result["single"] and not result["found"]:
        return f"Batch '{result.get('query_batch_id', batch_id)}' not found."
    if result["count"] > 0:
        await _send_action_card(ctx, {
            "type": "batch_list",
            "batches": result["batches"], "count": result["count"],
        })
        return f"Found {result['count']} batch(es). I've sent the details to your screen."
    return "No batches found matching your criteria."


@function_tool(description=(
    "Search the Voice Ledger knowledge base for documentation, guides, "
    "standards, and how-to information. Use when user asks 'how to', "
    "'what is', 'explain', or questions about EUDR, EPCIS, GS1, blockchain."
))
async def search_knowledge(
    ctx: RunContext,
    query: Annotated[str, "The search query in English"],
) -> str:
    return await _exec(ctx, "search_knowledge", {"query": query})


# =====================================================================
# 2. MARKETPLACE TOOLS (RFQs, offers, acceptances)
# =====================================================================

@function_tool(description=(
    "Create a new Request for Quote (RFQ) on the marketplace. "
    "Only BUYER role users can create RFQs. Use when a buyer says "
    "'I need coffee', 'looking for', 'request quote', 'buy', 'purchase'."
))
async def create_rfq(
    ctx: RunContext,
    quantity_kg: Annotated[float, "Quantity needed in kg. If bags, multiply by 60"],
    variety: Annotated[str | None, "Coffee variety e.g. Yirgacheffe, Sidama, Guji"] = None,
    processing_method: Annotated[str | None, "Processing: Washed, Natural, Honey"] = None,
    grade: Annotated[str | None, "Quality grade: Grade 1, Grade 2, Specialty"] = None,
    delivery_location: Annotated[str | None, "Delivery destination"] = None,
) -> str:
    return await _exec(ctx, "create_rfq", {
        "quantity_kg": quantity_kg, "variety": variety,
        "processing_method": processing_method, "grade": grade,
        "delivery_location": delivery_location,
    })


@function_tool(description=(
    "Browse open RFQs on the marketplace. Use when cooperative managers ask "
    "'what do buyers need', 'show me requests', 'available RFQs', 'marketplace'."
))
async def browse_rfqs(
    ctx: RunContext,
    variety: Annotated[str | None, "Filter by coffee variety"] = None,
    status: Annotated[str | None, "Filter: OPEN, PARTIALLY_FILLED, FULFILLED"] = "OPEN",
    limit: Annotated[int, "Max results (default 10)"] = 10,
) -> str:
    return await _exec(ctx, "browse_rfqs", {
        "variety": variety, "status": status, "limit": limit,
    })


@function_tool(description=(
    "Submit an offer for an open RFQ. Only COOPERATIVE_MANAGER role. "
    "Use when user says 'I can supply', 'make offer', 'bid on'."
))
async def submit_offer(
    ctx: RunContext,
    quantity_offered_kg: Annotated[float, "Quantity offered in kg"],
    price_per_kg: Annotated[float, "Price per kg in USD"],
    rfq_id: Annotated[int | None, "RFQ ID to make an offer on"] = None,
    rfq_number: Annotated[str | None, "RFQ number e.g. RFQ-000001"] = None,
    delivery_timeline: Annotated[str | None, "Timeline e.g. '2 weeks', '30 days'"] = None,
) -> str:
    return await _exec(ctx, "submit_offer", {
        "rfq_id": rfq_id, "rfq_number": rfq_number,
        "quantity_offered_kg": quantity_offered_kg,
        "price_per_kg": price_per_kg, "delivery_timeline": delivery_timeline,
    })


@function_tool(description=(
    "Accept an offer from a cooperative on one of your RFQs. "
    "Only the BUYER who created the RFQ can accept."
))
async def accept_offer(
    ctx: RunContext,
    offer_id: Annotated[int, "The offer ID to accept"],
    rfq_id: Annotated[int, "RFQ ID the offer belongs to"],
    quantity_accepted_kg: Annotated[float | None, "Quantity to accept (full offer if omitted)"] = None,
    payment_terms: Annotated[str | None, "Payment terms e.g. 'Net 30 days'"] = None,
) -> str:
    return await _exec(ctx, "accept_offer", {
        "offer_id": offer_id, "rfq_id": rfq_id,
        "quantity_accepted_kg": quantity_accepted_kg,
        "payment_terms": payment_terms,
    })


@function_tool(description=(
    "List offers submitted by your cooperative. "
    "Use when user asks 'show my offers', 'what have I offered'."
))
async def list_my_offers(
    ctx: RunContext,
    status: Annotated[str | None, "Filter: PENDING, ACCEPTED, REJECTED"] = None,
) -> str:
    return await _exec(ctx, "list_my_offers", {"status": status})


# =====================================================================
# 3. CONTAINER MARKETPLACE & POOLS
# =====================================================================

@function_tool(description=(
    "Browse available container offerings on the marketplace. "
    "Use when user asks about containers, full-lot purchases."
))
async def browse_containers(
    ctx: RunContext,
    variety: Annotated[str | None, "Filter by coffee variety"] = None,
    min_quantity_kg: Annotated[float | None, "Minimum quantity available"] = None,
    limit: Annotated[int, "Max results (default 10)"] = 10,
) -> str:
    return await _exec(ctx, "browse_containers", {
        "variety": variety, "min_quantity_kg": min_quantity_kg, "limit": limit,
    })


@function_tool(description=(
    "Purchase a partial quantity from a container offering. Buyers only."
))
async def purchase_container(
    ctx: RunContext,
    container_id: Annotated[int, "Container offering ID"],
    quantity_kg: Annotated[float, "Quantity to purchase in kg"],
    payment_terms: Annotated[str | None, "Payment terms"] = "Net 7 days",
) -> str:
    return await _exec(ctx, "purchase_container", {
        "container_id": container_id, "quantity_kg": quantity_kg,
        "payment_terms": payment_terms,
    })


@function_tool(description=(
    "Browse active shared-buying container pools. "
    "Use when user asks about pools, shared containers, group buys."
))
async def browse_pools(
    ctx: RunContext,
    region: Annotated[str | None, "Filter by destination region"] = None,
    container_offering_id: Annotated[int | None, "Filter by specific container"] = None,
) -> str:
    return await _exec(ctx, "browse_pools", {
        "region": region, "container_offering_id": container_offering_id,
    })


@function_tool(description=(
    "Commit a fractional quantity to a shared container pool. Buyers only."
))
async def commit_to_pool(
    ctx: RunContext,
    container_offering_id: Annotated[int, "Container offering to commit to"],
    quantity_kg: Annotated[float, "Quantity to commit in kg"],
    delivery_country: Annotated[str | None, "2-letter country code for delivery"] = None,
    delivery_city: Annotated[str | None, "Delivery city"] = None,
) -> str:
    return await _exec(ctx, "commit_to_pool", {
        "container_offering_id": container_offering_id,
        "quantity_kg": quantity_kg,
        "delivery_country": delivery_country,
        "delivery_city": delivery_city,
    })


@function_tool(description=(
    "List your own pool commitments. "
    "Use when user asks 'show my commitments', 'what pools am I in'."
))
async def list_my_commitments(ctx: RunContext) -> str:
    return await _exec(ctx, "list_my_commitments", {})


# =====================================================================
# 4. COMPLIANCE TOOLS
# =====================================================================

@function_tool(description=(
    "Check EUDR compliance for one or more batches. "
    "Validates GPS, photo verification, and deforestation status."
))
async def check_eudr_compliance(
    ctx: RunContext,
    batch_ids_json: Annotated[str, "JSON array of batch IDs to check, e.g. '[\"BATCH-001\"]'"],
) -> str:
    import json as _json
    try:
        batch_ids = _json.loads(batch_ids_json)
    except Exception:
        batch_ids = [b.strip() for b in batch_ids_json.split(",")]
    return await _exec(ctx, "check_eudr_compliance", {"batch_ids": batch_ids})


@function_tool(description=(
    "Validate mass balance between inputs and outputs. "
    "Use when checking processing yield or aggregation totals."
))
async def check_mass_balance(
    ctx: RunContext,
    input_quantities_json: Annotated[str, "JSON array of input records, e.g. '[{\"quantity\": 100}]'"],
    output_quantities_json: Annotated[str, "JSON array of output records, e.g. '[{\"quantity\": 80}]'"],
    allow_loss: Annotated[bool, "Allow output < input (processing loss)"] = False,
) -> str:
    import json as _json
    try:
        input_quantities = _json.loads(input_quantities_json)
    except Exception:
        input_quantities = []
    try:
        output_quantities = _json.loads(output_quantities_json)
    except Exception:
        output_quantities = []
    return await _exec(ctx, "check_mass_balance", {
        "input_quantities": input_quantities,
        "output_quantities": output_quantities,
        "allow_loss": allow_loss,
    })


# =====================================================================
# 5. DPP / TRACEABILITY TOOLS
# =====================================================================

@function_tool(description=(
    "Generate or retrieve the Digital Product Passport (DPP) for a "
    "coffee batch. Returns EUDR compliance, traceability, blockchain "
    "anchoring, and QR code. Use when user asks 'show passport', "
    "'get DPP', 'traceability info', 'where did this coffee come from'."
))
async def get_dpp(
    ctx: RunContext,
    batch_id: Annotated[str, "Batch ID or GTIN to look up"],
) -> str:
    """Retrieve a DPP and push a passport card to the frontend."""
    from services.dpp_service import get_dpp as svc_get_dpp

    with _get_db() as db:
        result = svc_get_dpp(db, batch_id=batch_id)

    if not result["success"]:
        return f"Could not generate DPP: {result['error']}"

    await _send_action_card(ctx, {
        "type": "dpp_passport",
        "batch_id": result["batch_id"],
        "passport_id": result["passport_id"],
        "product": result["product"],
        "origin": result["origin"],
        "compliance": result["compliance"],
        "blockchain": result["blockchain"],
        "don_attestation": result["don_attestation"],
        "certifications": result["certifications"],
        "qr": result["qr"],
    })

    p = result["product"]
    o = result["origin"]
    c = result["compliance"]
    bc = result["blockchain"]
    don = result["don_attestation"]

    don_line = ""
    if don["attested"]:
        don_line = (
            f" DON attestation: {don['risk_label'] or '?'} risk, "
            f"{'compliant' if don['eudr_compliant'] else 'non-compliant'}."
        )

    return (
        f"Here's the Digital Product Passport for {result['batch_id']}. "
        f"{p['variety'] or 'Coffee'} from {o['region']}, {o['country']}. "
        f"EUDR {'compliant' if c['eudr_compliant'] else 'not compliant'}. "
        f"Blockchain {'anchored' if bc['anchored'] else 'pending'}."
        f"{don_line}"
        f" I've sent the full passport to your screen."
    )


@function_tool(description=(
    "Get the aggregated Digital Product Passport for a shipping container. "
    "Shows all contributing farmers and total quantities."
))
async def get_container_dpp(
    ctx: RunContext,
    container_id: Annotated[str, "Container or SSCC ID"],
) -> str:
    return await _exec(ctx, "get_container_dpp", {"container_id": container_id})


@function_tool(description=(
    "Trace the full supply chain lineage of a product or batch. "
    "Shows all contributing farmers, transformations, and custody transfers."
))
async def trace_lineage(
    ctx: RunContext,
    product_id: Annotated[str, "Product, batch, or container ID to trace"],
    max_depth: Annotated[int, "Max recursion depth (default 5)"] = 5,
) -> str:
    return await _exec(ctx, "trace_lineage", {
        "product_id": product_id, "max_depth": max_depth,
    })


@function_tool(description=(
    "Validate a DPP for completeness and EUDR compliance. "
    "Checks all required fields and compliance criteria."
))
async def validate_dpp(
    ctx: RunContext,
    batch_id: Annotated[str, "Batch ID to validate"],
) -> str:
    return await _exec(ctx, "validate_dpp", {"batch_id": batch_id})


# =====================================================================
# 6. VERIFICATION TOOLS
# =====================================================================

@function_tool(description=(
    "List batches pending verification. Use when a cooperative manager "
    "asks 'what needs to be verified', 'pending verifications'."
))
async def list_pending_verifications(
    ctx: RunContext,
    origin: Annotated[str | None, "Filter by origin"] = None,
    limit: Annotated[int, "Max results (default 10)"] = 10,
) -> str:
    return await _exec(ctx, "list_pending_verifications", {
        "origin": origin, "limit": limit,
    })


@function_tool(description=(
    "Verify a coffee batch. Only COOPERATIVE_MANAGER or ADMIN roles. "
    "Sets batch status to VERIFIED and issues a verifiable credential."
))
async def verify_batch(
    ctx: RunContext,
    batch_id: Annotated[str, "Batch ID to verify"],
    verified_quantity_kg: Annotated[float | None, "Verified weight (defaults to claimed)"] = None,
    quality_notes: Annotated[str | None, "Quality assessment notes"] = None,
    cupping_score: Annotated[float | None, "Cupping score (0-100)"] = None,
    moisture_pct: Annotated[float | None, "Moisture percentage"] = None,
    screen_size: Annotated[str | None, "Screen size"] = None,
    defect_count: Annotated[int | None, "Number of defects"] = None,
) -> str:
    args = {"batch_id": batch_id}
    if verified_quantity_kg is not None:
        args["verified_quantity_kg"] = verified_quantity_kg
    if quality_notes:
        args["quality_notes"] = quality_notes
    if cupping_score is not None:
        args["cupping_score"] = cupping_score
    if moisture_pct is not None:
        args["moisture_pct"] = moisture_pct
    if screen_size:
        args["screen_size"] = screen_size
    if defect_count is not None:
        args["defect_count"] = defect_count
    return await _exec(ctx, "verify_batch", args)


# =====================================================================
# 7. BLOCKCHAIN TOOLS
# =====================================================================

@function_tool(description=(
    "Check if a batch is anchored on the blockchain. "
    "Use when user asks 'is batch X on chain', 'blockchain status'."
))
async def check_blockchain_anchor(
    ctx: RunContext,
    batch_id: Annotated[str, "Batch ID to check"],
) -> str:
    return await _exec(ctx, "check_blockchain_anchor", {"batch_id": batch_id})


@function_tool(description=(
    "Look up an ERC-1155 batch token's on-chain metadata. "
    "Use when user asks about a token ID or on-chain batch data."
))
async def get_token_info(
    ctx: RunContext,
    token_id: Annotated[int, "Token ID to look up"],
) -> str:
    return await _exec(ctx, "get_token_info", {"token_id": token_id})


@function_tool(description=(
    "Verify batch data integrity by comparing its hash against the "
    "blockchain record. Detects if data has been tampered with."
))
async def verify_batch_hash(
    ctx: RunContext,
    batch_id: Annotated[str, "Batch ID to verify"],
) -> str:
    return await _exec(ctx, "verify_batch_hash", {"batch_id": batch_id})


# =====================================================================
# 8. CHAINLINK CRE / DON ATTESTATION TOOLS
# =====================================================================

@function_tool(description=(
    "Request a Chainlink DON-attested deforestation check for a farm. "
    "Uses satellite data (GFW) to verify no tree loss at the farm's GPS."
))
async def request_don_attestation(
    ctx: RunContext,
    farm_id: Annotated[str, "Farm or farmer ID to check"],
) -> str:
    return await _exec(ctx, "request_don_attestation", {"farm_id": farm_id})


@function_tool(description=(
    "Read a DON-attested deforestation result from the blockchain. "
    "Use after requesting an attestation, or to check existing results."
))
async def check_don_attestation(
    ctx: RunContext,
    farm_id: Annotated[str, "Farm or farmer ID to check"],
) -> str:
    return await _exec(ctx, "check_don_attestation", {"farm_id": farm_id})


@function_tool(description=(
    "Read DON-attested supply chain provenance metrics from the blockchain. "
    "Shows total farmers, batches, quantity, EUDR compliance rates."
))
async def get_don_provenance_metrics(ctx: RunContext) -> str:
    return await _exec(ctx, "get_don_provenance_metrics", {})


# =====================================================================
# 9. SETTLEMENT / PAYMENT TOOLS
# =====================================================================

@function_tool(description=(
    "Confirm you made a bank transfer for a commitment or acceptance. "
    "Records settlement on-chain. Buyer role required."
))
async def confirm_payment(
    ctx: RunContext,
    commitment_id: Annotated[int | None, "Commitment ID to confirm payment for"] = None,
    acceptance_number: Annotated[str | None, "Acceptance number e.g. ACC-000001"] = None,
    payment_reference: Annotated[str | None, "Bank transfer reference"] = None,
) -> str:
    return await _exec(ctx, "confirm_payment", {
        "commitment_id": commitment_id,
        "acceptance_number": acceptance_number,
        "payment_reference": payment_reference,
    })


@function_tool(description=(
    "Check payment and blockchain settlement status for a commitment "
    "or acceptance. Shows buyer/coop confirmation and TX hashes."
))
async def check_payment_status(
    ctx: RunContext,
    commitment_id: Annotated[int | None, "Commitment ID"] = None,
    acceptance_number: Annotated[str | None, "Acceptance number"] = None,
) -> str:
    return await _exec(ctx, "check_payment_status", {
        "commitment_id": commitment_id,
        "acceptance_number": acceptance_number,
    })


@function_tool(description=(
    "Admin records that WAGA forwarded funds to the cooperative's bank. "
    "Records payout on-chain. Admin role required."
))
async def record_cooperative_payout(
    ctx: RunContext,
    commitment_id: Annotated[int | None, "Commitment ID"] = None,
    acceptance_number: Annotated[str | None, "Acceptance number"] = None,
) -> str:
    return await _exec(ctx, "record_cooperative_payout", {
        "commitment_id": commitment_id,
        "acceptance_number": acceptance_number,
    })


@function_tool(description=(
    "Cooperative confirms they received the buyer's payment. "
    "Updates delivery status to PREPARING_SHIPMENT."
))
async def confirm_payment_received(
    ctx: RunContext,
    commitment_id: Annotated[int | None, "Commitment ID"] = None,
    acceptance_number: Annotated[str | None, "Acceptance number"] = None,
) -> str:
    return await _exec(ctx, "confirm_payment_received", {
        "commitment_id": commitment_id,
        "acceptance_number": acceptance_number,
    })


# =====================================================================
# 10. DeFi FINANCING POOL TOOLS
# =====================================================================

@function_tool(description=(
    "Check the current DeFi financing pool stats — liquidity, "
    "utilisation, share price, advances. READ-ONLY."
))
async def check_financing_pool(ctx: RunContext) -> str:
    return await _exec(ctx, "check_financing_pool", {})


@function_tool(description=(
    "Request a USDC advance from the financing pool against a confirmed "
    "trade. Cooperative role required. The pool advances ~80% of agreed price."
))
async def request_financing_advance(
    ctx: RunContext,
    acceptance_number: Annotated[str | None, "Acceptance number for the trade"] = None,
    token_id: Annotated[int | None, "Container token ID (if known)"] = None,
    buyer_address: Annotated[str | None, "Buyer's wallet address"] = None,
) -> str:
    return await _exec(ctx, "request_financing_advance", {
        "acceptance_number": acceptance_number,
        "token_id": token_id,
        "buyer_address": buyer_address,
    })


@function_tool(description=(
    "Check the status of a financed trade — advance amount, fees, "
    "settlement status, deadline."
))
async def check_trade_financing(
    ctx: RunContext,
    trade_id: Annotated[int | None, "On-chain trade ID"] = None,
    acceptance_number: Annotated[str | None, "Acceptance number"] = None,
) -> str:
    return await _exec(ctx, "check_trade_financing", {
        "trade_id": trade_id,
        "acceptance_number": acceptance_number,
    })


@function_tool(description=(
    "Buyer confirms coffee delivery and releases payment from escrow. "
    "This settles the trade: remaining 20% goes to cooperative, "
    "fees are distributed to investors, and collateral is unlocked. "
    "Buyer role required."
))
async def confirm_trade_delivery(
    ctx: RunContext,
    trade_id: Annotated[int | None, "On-chain trade ID"] = None,
    acceptance_number: Annotated[str | None, "Acceptance number"] = None,
) -> str:
    return await _exec(ctx, "confirm_trade_delivery", {
        "trade_id": trade_id,
        "acceptance_number": acceptance_number,
    })


@function_tool(description=(
    "Cancel a pending or active financed trade. Returns collateral "
    "to the cooperative and frees up pool liquidity. "
    "Cooperative role required."
))
async def cancel_trade(
    ctx: RunContext,
    trade_id: Annotated[int | None, "On-chain trade ID"] = None,
    acceptance_number: Annotated[str | None, "Acceptance number"] = None,
) -> str:
    return await _exec(ctx, "cancel_trade", {
        "trade_id": trade_id,
        "acceptance_number": acceptance_number,
    })


@function_tool(description=(
    "Mark a financed trade as defaulted when delivery deadline passes. "
    "Liquidates collateral and distributes to pool investors. "
    "Cooperative or admin role required."
))
async def mark_default(
    ctx: RunContext,
    trade_id: Annotated[int | None, "On-chain trade ID"] = None,
    acceptance_number: Annotated[str | None, "Acceptance number"] = None,
) -> str:
    return await _exec(ctx, "mark_default", {
        "trade_id": trade_id,
        "acceptance_number": acceptance_number,
    })


# =====================================================================
# System prompt — full capabilities
# =====================================================================

SYSTEM_PROMPT = """\
You are Voice Ledger — an AI voice assistant for the Ethiopian coffee supply chain.

You help farmers, cooperatives, exporters, and buyers manage coffee from harvest
to export through natural conversation. You are speaking over a live audio
connection — keep responses SHORT (2-3 sentences for confirmations, brief lists
for data queries).

YOUR CAPABILITIES (use the tools provided):

SUPPLY CHAIN RECORDING
• Record new coffee batches (record_commission)
• Ship batches (record_shipment), receive batches (record_receipt)
• Process / transform coffee (record_transformation)
• Pack (pack_batches), unpack (unpack_batches), split (split_batch)

QUERIES & KNOWLEDGE
• Look up batches by ID, status, or origin (query_batches)
• Search docs, guides, EUDR/EPCIS standards (search_knowledge)

MARKETPLACE
• Create a Request for Quote / RFQ (create_rfq) — buyers only
• Browse active RFQs (browse_rfqs)
• Submit an offer on an RFQ (submit_offer) — cooperatives only
• Accept an offer (accept_offer) — buyer who created the RFQ
• List your submitted offers (list_my_offers)

CONTAINER MARKETPLACE & POOLS
• Browse container offerings (browse_containers)
• Purchase from a container (purchase_container)
• Browse shared-buying pools (browse_pools)
• Commit to a pool (commit_to_pool)
• List your pool commitments (list_my_commitments)

COMPLIANCE
• Check EUDR compliance (check_eudr_compliance)
• Validate mass balance (check_mass_balance)

DIGITAL PRODUCT PASSPORTS
• Generate full DPP for a batch (get_dpp)
• Container-level DPP (get_container_dpp)
• Trace supply chain lineage (trace_lineage)
• Validate DPP completeness (validate_dpp)

VERIFICATION
• List batches pending verification (list_pending_verifications)
• Verify a batch (verify_batch) — cooperative managers / admin

BLOCKCHAIN
• Check blockchain anchor status (check_blockchain_anchor)
• Look up on-chain token info (get_token_info)
• Verify batch hash integrity (verify_batch_hash)

CHAINLINK DON / CRE
• Request DON-attested deforestation check (request_don_attestation)
• Read attestation result (check_don_attestation)
• Read provenance metrics (get_don_provenance_metrics)

SETTLEMENT & PAYMENTS
• Confirm bank payment (confirm_payment)
• Check payment status (check_payment_status)
• Record cooperative payout (record_cooperative_payout) — admin
• Confirm payment received (confirm_payment_received) — cooperative

DeFi FINANCING
• Check financing pool stats (check_financing_pool)
• Request advance against trade (request_financing_advance)
• Check trade financing status (check_trade_financing)
• Confirm delivery and release payment (confirm_trade_delivery)
• Cancel pending or active trade (cancel_trade)
• Mark trade as defaulted (mark_default)

RULES:
1. Be warm, clear, and concise — the user is speaking to you live.
2. When the user gives enough info, call the tool immediately.
3. When info is missing, ask ONE question at a time.
4. After a tool runs, summarize briefly — the visual card has the details.
5. For quantities in "bags", convert to kg (1 bag = 60 kg).
6. Never fabricate batch IDs — always query first if unsure.
7. Respect role-based access — farmers create batches, cooperatives verify
   and offer, buyers create RFQs and purchase, admins manage payouts.
8. Respond in English only (Amharic support coming soon).
"""


# =====================================================================
# Tool sets — guests see only read-only tools; registered users see all
# =====================================================================

# Read-only tools (safe for guests / anonymous users)
GUEST_TOOLS = [
    query_batches, search_knowledge,
    browse_rfqs, list_my_offers,
    browse_containers, browse_pools, list_my_commitments,
    check_eudr_compliance, check_mass_balance,
    get_dpp, get_container_dpp, trace_lineage, validate_dpp,
    list_pending_verifications,
    check_blockchain_anchor, get_token_info, verify_batch_hash,
    check_don_attestation, get_don_provenance_metrics,
    check_payment_status,
    check_financing_pool, check_trade_financing,
]

# All 40 tools (registered / authenticated users)
ALL_TOOLS = [
    # Supply chain recording (write)
    record_commission, record_shipment, record_receipt,
    record_transformation, pack_batches, unpack_batches, split_batch,
    # Queries / knowledge (read)
    query_batches, search_knowledge,
    # Marketplace (mixed)
    create_rfq, browse_rfqs, submit_offer, accept_offer, list_my_offers,
    # Containers & pools (mixed)
    browse_containers, purchase_container,
    browse_pools, commit_to_pool, list_my_commitments,
    # Compliance (read)
    check_eudr_compliance, check_mass_balance,
    # DPP / traceability (read)
    get_dpp, get_container_dpp, trace_lineage, validate_dpp,
    # Verification (mixed)
    list_pending_verifications, verify_batch,
    # Blockchain (read)
    check_blockchain_anchor, get_token_info, verify_batch_hash,
    # Chainlink DON / CRE (mixed)
    request_don_attestation, check_don_attestation, get_don_provenance_metrics,
    # Settlement (mixed)
    confirm_payment, check_payment_status,
    record_cooperative_payout, confirm_payment_received,
    # DeFi (mixed)
    check_financing_pool, request_financing_advance, check_trade_financing,
    confirm_trade_delivery, cancel_trade, mark_default,
]


# =====================================================================
# Agent class
# =====================================================================

# Guest-mode addendum appended to system prompt for anonymous sessions
GUEST_PROMPT_ADDENDUM = """

AUTHENTICATION STATUS: This user is a GUEST (not signed in).
- They CAN browse and query: look up batches, browse RFQs, view DPPs,
  check compliance, inspect blockchain anchors, and search knowledge.
- They CANNOT perform any write operations: creating batches, RFQs,
  offers, purchases, commitments, payments, verifications, or financing.
- If they ask for a write action, do NOT attempt it. Instead, warmly
  explain that they need to sign in first. Give two options:
  1. Click 'Sign In' in the navigation bar
  2. Register via Telegram: https://t.me/voice_ledger_bot
- Then ask if there is anything you can look up for them.
"""


class VoiceLedgerAgent(Agent):
    """LiveKit voice agent for Voice Ledger."""

    def __init__(self, user_name: str = "there", is_guest: bool = False):
        prompt = SYSTEM_PROMPT + f"\nThe user's name is {user_name}."
        if is_guest:
            prompt += GUEST_PROMPT_ADDENDUM
        super().__init__(
            instructions=prompt,
            tools=GUEST_TOOLS if is_guest else ALL_TOOLS,
        )


# =====================================================================
# Server + session entrypoint
# =====================================================================

server = agents.AgentServer()


@server.rtc_session()
async def handle_session(ctx: agents.JobContext):
    """Fired when a participant joins a LiveKit room."""
    await ctx.connect()
    participant = await ctx.wait_for_participant()

    # Read user metadata from the JWT (set by our token endpoint)
    metadata: dict = {}
    if participant.metadata:
        try:
            metadata = json.loads(participant.metadata)
        except (json.JSONDecodeError, TypeError):
            pass

    user_name = metadata.get("name", "there")
    user_id = metadata.get("user_id", "anonymous")
    user_role = metadata.get("role", "user")
    is_guest = (not user_id or str(user_id) == "anonymous" or str(user_id) == "0")

    logger.info(
        "Session started: user=%s (id=%s, role=%s, guest=%s)",
        user_name, user_id, user_role, is_guest,
    )

    llm_instance, llm_provider, llm_model = _build_livekit_llm()
    tts_instance = _build_livekit_tts(llm_provider)

    logger.info("LiveKit provider selection: llm_provider=%s, llm_model=%s", llm_provider, llm_model)

    session = AgentSession(
        stt=deepgram.STT(model="nova-2", language="en-US"),
        llm=llm_instance,
        tts=tts_instance,
        vad=silero.VAD.load(),
        userdata={
            "user_id": user_id,
            "user_did": metadata.get("user_did"),
            "name": user_name,
            "role": user_role,
            "is_guest": is_guest,
        },
    )

    await session.start(
        agent=VoiceLedgerAgent(user_name=user_name, is_guest=is_guest),
        room=ctx.room,
        room_options=room_io.RoomOptions(),
    )

    # Build a role-aware greeting that tells users what they can actually do
    if is_guest:
        what_i_can_do = (
            "As a guest, I can help you explore — browse coffee batches, "
            "look up Digital Product Passports, check EUDR compliance, "
            "view marketplace listings, and search our knowledge base. "
            "If you'd like to do more, just sign in!"
        )
    else:
        role_hints = {
            "farmer": (
                "You can register new coffee batches, check their status, "
                "track shipments, and generate Digital Product Passports."
            ),
            "cooperative_manager": (
                "You can verify batches, browse buyer RFQs, submit offers, "
                "manage settlements, and request financing advances."
            ),
            "buyer": (
                "You can create Requests for Quote, browse container offerings, "
                "join shared-buying pools, confirm payments, and pull up DPPs."
            ),
            "admin": (
                "You have full access — batch management, marketplace, "
                "verification, settlement payouts, blockchain tools, and DeFi."
            ),
        }
        what_i_can_do = role_hints.get(
            user_role,
            "I can help you record coffee batches, look up traceability data, "
            "manage marketplace transactions, check compliance, and more.",
        )

    greeting_text = (
        f"Hello {user_name}! Welcome to The Voice Ledger. "
        f"{what_i_can_do} Just tell me what you need, and I will help right away."
    )
    try:
        speech = session.say(greeting_text)
        await speech
        await _send_assistant_transcript(ctx, greeting_text)
        logger.info("Greeting delivered for user=%s", user_name)
    except Exception as e:
        _maybe_trip_openai_circuit_from_exception(e, llm_provider)
        logger.error("greeting say() failed: %s", e)
        try:
            fallback = (
                f"Hello {user_name}! Welcome to The Voice Ledger. "
                f"{what_i_can_do} Just tell me what you need!"
            )
            speech = session.say(fallback)
            await speech
            await _send_assistant_transcript(ctx, fallback)
        except Exception as e2:
            _maybe_trip_openai_circuit_from_exception(e2, llm_provider)
            logger.error("greeting fallback say() also failed: %s", e2)


if __name__ == "__main__":
    cli.run_app(server)
