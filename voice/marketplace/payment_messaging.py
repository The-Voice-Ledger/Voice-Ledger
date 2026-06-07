"""
Payment Coordination Messaging - Send payment instructions after offer acceptance

Phase 4: Manual Payment Coordination
Date: December 23, 2025

This module sends both parties (buyer + cooperative) detailed payment coordination
instructions after an RFQ offer is accepted.
"""

import logging
from typing import Dict, Any
from database.models import RFQAcceptance, RFQOffer, RFQ, UserIdentity, Organization

logger = logging.getLogger(__name__)


async def send_payment_instructions(
    acceptance: RFQAcceptance,
    offer: RFQOffer,
    rfq: RFQ,
    buyer: UserIdentity,
    cooperative_org: Organization,
    db
) -> None:
    """
    Send payment coordination instructions to both buyer and cooperative.
    
    Args:
        acceptance: RFQAcceptance record
        offer: RFQOffer that was accepted
        rfq: RFQ that generated this transaction
        buyer: UserIdentity of buyer
        cooperative_org: Organization (cooperative)
        db: Database session
    """
    # Calculate total
    total_amount = acceptance.quantity_accepted_kg * offer.price_per_kg
    
    # Get buyer organization (if exists)
    buyer_org = db.query(Organization).filter_by(id=buyer.organization_id).first() if buyer.organization_id else None
    
    # Send to buyer
    await send_buyer_payment_message(
        buyer=buyer,
        buyer_org=buyer_org,
        acceptance=acceptance,
        offer=offer,
        rfq=rfq,
        cooperative_org=cooperative_org,
        total_amount=total_amount
    )
    
    # Send to cooperative
    await send_cooperative_payment_message(
        cooperative_org=cooperative_org,
        buyer=buyer,
        buyer_org=buyer_org,
        acceptance=acceptance,
        offer=offer,
        rfq=rfq,
        total_amount=total_amount
    )


async def send_buyer_payment_message(
    buyer: UserIdentity,
    buyer_org: Organization,
    acceptance: RFQAcceptance,
    offer: RFQOffer,
    rfq: RFQ,
    cooperative_org: Organization,
    total_amount: float
) -> None:
    """Send payment instructions to buyer"""
    
    # Format bank details
    bank_name = getattr(cooperative_org, 'bank_name', None)
    bank_details = ""
    if bank_name:
        bank_details = (
            f"<b>Bank Details:</b>\n"
            f"Bank: {bank_name}\n"
            f"Account #: <code>{getattr(cooperative_org, 'bank_account_number', 'N/A')}</code>\n"
            f"Account Name: {getattr(cooperative_org, 'bank_account_name', cooperative_org.name)}\n"
        )

        swift = getattr(cooperative_org, 'bank_swift_code', None)
        if swift:
            bank_details += f"SWIFT/BIC: <code>{swift}</code>\n"

        branch = getattr(cooperative_org, 'bank_branch', None)
        if branch:
            bank_details += f"Branch: {branch}\n"

        bank_details += f"Reference: <b>{acceptance.acceptance_number}</b>\n"
    else:
        bank_details = (
            f"⚠️ <b>Bank details not on file</b>\n"
            f"Contact cooperative directly:\n"
            f"Phone: {getattr(cooperative_org, 'phone_number', 'N/A')}\n"
        )

    # Build message
    message = (
        f"✅ <b>Offer Accepted Successfully!</b>\n\n"
        f"📋 <b>Transaction Details</b>\n"
        f"Acceptance #: <code>{acceptance.acceptance_number}</code>\n"
        f"Cooperative: <b>{cooperative_org.name}</b>\n"
        f"Location: {cooperative_org.location}\n\n"
        f"📦 <b>Order Details</b>\n"
        f"Quantity: {acceptance.quantity_accepted_kg:,.0f} kg\n"
        f"Price per kg: ${offer.price_per_kg:.2f}\n"
        f"<b>Total Amount: ${total_amount:,.2f} USD</b>\n"
        f"Payment Terms: {acceptance.payment_terms or 'Standard'}\n\n"
        f"💰 <b>PAYMENT INSTRUCTIONS</b>\n\n"
        f"{bank_details}\n"
        f"⚠️ <b>IMPORTANT:</b>\n"
        f"• Include reference number: <code>{acceptance.acceptance_number}</code>\n"
        f"• Keep receipt photo for confirmation\n"
        f"• Payment expected within 5 business days\n\n"
        f"⏱️ <b>Next Steps:</b>\n\n"
        f"1️⃣ Transfer ${total_amount:,.2f} to cooperative's bank account\n"
        f"2️⃣ After payment, send: <code>/confirm_payment {acceptance.acceptance_number}</code> with receipt photo\n"
        f"3️⃣ Cooperative will verify and confirm receipt\n"
        f"4️⃣ Coffee shipment begins to {rfq.delivery_location}\n\n"
        f"📞 <b>Cooperative Contact:</b>\n"
        f"Phone: {getattr(cooperative_org, 'phone_number', 'N/A')}\n"
        f"Contact person: {cooperative_org.name}\n\n"
        f"💡 <b>Track Payment:</b>\n"
        f"Check status anytime: <code>/payment_status {acceptance.acceptance_number}</code>\n\n"
        f"🔗 Blockchain settlement record will be created when you confirm payment."
    )

    # Send to buyer via Telegram
    logger.info(f"Payment instructions sent to buyer {buyer.id} for acceptance {acceptance.acceptance_number}")
    print(f"\n📤 MESSAGE TO BUYER ({buyer.telegram_username}):\n{message}\n")
    if buyer.telegram_user_id:
        send_telegram_message(buyer.telegram_user_id, message, parse_mode='HTML')
    else:
        logger.warning("Buyer %s has no telegram_user_id, skipping payment message", buyer.id)


