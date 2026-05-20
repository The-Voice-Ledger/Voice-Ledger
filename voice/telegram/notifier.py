"""
Simple Telegram notification utility for Celery tasks.

Uses python-telegram-bot's Bot class with direct API calls (no async complexity).
Designed to work reliably in Celery worker context.
"""

import os
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


def send_telegram_notification(chat_id: int, message: str) -> bool:
    """
    Send a simple text notification to a Telegram user.
    
    Uses synchronous HTTP requests to avoid asyncio issues in Celery.
    
    Args:
        chat_id: Telegram user/chat ID
        message: Text message to send
        
    Returns:
        True if sent successfully, False otherwise
    """
    import requests
    
    bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
    if not bot_token:
        logger.error("TELEGRAM_BOT_TOKEN not set")
        return False
    
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    
    try:
        response = requests.post(
            url,
            json={
                'chat_id': chat_id,
                'text': message,
                'parse_mode': 'Markdown'
            },
            timeout=10
        )
        
        if response.status_code == 200:
            logger.info(f"Telegram notification sent to {chat_id}")
            return True
        else:
            logger.error(f"Telegram API error: {response.status_code} - {response.text}")
            return False
            
    except Exception as e:
        logger.error(f"Failed to send Telegram notification: {e}")
        return False


def send_batch_confirmation(chat_id: int, batch_info: Dict[str, Any]) -> bool:
    """
    Send a formatted batch confirmation notification.
    
    Args:
        chat_id: Telegram user/chat ID
        batch_info: Dictionary with batch details
        
    Returns:
        True if sent successfully, False otherwise
    """
    batch_id = batch_info.get('id', 'Unknown')
    variety = batch_info.get('variety', 'Unknown')
    quantity = batch_info.get('quantity', 0)
    farm = batch_info.get('farm', 'Unknown')
    gtin = batch_info.get('gtin', 'N/A')
    gln = batch_info.get('gln', 'Not assigned')
    
    message = (
        f"✅ *Batch Created Successfully!*\n\n"
        f"📦 *Batch ID:* `{batch_id}`\n"
        f"🏷️ *GTIN:* `{gtin}`\n"
        f"📍 *GLN:* `{gln}`\n"
        f"☕ *Variety:* {variety}\n"
        f"⚖️ *Quantity:* {quantity} kg\n"
        f"🌍 *Origin:* {farm}\n\n"
        f"Your coffee batch has been registered in the traceability system."
    )
    
    return send_telegram_notification(chat_id, message)


