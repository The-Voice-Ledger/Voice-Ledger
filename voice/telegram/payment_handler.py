"""
Payment Handler for Telegram Bot - Manual Payment Coordination

Phase 4: Manual Payment Coordination with Blockchain Receipt
Date: December 23, 2025

Commands:
- /confirm_payment <acceptance_number> [photo] - Buyer confirms payment sent
- /confirm_receipt <acceptance_number> - Cooperative confirms payment received  
- /payment_status <acceptance_number> - Check payment status
- /dispute_payment <acceptance_number> [reason] - Raise payment dispute

Workflow:
1. Offer accepted → Payment instructions sent
2. Buyer pays via bank → /confirm_payment with receipt
3. System records settlement on blockchain
4. Cooperative checks bank → /confirm_receipt
5. Shipment begins
"""

import logging
import os
import sys
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
from pathlib import Path

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from database.models import (
    RFQAcceptance, RFQOffer, RFQ,
    BuyerCommitment, ContainerPool, ContainerOffering,
    UserIdentity, Organization, SessionLocal
)
from blockchain.settlement_manager import SettlementManager

logger = logging.getLogger(__name__)


async def handle_confirm_payment(
    user_id: int,
    message_text: str,
    photo_url: Optional[str] = None
) -> Dict[str, Any]:
    """
    Buyer confirms off-chain payment made.
    
    Usage: /confirm_payment ACC-000001 [photo]
    
    Workflow:
    1. Parse acceptance number from message
    2. Validate user is buyer for this acceptance
    3. Require receipt photo
    4. Update payment_status = CONFIRMED_BY_BUYER
    5. Record settlement on blockchain (SettlementContract)
    6. Notify cooperative
    
    Args:
        user_id: Telegram user ID (buyer)
        message_text: "/confirm_payment ACC-000001"
        photo_url: URL to bank receipt photo (S3/IPFS)
        
    Returns:
        Response dict with message for user
    """
    db = SessionLocal()
    
    try:
        # Parse acceptance number
        parts = message_text.strip().split()
        if len(parts) < 2:
            return {
                'message': (
                    "❌ *Invalid Format*\n\n"
                    "Usage: `/confirm_payment ACC-000001` with receipt photo\n\n"
                    "Please attach a photo of your bank transfer receipt."
                ),
                'parse_mode': 'Markdown'
            }
        
        acceptance_number = parts[1].upper()
        
        # Get user
        user = db.query(UserIdentity).filter_by(telegram_user_id=str(user_id)).first()
        if not user:
            return {'message': "❌ User not found. Please /register first."}
        
        # Get acceptance
        acceptance = db.query(RFQAcceptance).filter_by(
            acceptance_number=acceptance_number
        ).first()
        
        if not acceptance:
            return {
                'message': f"❌ Acceptance `{acceptance_number}` not found.",
                'parse_mode': 'Markdown'
            }
        
        # Verify user is the buyer
        rfq = db.query(RFQ).filter_by(id=acceptance.rfq_id).first()
        if rfq.buyer_id != user.id:
            return {
                'message': (
                    f"❌ *Access Denied*\n\n"
                    f"You are not the buyer for acceptance `{acceptance_number}`."
                ),
                'parse_mode': 'Markdown'
            }
        
        # Check if already confirmed
        if acceptance.payment_status == 'CONFIRMED_BY_BUYER':
            return {
                'message': (
                    f"ℹ️ Payment already confirmed for `{acceptance_number}`\n\n"
                    f"Waiting for cooperative to confirm receipt.\n"
                    f"Check status: `/payment_status {acceptance_number}`"
                ),
                'parse_mode': 'Markdown'
            }
        
        if acceptance.payment_status == 'RECEIVED':
            return {
                'message': (
                    f"✅ Payment already completed for `{acceptance_number}`\n\n"
                    f"Cooperative confirmed receipt on: "
                    f"{acceptance.payment_received_by_coop_at.strftime('%Y-%m-%d %H:%M')}"
                ),
                'parse_mode': 'Markdown'
            }
        
        # Require receipt photo
        if not photo_url:
            return {
                'message': (
                    f"📸 *Receipt Photo Required*\n\n"
                    f"Please attach a photo of your bank transfer receipt when sending:\n"
                    f"`/confirm_payment {acceptance_number}`\n\n"
                    f"This creates a verifiable record for both parties."
                ),
                'parse_mode': 'Markdown'
            }
        
        # Get offer details for amount calculation
        offer = db.query(RFQOffer).filter_by(id=acceptance.offer_id).first()
        total_amount = acceptance.quantity_accepted_kg * offer.price_per_kg
        
        # Get cooperative details
        cooperative_org = db.query(Organization).filter_by(id=offer.cooperative_id).first()
        
        # Record settlement on blockchain
        settlement_result = None
        if cooperative_org.wallet_address:
            try:
                settlement_manager = SettlementManager()
                settlement_result = settlement_manager.record_settlement(
                    acceptance_id=acceptance.id,
                    recipient_address=cooperative_org.wallet_address,
                    amount_usd=total_amount,
                    payment_method='BANK_TRANSFER'
                )
                
                # Update acceptance with settlement details
                acceptance.settlement_tx_hash = settlement_result['tx_hash']
                acceptance.settlement_recorded_at = datetime.utcnow()
                acceptance.settlement_blockchain_confirmed = settlement_result['confirmed']
                
                logger.info(
                    f"Settlement recorded on blockchain: {settlement_result['tx_hash']} "
                    f"for acceptance {acceptance_number}"
                )
                
            except Exception as e:
                logger.error(f"Failed to record settlement on blockchain: {e}")
                # Continue without blockchain (graceful degradation)
                settlement_result = None
        
        # Update acceptance
        acceptance.payment_status = 'CONFIRMED_BY_BUYER'
        acceptance.payment_receipt_url = photo_url
        acceptance.payment_confirmed_by_buyer_at = datetime.utcnow()
        acceptance.payment_method = 'BANK_TRANSFER'
        
        db.commit()
        
        # Prepare response for buyer
        response_message = (
            f"✅ *Payment Confirmation Recorded*\n\n"
            f"📋 Acceptance: `{acceptance_number}`\n"
            f"💰 Amount: ${total_amount:,.2f} USD\n"
            f"🏢 Cooperative: {cooperative_org.name}\n"
            f"📸 Receipt: Saved\n"
        )
        
        if settlement_result:
            response_message += (
                f"\n🔗 *Blockchain Receipt Created*\n"
                f"TX Hash: `{settlement_result['tx_hash'][:16]}...`\n"
                f"Block: {settlement_result['block_number']}\n"
                f"Timestamp: {datetime.fromtimestamp(settlement_result['timestamp']).strftime('%Y-%m-%d %H:%M UTC')}\n"
            )
        
        response_message += (
            f"\n⏳ *Next Steps:*\n"
            f"1. Cooperative will check their bank account\n"
            f"2. They will confirm receipt with `/confirm_receipt {acceptance_number}`\n"
            f"3. Coffee shipment begins\n\n"
            f"Check status: `/payment_status {acceptance_number}`"
        )
        
        # TODO: Send notification to cooperative
        # notify_cooperative_of_payment_confirmation(acceptance, cooperative_org, total_amount)
        
        return {
            'message': response_message,
            'parse_mode': 'Markdown'
        }
        
    except Exception as e:
        logger.error(f"Error in handle_confirm_payment: {e}", exc_info=True)
        return {
            'message': f"❌ Error processing payment confirmation: {str(e)}"
        }
    finally:
        db.close()