async def send_cooperative_payment_message(
    cooperative_org: Organization,
    buyer: UserIdentity,
    buyer_org: Organization,
    acceptance: RFQAcceptance,
    offer: RFQOffer,
    rfq: RFQ,
    total_amount: float
) -> None:
    """Send payment notification to cooperative"""
    
    buyer_name = buyer_org.name if buyer_org else f"{buyer.telegram_first_name} {buyer.telegram_last_name or ''}".strip()
    country_line = f"Country: {buyer_org.country}\n" if buyer_org and hasattr(buyer_org, 'country') and getattr(buyer_org, 'country', None) else ""

    message = (
        f"🎉 <b>Your Offer Has Been Accepted!</b>\n\n"
        f"📋 <b>Transaction Details</b>\n"
        f"Acceptance #: <code>{acceptance.acceptance_number}</code>\n"
        f"Buyer: <b>{buyer_name}</b>\n"
        f"{country_line}"
        f"\n📦 <b>Order Details</b>\n"
        f"Quantity: {acceptance.quantity_accepted_kg:,.0f} kg\n"
        f"Price per kg: ${offer.price_per_kg:.2f}\n"
        f"<b>Total Amount: ${total_amount:,.2f} USD</b>\n"
        f"Delivery to: {rfq.delivery_location}\n\n"
        f"⏳ <b>AWAITING PAYMENT</b>\n\n"
        f"Expected: Within 5 business days\n"
        f"Method: Bank transfer\n"
        f"Your Account: {getattr(cooperative_org, 'bank_account_number', '[Update bank details]')}\n\n"
        f"📋 <b>What Happens Next:</b>\n\n"
        f"1️⃣ Buyer will transfer ${total_amount:,.2f} to your bank account\n"
        f"2️⃣ Buyer will confirm payment with receipt photo\n"
        f"3️⃣ You'll receive notification when buyer confirms\n"
        f"4️⃣ Check your bank account (2-5 business days)\n"
        f"5️⃣ Confirm receipt: <code>/confirm_receipt {acceptance.acceptance_number}</code>\n"
        f"6️⃣ Prepare and ship {acceptance.quantity_accepted_kg:,.0f} kg to {rfq.delivery_location}\n\n"
        f"📞 <b>Buyer Contact:</b>\n"
        f"Phone: {buyer.phone_number or 'Not provided'}\n"
        f"Contact: {buyer_name}\n\n"
        f"⚠️ <b>Important:</b>\n"
        f"• Reference number on transfer: <code>{acceptance.acceptance_number}</code>\n"
        f"• Verify exact amount: ${total_amount:,.2f}\n"
        f"• Do NOT ship before payment confirmed\n\n"
        f"💡 <b>Track Payment:</b>\n"
        f"Check status anytime: <code>/payment_status {acceptance.acceptance_number}</code>\n\n"
        f"🔗 Blockchain settlement record will be created automatically when buyer confirms payment."
    )
    
    # Get cooperative manager user IDs and send to each
    cooperative_users = buyer._sa_instance_state.session.query(UserIdentity).filter_by(
        organization_id=cooperative_org.id,
        role='COOPERATIVE_MANAGER'
    ).all()

    logger.info(f"Payment notification sent to cooperative {cooperative_org.id} for acceptance {acceptance.acceptance_number}")
    print(f"\n📤 MESSAGE TO COOPERATIVE ({cooperative_org.name}):\n{message}\n")
    for coop_user in cooperative_users:
        if coop_user.telegram_user_id:
            send_telegram_message(coop_user.telegram_user_id, message, parse_mode='HTML')
        else:
            logger.warning("Cooperative manager %s has no telegram_user_id, skipping", coop_user.id)


# ---------------------------------------------------------------------------
# Telegram delivery helper
# ---------------------------------------------------------------------------

def send_telegram_message(telegram_user_id: str, message: str, parse_mode: str = 'Markdown') -> bool:
    """
    Send a message to a Telegram user via the Bot API.
    Uses synchronous requests to avoid asyncio complexity in sync tool handlers.
    """
    import os
    import requests

    bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
    if not bot_token:
        logger.error("TELEGRAM_BOT_TOKEN not set - cannot send payment message")
        return False

    try:
        response = requests.post(
            f"https://api.telegram.org/bot{bot_token}/sendMessage",
            json={
                'chat_id': telegram_user_id,
                'text': message,
                'parse_mode': parse_mode,
            },
            timeout=20,
        )
        if response.status_code == 200:
            logger.info("Telegram message sent to %s", telegram_user_id)
            return True
        else:
            logger.error("Telegram API error for %s: %s %s", telegram_user_id, response.status_code, response.text)
            return False
    except Exception as e:
        logger.error("Failed to send Telegram message to %s: %s", telegram_user_id, e)
        return False