async def send_batch_verification_qr(chat_id: int, batch_info: Dict[str, Any]) -> bool:
    """
    Send batch confirmation with verification QR code AND voice message.
    
    Sends a photo (QR code) with caption containing batch details,
    followed by a voice message for accessibility.
    
    Args:
        chat_id: Telegram user/chat ID
        batch_info: Dictionary with batch details including verification_token
        
    Returns:
        True if sent successfully, False otherwise
    """
    import httpx
    from telegram import Bot
    
    bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
    if not bot_token:
        logger.error("TELEGRAM_BOT_TOKEN not set")
        return False
    
    # Extract batch information
    batch_id = batch_info.get('batch_id', 'Unknown')
    variety = batch_info.get('variety', 'Unknown')
    quantity = batch_info.get('quantity_kg', 0)
    origin = batch_info.get('origin', 'Unknown')
    gtin = batch_info.get('gtin', 'N/A')
    verification_token = batch_info.get('verification_token')
    status = batch_info.get('status', 'UNKNOWN')
    
    if not verification_token:
        logger.error("No verification token provided for QR code")
        return False
    
    # Generate QR code
    try:
        from voice.verification.qr_codes import generate_qr_code_bytes
        qr_bytes = generate_qr_code_bytes(verification_token)
    except Exception as e:
        logger.error(f"Failed to generate QR code: {e}")
        return False
    
    # Prepare caption message with nice formatting
    base_url = os.getenv('BASE_URL', 'http://localhost:8000')
    
    # Get GLN for display
    gln = batch_info.get('gln', 'Not assigned')
    
    # Use HTML parse mode - MarkdownV2 requires escaping dozens of
    # special characters (. - ! ( ) etc.) which is fragile with
    # dynamic data like GTINs and GLNs.
    import html as _html
    _e = lambda v: _html.escape(str(v))  # shorthand for HTML-escaping

    caption = (
        f"📦 <b>Batch Created - Awaiting Verification</b>\n\n"
        f"<b>Batch ID:</b> <code>{_e(batch_id)}</code>\n"
        f"🏷️ <b>GTIN:</b> <code>{_e(gtin)}</code>\n"
        f"📍 <b>GLN:</b> <code>{_e(gln)}</code>\n"
        f"☕ <b>Variety:</b> {_e(variety)}\n"
        f"⚖️ <b>Quantity:</b> {_e(quantity)} kg\n"
        f"🌍 <b>Origin:</b> {_e(origin)}\n"
        f"📊 <b>Status:</b> {_e(status)}\n\n"
        f"🔍 <b>Next Step: Physical Verification</b>\n"
        f"Take this QR code to the cooperative collection center. "
        f"The manager will scan it to verify your batch.\n\n"
        f"⏱️ <b>Valid for:</b> 48 hours\n"
        f"🔗 <b>Verification Token:</b> <code>{_e(verification_token)}</code>"
    )
    
    # Send photo with caption
    url = f"https://api.telegram.org/bot{bot_token}/sendPhoto"
    
    try:
        files = {'photo': ('verification_qr.png', qr_bytes, 'image/png')}
        data = {
            'chat_id': chat_id,
            'caption': caption,
            'parse_mode': 'HTML'
        }
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(url, data=data, files=files)
        
        if response.status_code == 200:
            logger.info(f"Verification QR code sent to {chat_id}")
            
            # Now send voice message with TTS for accessibility
            try:
                from voice.telegram.voice_responses import send_voice_reply
                bot = Bot(token=bot_token)
                
                # Simplified text for voice (without markdown and emojis)
                voice_text = (
                    f"Batch Created - Awaiting Verification. "
                    f"Batch ID: {batch_id}. "
                    f"GTIN: {gtin}. "
                    f"Variety: {variety}. "
                    f"Quantity: {quantity} kilograms. "
                    f"Origin: {origin}. "
                    f"Status: {status}. "
                    f"Next Step: Physical Verification. "
                    f"Take this QR code to the cooperative collection center. "
                    f"The manager will scan it to verify your batch. "
                    f"Valid for 48 hours. "
                    f"Verification Token: {verification_token}"
                )
                
                await send_voice_reply(
                    bot=bot,
                    chat_id=chat_id,
                    message=voice_text,
                    parse_mode=None,  # Plain text for voice
                    send_voice=True
                )
                logger.info(f"Voice message sent for batch confirmation to {chat_id}")
            except Exception as voice_err:
                logger.warning(f"Failed to send voice message (QR sent successfully): {voice_err}")
            
            return True
        else:
            logger.error(f"Telegram API error: {response.status_code} - {response.text}")
            return False
            
    except Exception as e:
        logger.error(f"Failed to send verification QR code: {e}")
        return False


def send_error_notification(chat_id: int, error: str) -> bool:
    """
    Send an error notification.
    
    Args:
        chat_id: Telegram user/chat ID
        error: Error message
        
    Returns:
        True if sent successfully, False otherwise
    """
    message = f"❌ *Error Processing Voice Command*\n\n{error}"
    return send_telegram_notification(chat_id, message)


