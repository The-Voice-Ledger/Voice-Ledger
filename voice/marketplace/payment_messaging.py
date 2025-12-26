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
    bank_details = ""
    if cooperative_org.bank_name:
        bank_details = (
            f"*Bank Details:*\n"
            f"Bank: {cooperative_org.bank_name}\n"
            f"Account #: `{cooperative_org.bank_account_number}`\n"
            f"Account Name: {cooperative_org.bank_account_name}\n"
        )
        
        if cooperative_org.bank_swift_code:
            bank_details += f"SWIFT/BIC: `{cooperative_org.bank_swift_code}`\n"
        
        if cooperative_org.bank_branch:
            bank_details += f"Branch: {cooperative_org.bank_branch}\n"
        
        bank_details += f"Reference: *{acceptance.acceptance_number}*\n"
    else:
        bank_details = (
            f"⚠️ *Bank details not on file*\n"
            f"Contact cooperative directly:\n"
            f"Phone: {cooperative_org.phone_number}\n"
        )
    
    # Build message
    message = f"""✅ *Offer Accepted Successfully!*

📋 *Transaction Details*
Acceptance #: `{acceptance.acceptance_number}`
Cooperative: *{cooperative_org.name}*
Location: {cooperative_org.location}

📦 *Order Details*
Quantity: {acceptance.quantity_accepted_kg:,.0f} kg
Price per kg: ${offer.price_per_kg:.2f}
*Total Amount: ${total_amount:,.2f} USD*
Payment Terms: {acceptance.payment_terms or 'Standard'}

💰 *PAYMENT INSTRUCTIONS*

{bank_details}

⚠️ *IMPORTANT:*
• Include reference number: `{acceptance.acceptance_number}`
• Keep receipt photo for confirmation
• Payment expected within 5 business days

⏱️ *Next Steps:*

1️⃣ Transfer ${total_amount:,.2f} to cooperative's bank account
2️⃣ After payment, send: `/confirm_payment {acceptance.acceptance_number}` with receipt photo
3️⃣ Cooperative will verify and confirm receipt
4️⃣ Coffee shipment begins to {rfq.delivery_location}

📞 *Cooperative Contact:*
Phone: {cooperative_org.phone_number}
Contact person: {cooperative_org.name}

💡 *Track Payment:*
Check status anytime: `/payment_status {acceptance.acceptance_number}`

🔗 Blockchain settlement record will be created when you confirm payment.
"""
    
    # TODO: Actually send via Telegram
    # await send_telegram_message(buyer.telegram_user_id, message)
    logger.info(f"Payment instructions sent to buyer {buyer.id} for acceptance {acceptance.acceptance_number}")
    print(f"\n📤 MESSAGE TO BUYER ({buyer.telegram_username}):\n{message}\n")


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
    
    message = f"""🎉 *Your Offer Has Been Accepted!*

📋 *Transaction Details*
Acceptance #: `{acceptance.acceptance_number}`
Buyer: *{buyer_name}*
{f"Country: {buyer_org.country}" if buyer_org and hasattr(buyer_org, 'country') else ""}

📦 *Order Details*
Quantity: {acceptance.quantity_accepted_kg:,.0f} kg
Price per kg: ${offer.price_per_kg:.2f}
*Total Amount: ${total_amount:,.2f} USD*
Delivery to: {rfq.delivery_location}

⏳ *AWAITING PAYMENT*

Expected: Within 5 business days
Method: Bank transfer
Your Account: {cooperative_org.bank_account_number or '[Update bank details]'}

📋 *What Happens Next:*

1️⃣ Buyer will transfer ${total_amount:,.2f} to your bank account
2️⃣ Buyer will confirm payment with receipt photo
3️⃣ You'll receive notification when buyer confirms
4️⃣ Check your bank account (2-5 business days)
5️⃣ Confirm receipt: `/confirm_receipt {acceptance.acceptance_number}`
6️⃣ Prepare and ship {acceptance.quantity_accepted_kg:,.0f} kg to {rfq.delivery_location}

📞 *Buyer Contact:*
Phone: {buyer.phone_number or 'Not provided'}
Contact: {buyer_name}

⚠️ *Important:*
• Reference number on transfer: `{acceptance.acceptance_number}`
• Verify exact amount: ${total_amount:,.2f}
• Do NOT ship before payment confirmed

💡 *Track Payment:*
Check status anytime: `/payment_status {acceptance.acceptance_number}`

🔗 Blockchain settlement record will be created automatically when buyer confirms payment.
"""
    
    # Get cooperative manager user IDs
    cooperative_users = buyer._sa_instance_state.session.query(UserIdentity).filter_by(
        organization_id=cooperative_org.id,
        role='COOPERATIVE_MANAGER'
    ).all()
    
    # TODO: Send to all cooperative managers
    # for coop_user in cooperative_users:
    #     await send_telegram_message(coop_user.telegram_user_id, message)
    
    logger.info(f"Payment notification sent to cooperative {cooperative_org.id} for acceptance {acceptance.acceptance_number}")
    print(f"\n📤 MESSAGE TO COOPERATIVE ({cooperative_org.name}):\n{message}\n")


# Helper for actual Telegram sending (to be implemented)
async def send_telegram_message(telegram_user_id: str, message: str, parse_mode: str = 'Markdown'):
    """
    Send message via Telegram bot.
    
    TODO: Integrate with actual Telegram bot API
    For now, just logs the message
    """
    logger.info(f"Sending Telegram message to {telegram_user_id}: {message[:100]}...")
    # In production:
    # bot.send_message(chat_id=telegram_user_id, text=message, parse_mode=parse_mode)
