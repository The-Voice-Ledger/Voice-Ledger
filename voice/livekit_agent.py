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
from typing import Annotated

from dotenv import load_dotenv

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

logger = logging.getLogger("voice-ledger-agent")

# ── Action card topic ────────────────────────────────────────────────
ACTION_TOPIC = "vl.action"


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


# ── Helper: get a DB session ────────────────────────────────────────

def _get_db():
    """Lazy import + create a DB session."""
    from database.connection import get_db
    return get_db()


# =====================================================================
# Tools — each wraps a services/ function
# =====================================================================

@function_tool(description=(
    "Look up coffee batches in the database. Use when the user asks "
    "'show my batches', 'find batch X', 'how many batches', 'what batches', "
    "'status of batch'. This is a READ-ONLY operation."
))
async def query_batches(
    ctx: RunContext,
    batch_id: Annotated[str | None, "Specific batch ID or GTIN to look up"] = None,
    status: Annotated[str | None, "Filter by status: PENDING_VERIFICATION, VERIFIED, SHIPPED, RECEIVED"] = None,
    origin: Annotated[str | None, "Filter by origin region"] = None,
    limit: Annotated[int, "Max number of results (default 10)"] = 10,
) -> str:
    """Query batches and push a visual card with results."""
    from services.batch_service import query_batches as svc_query_batches

    user_id = ctx.userdata.get("user_id")
    uid = int(user_id) if user_id and str(user_id).isdigit() else None

    with _get_db() as db:
        result = svc_query_batches(
            db,
            batch_id=batch_id,
            status=status,
            origin=origin,
            user_id=uid,
            limit=limit,
        )

    # Push action card to frontend
    if result["single"] and result["found"]:
        await _send_action_card(ctx, {
            "type": "batch_detail",
            **result["batch"],
        })
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
            "batches": result["batches"],
            "count": result["count"],
        })
        return f"Found {result['count']} batch(es). I've sent the details to your screen."

    return "No batches found matching your criteria."


@function_tool(description=(
    "Generate or retrieve the Digital Product Passport (DPP) for a "
    "coffee batch. Returns EUDR compliance data, traceability, "
    "blockchain anchoring status, and QR code. Use when user asks "
    "'show me the passport for batch X', 'get DPP', 'product passport', "
    "'traceability info', 'where did this coffee come from'."
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

    # Push rich DPP passport card to frontend
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

    # Build concise voice summary
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


# =====================================================================
# System prompt (reuses the same domain knowledge as executor.py)
# =====================================================================

SYSTEM_PROMPT = """\
You are Voice Ledger — an AI voice assistant for the Ethiopian coffee supply chain.

You help farmers, cooperatives, exporters, and buyers manage coffee from harvest
to export through natural conversation. You are speaking over a live audio
connection — keep responses SHORT (2-3 sentences for confirmations, brief lists
for data queries).

YOUR CAPABILITIES (use the tools provided):
• Look up batches and data (query_batches)
• Get Digital Product Passports (get_dpp)

More tools are being connected — if a user asks for something you can't do yet,
let them know it will be available soon.

RULES:
1. Be warm, clear, and concise — the user is speaking to you live
2. When the user gives enough info, call the tool immediately
3. When info is missing, ask ONE question at a time
4. After a tool runs, summarize briefly — the visual card has the details
5. For quantities in "bags", convert to kg (1 bag = 60 kg)
6. Never fabricate batch IDs — always query first if unsure
7. Respond in English only (Amharic support coming soon)
"""


# =====================================================================
# Agent class
# =====================================================================

class VoiceLedgerAgent(Agent):
    """LiveKit voice agent for Voice Ledger."""

    def __init__(self, user_name: str = "there"):
        super().__init__(
            instructions=SYSTEM_PROMPT + f"\nThe user's name is {user_name}.",
            tools=[query_batches, get_dpp],
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

    logger.info(
        "Session started: user=%s (id=%s, role=%s)",
        user_name, user_id, user_role,
    )

    session = AgentSession(
        stt=deepgram.STT(model="nova-2", language="en-US"),
        llm=openai.LLM(model="gpt-4o-mini", temperature=0.2),
        tts=openai.TTS(model="tts-1", voice="nova"),
        vad=silero.VAD.load(),
        userdata={
            "user_id": user_id,
            "user_did": metadata.get("user_did"),
            "name": user_name,
            "role": user_role,
        },
    )

    await session.start(
        agent=VoiceLedgerAgent(user_name=user_name),
        room=ctx.room,
        room_input_options=room_io.RoomInputOptions(),
    )

    # Build a role-aware greeting that tells users what they can actually do
    greeting = (
        f"Greet {user_name} warmly by name. Then briefly tell them what you "
        f"can help with right now. Say something like: "
        f"'You can ask me to look up any coffee batch — by ID, origin, or "
        f"status — and I'll pull up the details for you. I can also generate "
        f"a full Digital Product Passport for any batch, showing traceability, "
        f"EUDR compliance, and blockchain anchoring. Just tell me what you need.' "
        f"Keep the whole greeting to 3–4 sentences, conversational and warm. "
        f"Do NOT list features with bullet points — speak naturally."
    )
    await session.generate_reply(instructions=greeting)


if __name__ == "__main__":
    cli.run_app(server)