async def send_batch_dpp_pdf(chat_id: int, batch_id: str) -> bool:
    """
    Generate and send the Digital Product Passport PDF via Telegram.

    Called after a successful batch commission so the farmer receives a
    downloadable PDF they can share with cooperatives or customs brokers.

    Args:
        chat_id: Telegram user/chat ID
        batch_id: Batch identifier (e.g. "BATCH-2025-001")

    Returns:
        True if sent successfully, False otherwise
    """
    import httpx

    bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not bot_token:
        logger.error("TELEGRAM_BOT_TOKEN not set - cannot send DPP PDF")
        return False

    try:
        from dpp.dpp_pdf import build_and_render_pdf

        pdf_bytes = build_and_render_pdf(batch_id)
    except Exception as e:
        logger.error(f"Failed to generate DPP PDF for {batch_id}: {e}")
        return False

    import html as _html
    _e = lambda v: _html.escape(str(v))

    caption = (
        f"📄 <b>Digital Product Passport</b>\n\n"
        f"<b>Batch:</b> <code>{_e(batch_id)}</code>\n"
        f"Your full DPP is attached as a PDF.  Share it with "
        f"cooperatives, customs brokers, or buyers for instant "
        f"traceability verification."
    )

    url = f"https://api.telegram.org/bot{bot_token}/sendDocument"

    try:
        files = {
            "document": (f"DPP_{batch_id}.pdf", pdf_bytes, "application/pdf"),
        }
        data = {
            "chat_id": chat_id,
            "caption": caption,
            "parse_mode": "HTML",
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(url, data=data, files=files)

        if response.status_code == 200:
            logger.info(f"DPP PDF sent to {chat_id} for batch {batch_id}")
            return True
        else:
            logger.error(
                f"Telegram sendDocument error: {response.status_code} - {response.text}"
            )
            return False
    except Exception as e:
        logger.error(f"Failed to send DPP PDF to {chat_id}: {e}")
        return False


# ---------------------------------------------------------------------------
# Unified DPP Telegram Package
# ---------------------------------------------------------------------------

def _get_public_base_url() -> str:
    """Return the public-facing base URL for links shared in Telegram."""
    import os as _os
    for key in ("RAILWAY_PUBLIC_DOMAIN", "BASE_URL", "API_BASE_URL", "NGROK_URL"):
        val = _os.getenv(key, "").strip()
        if val:
            return val.rstrip("/") if val.startswith("http") else f"https://{val}"
    return "http://localhost:8002"


async def send_dpp_package(
    chat_id: int,
    batch_id: str,
    *,
    dpp: Optional[dict] = None,
    include_pdf: bool = True,
    include_qr: bool = True,
) -> bool:
    """
    Send an elegant, multi-part DPP delivery to a Telegram chat.

    Sequence:
      1. Rich HTML summary message with inline buttons (View Passport / Download PDF)
      2. QR code as a photo (if available)
      3. PDF document (if requested and generation succeeds)

    This is the single call-site for DPP delivery on Telegram - used by
    the /dpp command, post-commission flow, and agent get_dpp tool.

    Args:
        chat_id:      Telegram chat / user ID.
        batch_id:     The coffee batch identifier.
        dpp:          Pre-built DPP dict.  If *None*, one is built on the fly.
        include_pdf:  Whether to attach the PDF document.
        include_qr:   Whether to send the QR photo.

    Returns:
        True if the summary message was sent (the primary deliverable).
    """
    import httpx
    import html as _html
    import json as _json
    import base64

    bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not bot_token:
        logger.error("TELEGRAM_BOT_TOKEN not set - cannot send DPP package")
        return False

    # ── build DPP if not provided ──────────────────────────────────
    if dpp is None:
        try:
            from dpp.dpp_builder import build_dpp
            dpp = build_dpp(batch_id=batch_id)
        except Exception as e:
            logger.error("Cannot build DPP for %s: %s", batch_id, e)
            return False

    _e = lambda v: _html.escape(str(v)) if v is not None else "N/A"

    # ── extract fields ─────────────────────────────────────────────
    prod  = dpp.get("productInformation", {})
    trace = dpp.get("traceability", {})
    origin = trace.get("origin", {})
    farmer = origin.get("farmer", {})
    eudr  = dpp.get("eudrCompliance", {})
    dd    = dpp.get("dueDiligence", {})
    bc    = dpp.get("blockchain", {})
    don   = dpp.get("donAttestation", {})
    qr    = dpp.get("qrCode", {})
    events = trace.get("events", [])

    # Compliance badge
    comp_status = eudr.get("complianceStatus", "UNKNOWN")
    status_emoji = {
        "FULLY_VERIFIED": "🟢", "FARM_VERIFIED": "🟡",
        "SELF_REPORTED": "🟠", "NO_GPS": "🔴",
    }.get(comp_status, "⚪")

    level = _e(eudr.get("complianceLevel", "Unknown"))
    anchored = bool(bc.get("transactionHash") or bc.get("anchors"))
    tx_hash = bc.get("transactionHash") or (
        bc["anchors"][0].get("transactionHash") if bc.get("anchors") else None
    )

    # ── format lineage ─────────────────────────────────────────────
    lineage_lines = []
    for i, ev in enumerate(events[:6], 1):
        ts = (ev.get("timestamp") or "")[:10]
        etype = ev.get("eventType", "Event")
        biz = ev.get("bizStep", "")
        lineage_lines.append(f"   {i}. {_e(etype)}" + (f" - {_e(biz)}" if biz else "") + (f"  <i>{_e(ts)}</i>" if ts else ""))
    lineage_block = "\n".join(lineage_lines) if lineage_lines else "   No events recorded yet."

    # ── DON attestation line ───────────────────────────────────────
    don_block = ""
    if don.get("attestationExists"):
        don_block = (
            f"\n<b>Chainlink DON</b>\n"
            f"   Risk: {_e(don.get('riskLabel'))}  "
            f"{'✅' if don.get('eudrCompliant') else '❌'} EUDR\n"
        )

    # ── build message ──────────────────────────────────────────────
    message = (
        f"📋 <b>Digital Product Passport</b>\n"
        f"{'━' * 28}\n\n"

        f"<b>Batch</b>   <code>{_e(dpp.get('batchId', batch_id))}</code>\n"
        f"<b>GTIN</b>    <code>{_e(prod.get('gtin'))}</code>\n\n"

        f"<b>Product</b>\n"
        f"   {_e(prod.get('productName', 'Coffee'))} - {_e(prod.get('variety'))}\n"
        f"   {_e(prod.get('processMethod', ''))}  |  {_e(prod.get('quantity'))} {_e(prod.get('unit', 'kg'))}\n\n"

        f"<b>Origin</b>\n"
        f"   📍 {_e(origin.get('region'))}, {_e(origin.get('country'))}\n"
        f"   🧑‍🌾 {_e(farmer.get('name', 'Unknown farmer'))}\n"
        f"   🌿 Farm: {_e(origin.get('farmName', '-'))}\n\n"

        f"<b>EUDR Compliance</b>\n"
        f"   {status_emoji} {_e(comp_status.replace('_', ' ').title())}  |  Level: {level}\n"
        f"   {'✅' if dd.get('eudrCompliant') else '❌'} EUDR Compliant   "
        f"{'✅' if dd.get('allFarmersGeolocated') or (origin.get('latitude') is not None) else '⚠️'} GPS Verified\n"
        f"{don_block}\n"

        f"<b>Blockchain</b>\n"
        f"   {'🔗 Anchored' if anchored else '⏳ Pending'}"
        + (f"\n   <code>{_e(tx_hash)}</code>" if tx_hash else "")
        + f"\n\n"

        f"<b>Supply Chain</b>\n"
        f"{lineage_block}\n\n"

        f"{'━' * 28}\n"
        f"<i>Voice Ledger - Ethiopian Coffee Traceability</i>"
    )

    from urllib.parse import quote
    base_url = _get_public_base_url()
    bid_enc = quote(str(batch_id))

    # ── inline keyboard buttons ────────────────────────────────────
    keyboard = {
        "inline_keyboard": [
            [
                {"text": "🌐 View Passport", "url": f"{base_url}/passport/{bid_enc}"},
                {"text": "📄 Download PDF", "url": f"{base_url}/api/dpp/batch/{bid_enc}/pdf"},
            ],
        ]
    }

    # ── 1. Send summary message ────────────────────────────────────
    ok = False
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"https://api.telegram.org/bot{bot_token}/sendMessage",
                json={
                    "chat_id": chat_id,
                    "text": message,
                    "parse_mode": "HTML",
                    "reply_markup": keyboard,
                },
            )
        ok = resp.status_code == 200
        if not ok:
            logger.error("DPP summary send failed: %s %s", resp.status_code, resp.text)
    except Exception as exc:
        logger.error("DPP summary send error: %s", exc)

    if not ok:
        return False

    # ── 2. Send QR code photo (best-effort) ────────────────────────
    if include_qr:
        qr_img = qr.get("imageUrl", "")  # base64 data-URL or http URL
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                if qr_img.startswith("data:image"):
                    # data:image/png;base64,...
                    raw = base64.b64decode(qr_img.split(",", 1)[1])
                    await client.post(
                        f"https://api.telegram.org/bot{bot_token}/sendPhoto",
                        data={"chat_id": chat_id, "caption": f"QR - {batch_id}"},
                        files={"photo": ("qr.png", raw, "image/png")},
                    )
                elif qr_img.startswith("http"):
                    await client.post(
                        f"https://api.telegram.org/bot{bot_token}/sendPhoto",
                        json={"chat_id": chat_id, "photo": qr_img, "caption": f"QR - {batch_id}"},
                    )
                else:
                    logger.debug("No usable QR image for %s", batch_id)
        except Exception as exc:
            logger.warning("QR photo send failed (non-critical): %s", exc)

    # ── 3. Send PDF document (best-effort) ─────────────────────────
    if include_pdf:
        try:
            from dpp.dpp_pdf import build_and_render_pdf
            pdf_bytes = bytes(build_and_render_pdf(batch_id))
            async with httpx.AsyncClient(timeout=30.0) as client:
                await client.post(
                    f"https://api.telegram.org/bot{bot_token}/sendDocument",
                    data={
                        "chat_id": chat_id,
                        "caption": f"📄 DPP - {_e(batch_id)}",
                        "parse_mode": "HTML",
                    },
                    files={"document": (f"DPP_{batch_id}.pdf", pdf_bytes, "application/pdf")},
                )
            logger.info("DPP PDF sent to %s for batch %s", chat_id, batch_id)
        except Exception as exc:
            logger.warning("PDF send failed (non-critical): %s", exc)

    logger.info("DPP package delivered to %s for batch %s", chat_id, batch_id)
    return True