async def handle_confirm_receipt(
    user_id: int,
    message_text: str
) -> Dict[str, Any]:
    """
    Cooperative confirms payment received in bank account.
    
    Usage: /confirm_receipt ACC-000001
    
    Workflow:
    1. Parse acceptance number
    2. Validate user is cooperative for this acceptance
    3. Verify blockchain settlement exists (optional but encouraged)
    4. Update payment_status = RECEIVED
    5. Trigger shipment workflow
    
    Args:
        user_id: Telegram user ID (cooperative manager)
        message_text: "/confirm_receipt ACC-000001"
        
    Returns:
        Response dict with message for user
    """
    db = SessionLocal()
    
    try:
        # Parse acceptance number
        parts = message_text.strip().split()
        if len(parts) < 2:
            return {
                'message': (
                    "❌ *Invalid Format*\n\n"
                    "Usage: `/confirm_receipt ACC-000001`\n\n"
                    "Confirm after payment appears in your bank account."
                ),
                'parse_mode': 'Markdown'
            }
        
        acceptance_number = parts[1].upper()
        
        # Get user
        user = db.query(UserIdentity).filter_by(telegram_user_id=str(user_id)).first()
        if not user:
            return {'message': "❌ User not found. Please /register first."}
        
        # Get acceptance
        acceptance = db.query(RFQAcceptance).filter_by(
            acceptance_number=acceptance_number
        ).first()
        
        if not acceptance:
            return {
                'message': f"❌ Acceptance `{acceptance_number}` not found.",
                'parse_mode': 'Markdown'
            }
        
        # Get offer to verify cooperative
        offer = db.query(RFQOffer).filter_by(id=acceptance.offer_id).first()
        
        # Verify user is from the cooperative
        if user.organization_id != offer.cooperative_id:
            return {
                'message': (
                    f"❌ *Access Denied*\n\n"
                    f"You are not the cooperative for acceptance `{acceptance_number}`."
                ),
                'parse_mode': 'Markdown'
            }
        
        # Check if buyer confirmed payment first
        if acceptance.payment_status != 'CONFIRMED_BY_BUYER':
            return {
                'message': (
                    f"⏳ *Waiting for Buyer Confirmation*\n\n"
                    f"Acceptance: `{acceptance_number}`\n"
                    f"Status: {acceptance.payment_status}\n\n"
                    f"Buyer must first confirm payment with:\n"
                    f"`/confirm_payment {acceptance_number}`\n\n"
                    f"Then you can confirm receipt after payment arrives."
                ),
                'parse_mode': 'Markdown'
            }
        
        # Check if already confirmed
        if acceptance.payment_status == 'RECEIVED':
            return {
                'message': (
                    f"✅ Payment already confirmed as received for `{acceptance_number}`\n\n"
                    f"Confirmed on: {acceptance.payment_received_by_coop_at.strftime('%Y-%m-%d %H:%M')}"
                ),
                'parse_mode': 'Markdown'
            }
        
        # Calculate total
        total_amount = acceptance.quantity_accepted_kg * offer.price_per_kg
        
        # Get RFQ and buyer info
        rfq = db.query(RFQ).filter_by(id=acceptance.rfq_id).first()
        buyer = db.query(UserIdentity).filter_by(id=rfq.buyer_id).first()
        buyer_org = db.query(Organization).filter_by(id=buyer.organization_id).first() if buyer.organization_id else None
        
        # Check blockchain settlement
        blockchain_verified = False
        if acceptance.settlement_tx_hash:
            blockchain_verified = True
        
        # Update acceptance
        acceptance.payment_status = 'RECEIVED'
        acceptance.payment_received_by_coop_at = datetime.utcnow()
        acceptance.payment_released_at = datetime.utcnow()
        acceptance.delivery_status = 'PREPARING_SHIPMENT'
        
        db.commit()
        
        # Prepare response
        response_message = (
            f"✅ *Payment Receipt Confirmed*\n\n"
            f"📋 Acceptance: `{acceptance_number}`\n"
            f"💰 Amount: ${total_amount:,.2f} USD\n"
            f"🏢 Buyer: {buyer_org.name if buyer_org else buyer.telegram_first_name}\n"
        )
        
        if blockchain_verified:
            response_message += (
                f"\n🔗 *Blockchain Verified*\n"
                f"Settlement TX: `{acceptance.settlement_tx_hash[:16]}...`\n"
            )
        
        response_message += (
            f"\n📦 *Next Steps:*\n"
            f"1. Prepare coffee shipment ({acceptance.quantity_accepted_kg:,.0f} kg)\n"
            f"2. Ship to: {rfq.delivery_location}\n"
            f"3. Confirm shipment with `/confirm_shipment {acceptance_number}`\n"
            f"4. Buyer will confirm delivery\n\n"
            f"💡 Payment transaction complete!"
        )
        
        # TODO: Send notification to buyer
        # notify_buyer_of_receipt_confirmation(acceptance, buyer, total_amount)
        
        return {
            'message': response_message,
            'parse_mode': 'Markdown'
        }
        
    except Exception as e:
        logger.error(f"Error in handle_confirm_receipt: {e}", exc_info=True)
        return {
            'message': f"❌ Error processing receipt confirmation: {str(e)}"
        }
    finally:
        db.close()


async def handle_payment_status(
    user_id: int,
    message_text: str
) -> Dict[str, Any]:
    """
    Check payment status for an acceptance.
    
    Usage: /payment_status ACC-000001
    """
    db = SessionLocal()
    
    try:
        # Parse acceptance number
        parts = message_text.strip().split()
        if len(parts) < 2:
            return {
                'message': (
                    "❌ *Invalid Format*\n\n"
                    "Usage: `/payment_status ACC-000001`"
                ),
                'parse_mode': 'Markdown'
            }
        
        acceptance_number = parts[1].upper()
        
        # Get acceptance
        acceptance = db.query(RFQAcceptance).filter_by(
            acceptance_number=acceptance_number
        ).first()
        
        if not acceptance:
            return {
                'message': f"❌ Acceptance `{acceptance_number}` not found.",
                'parse_mode': 'Markdown'
            }
        
        # Get related entities
        offer = db.query(RFQOffer).filter_by(id=acceptance.offer_id).first()
        rfq = db.query(RFQ).filter_by(id=acceptance.rfq_id).first()
        cooperative_org = db.query(Organization).filter_by(id=offer.cooperative_id).first()
        
        total_amount = acceptance.quantity_accepted_kg * offer.price_per_kg
        
        # Build status message
        status_emoji = {
            'PENDING': '⏳',
            'CONFIRMED_BY_BUYER': '🔄',
            'RECEIVED': '✅',
            'DISPUTED': '⚠️'
        }
        
        emoji = status_emoji.get(acceptance.payment_status, '❓')
        
        message = (
            f"{emoji} *Payment Status*\n\n"
            f"📋 Acceptance: `{acceptance_number}`\n"
            f"💰 Amount: ${total_amount:,.2f} USD\n"
            f"🏢 Cooperative: {cooperative_org.name}\n"
            f"📦 Quantity: {acceptance.quantity_accepted_kg:,.0f} kg\n\n"
            f"*Payment Status:* {acceptance.payment_status}\n"
            f"*Delivery Status:* {acceptance.delivery_status}\n"
        )
        
        if acceptance.payment_confirmed_by_buyer_at:
            message += f"\n✅ Buyer confirmed: {acceptance.payment_confirmed_by_buyer_at.strftime('%Y-%m-%d %H:%M')}"
        
        if acceptance.payment_received_by_coop_at:
            message += f"\n✅ Cooperative confirmed: {acceptance.payment_received_by_coop_at.strftime('%Y-%m-%d %H:%M')}"
        
        if acceptance.settlement_tx_hash:
            message += f"\n\n🔗 *Blockchain Receipt*\nTX: `{acceptance.settlement_tx_hash[:16]}...`"
        
        if acceptance.payment_receipt_url:
            message += f"\n📸 Bank receipt: Uploaded"
        
        # Next steps
        if acceptance.payment_status == 'PENDING':
            message += (
                f"\n\n*Next Step:*\n"
                f"Buyer: `/confirm_payment {acceptance_number}` with receipt photo"
            )
        elif acceptance.payment_status == 'CONFIRMED_BY_BUYER':
            message += (
                f"\n\n*Next Step:*\n"
                f"Cooperative: Check bank, then `/confirm_receipt {acceptance_number}`"
            )
        elif acceptance.payment_status == 'RECEIVED':
            message += f"\n\n✅ Payment complete! Proceed with shipment."
        
        return {
            'message': message,
            'parse_mode': 'Markdown'
        }
        
    except Exception as e:
        logger.error(f"Error in handle_payment_status: {e}", exc_info=True)
        return {
            'message': f"❌ Error checking payment status: {str(e)}"
        }
    finally:
        db.close()


async def handle_dispute_payment(
    user_id: int,
    message_text: str
) -> Dict[str, Any]:
    """
    Raise a payment dispute.
    
    Usage: /dispute_payment ACC-000001 Payment not received after 7 days
    """
    db = SessionLocal()
    
    try:
        # Parse acceptance number and reason
        parts = message_text.strip().split(maxsplit=2)
        if len(parts) < 3:
            return {
                'message': (
                    "❌ *Invalid Format*\n\n"
                    "Usage: `/dispute_payment ACC-000001 <reason>`\n\n"
                    "Example:\n"
                    "`/dispute_payment ACC-000001 Payment not received after 7 days`"
                ),
                'parse_mode': 'Markdown'
            }
        
        acceptance_number = parts[1].upper()
        dispute_reason = parts[2]
        
        # Get user
        user = db.query(UserIdentity).filter_by(telegram_user_id=str(user_id)).first()
        if not user:
            return {'message': "❌ User not found. Please /register first."}
        
        # Get acceptance
        acceptance = db.query(RFQAcceptance).filter_by(
            acceptance_number=acceptance_number
        ).first()
        
        if not acceptance:
            return {
                'message': f"❌ Acceptance `{acceptance_number}` not found.",
                'parse_mode': 'Markdown'
            }
        
        # Update acceptance
        acceptance.payment_status = 'DISPUTED'
        acceptance.payment_dispute_reason = dispute_reason
        acceptance.payment_disputed_at = datetime.utcnow()
        
        db.commit()
        
        return {
            'message': (
                f"⚠️ *Payment Dispute Raised*\n\n"
                f"📋 Acceptance: `{acceptance_number}`\n"
                f"📝 Reason: {dispute_reason}\n\n"
                f"An administrator will review this dispute and contact both parties.\n\n"
                f"Evidence on record:\n"
                f"- Buyer receipt: {'Yes' if acceptance.payment_receipt_url else 'No'}\n"
                f"- Blockchain settlement: {'Yes' if acceptance.settlement_tx_hash else 'No'}\n"
                f"- Payment confirmed by buyer: {'Yes' if acceptance.payment_confirmed_by_buyer_at else 'No'}"
            ),
            'parse_mode': 'Markdown'
        }
        
    except Exception as e:
        logger.error(f"Error in handle_dispute_payment: {e}", exc_info=True)
        return {
            'message': f"❌ Error processing dispute: {str(e)}"
        }
    finally:
        db.close()


# ======================================================================
#  Pool-commitment payment handlers
# ======================================================================

async def handle_confirm_pool_payment(
    user_id: int,
    commitment_id: int,
    photo_url: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Buyer confirms bank transfer for a pool commitment.

    Usage (Telegram): /confirm_pool_payment <commitment_id> [photo]
    """
    db = SessionLocal()
    try:
        user = db.query(UserIdentity).filter_by(telegram_user_id=str(user_id)).first()
        if not user:
            return {"message": "❌ User not found. Please /register first."}

        commitment = db.query(BuyerCommitment).filter_by(id=commitment_id).first()
        if not commitment:
            return {"message": f"❌ Commitment #{commitment_id} not found."}

        if commitment.buyer_id != user.id:
            return {"message": "❌ You are not the buyer for this commitment."}

        if commitment.status == "PAID":
            return {"message": f"✅ Commitment #{commitment_id} is already paid."}

        if commitment.status not in ("COMMITTED", "PAYMENT_PENDING"):
            return {
                "message": (
                    f"❌ Cannot confirm payment — commitment status is "
                    f"{commitment.status}."
                )
            }

        pool = db.query(ContainerPool).filter_by(id=commitment.pool_id).first()
        offering = (
            db.query(ContainerOffering)
            .filter_by(id=pool.container_offering_id)
            .first()
            if pool
            else None
        )
        coop = (
            db.query(Organization)
            .filter_by(id=offering.cooperative_id)
            .first()
            if offering
            else None
        )

        # Record settlement on blockchain
        settlement_result = None
        if coop and coop.wallet_address:
            try:
                sm = SettlementManager()
                settlement_result = sm.record_commitment_settlement(
                    commitment_id=commitment.id,
                    recipient_address=coop.wallet_address,
                    amount_usd=commitment.total_amount,
                    payment_method="BANK_TRANSFER",
                )
                commitment.settlement_tx_hash = settlement_result["tx_hash"]
                commitment.settlement_recorded_at = datetime.utcnow()
                commitment.settlement_blockchain_confirmed = settlement_result[
                    "confirmed"
                ]
                logger.info(
                    "Pool settlement on-chain: commitment=%s tx=%s",
                    commitment.id,
                    settlement_result["tx_hash"],
                )
            except Exception as e:
                logger.error(f"Blockchain settlement failed for commitment: {e}")

        commitment.status = "PAID"
        commitment.payment_method = "BANK_TRANSFER"
        commitment.payment_receipt_url = photo_url
        commitment.payment_confirmed_by_buyer_at = datetime.utcnow()
        commitment.paid_at = datetime.utcnow()
        commitment.updated_at = datetime.utcnow()

        db.commit()

        msg = (
            f"✅ *Payment Confirmed*\n\n"
            f"Commitment: #{commitment.id}\n"
            f"Amount: ${commitment.total_amount:,.2f}\n"
            f"Cooperative: {coop.name if coop else 'Unknown'}\n"
        )
        if settlement_result:
            msg += (
                f"\n🔗 *Blockchain Receipt*\n"
                f"TX: `{settlement_result['tx_hash'][:16]}...`\n"
                f"Block: {settlement_result['block_number']}\n"
            )

        return {"message": msg, "parse_mode": "Markdown"}

    except Exception as e:
        logger.error(f"Error in handle_confirm_pool_payment: {e}", exc_info=True)
        return {"message": f"❌ Error: {str(e)}"}
    finally:
        db.close()


async def handle_confirm_pool_receipt(
    user_id: int,
    commitment_id: int,
) -> Dict[str, Any]:
    """Cooperative confirms pool payment received in bank."""
    db = SessionLocal()
    try:
        user = db.query(UserIdentity).filter_by(telegram_user_id=str(user_id)).first()
        if not user:
            return {"message": "❌ User not found."}

        commitment = db.query(BuyerCommitment).filter_by(id=commitment_id).first()
        if not commitment:
            return {"message": f"❌ Commitment #{commitment_id} not found."}

        pool = db.query(ContainerPool).filter_by(id=commitment.pool_id).first()
        offering = (
            db.query(ContainerOffering)
            .filter_by(id=pool.container_offering_id)
            .first()
            if pool
            else None
        )
        if not offering or user.organization_id != offering.cooperative_id:
            return {"message": "❌ Access denied — not your cooperative's container."}

        if commitment.status != "PAID":
            return {
                "message": (
                    f"⏳ Buyer has not yet confirmed payment "
                    f"(status: {commitment.status})."
                )
            }

        commitment.payment_received_by_coop_at = datetime.utcnow()
        commitment.updated_at = datetime.utcnow()
        db.commit()

        return {
            "message": (
                f"✅ *Receipt Confirmed*\n\n"
                f"Commitment #{commitment.id} — "
                f"${commitment.total_amount:,.2f}\n"
                f"Shipment preparation can begin."
            ),
            "parse_mode": "Markdown",
        }

    except Exception as e:
        logger.error(f"Error in handle_confirm_pool_receipt: {e}", exc_info=True)
        return {"message": f"❌ Error: {str(e)}"}
    finally:
        db.close()


# ======================================================================
#  Cooperative payout recording  (admin / internal)
# ======================================================================

async def handle_record_cooperative_payout(
    record_id: int,
    record_type: str = "acceptance",
    admin_user_id: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Record on-chain that WAGA forwarded funds to the cooperative's
    Ethiopian bank account.

    Called by an admin (via Telegram command, web agent, or internal tool).
    Blockchain TX proves the cooperative was paid.

    Args:
        record_id:   RFQAcceptance.id   (record_type="acceptance")
                     BuyerCommitment.id  (record_type="commitment")
        record_type: "acceptance" or "commitment"
        admin_user_id: Optional admin who triggered the payout
    """
    db = SessionLocal()
    try:
        if record_type == "acceptance":
            record = db.query(RFQAcceptance).filter_by(id=record_id).first()
            if not record:
                return {"message": f"❌ Acceptance #{record_id} not found."}
            # Determine cooperative from offer
            offer = db.query(RFQOffer).filter_by(id=record.offer_id).first()
            coop = (
                db.query(Organization).filter_by(id=offer.cooperative_id).first()
                if offer
                else None
            )
            amount = record.quantity_accepted_kg * offer.price_per_kg if offer else 0
        else:
            record = db.query(BuyerCommitment).filter_by(id=record_id).first()
            if not record:
                return {"message": f"❌ Commitment #{record_id} not found."}
            pool = db.query(ContainerPool).filter_by(id=record.pool_id).first()
            offering = (
                db.query(ContainerOffering)
                .filter_by(id=pool.container_offering_id)
                .first()
                if pool
                else None
            )
            coop = (
                db.query(Organization).filter_by(id=offering.cooperative_id).first()
                if offering
                else None
            )
            amount = record.total_amount

        if not coop:
            return {"message": "❌ Could not resolve cooperative."}

        if not coop.wallet_address:
            return {
                "message": (
                    f"❌ Cooperative *{coop.name}* has no wallet address. "
                    f"Please update their profile first."
                ),
                "parse_mode": "Markdown",
            }

        # Already recorded?
        if record.coop_payout_tx_hash:
            return {
                "message": (
                    f"ℹ️ Payout already recorded.\n"
                    f"TX: `{record.coop_payout_tx_hash[:16]}...`"
                ),
                "parse_mode": "Markdown",
            }

        # Record on blockchain
        sm = SettlementManager()
        if record_type == "acceptance":
            result = sm.record_cooperative_payout_for_acceptance(
                acceptance_id=record_id,
                recipient_address=coop.wallet_address,
                amount_usd=amount,
            )
        else:
            result = sm.record_cooperative_payout_for_commitment(
                commitment_id=record_id,
                recipient_address=coop.wallet_address,
                amount_usd=amount,
            )

        record.coop_payout_tx_hash = result["tx_hash"]
        record.coop_payout_at = datetime.utcnow()
        record.coop_payout_confirmed = result["confirmed"]
        record.updated_at = datetime.utcnow()
        db.commit()

        logger.info(
            "Cooperative payout recorded: %s #%s → %s  tx=%s",
            record_type,
            record_id,
            coop.name,
            result["tx_hash"],
        )

        return {
            "message": (
                f"✅ *Cooperative Payout Recorded*\n\n"
                f"Cooperative: {coop.name}\n"
                f"Amount: ${amount:,.2f}\n"
                f"TX: `{result['tx_hash'][:16]}...`\n"
                f"Block: {result['block_number']}\n\n"
                f"The cooperative's payment is now permanently recorded on-chain."
            ),
            "parse_mode": "Markdown",
        }

    except Exception as e:
        logger.error(f"Error recording cooperative payout: {e}", exc_info=True)
        return {"message": f"❌ Error: {str(e)}"}
    finally:
        db.close()
