"""
Telegram bot handler for authenticated batch verification.

Implements secure verification flow:
1. Manager scans QR code → Opens Telegram deep link
2. Bot authenticates user, retrieves their DID
3. Bot shows verification form (interactive buttons)
4. Bot submits authenticated verification to API
"""

import os
import logging
from typing import Dict, Any, Optional
from datetime import datetime
from database.models import UserIdentity, CoffeeBatch, SessionLocal
from voice.verification.auth_checker import verify_user_authorization

logger = logging.getLogger(__name__)

# In-memory verification state (for webhook mode)
verification_sessions: Dict[int, Dict[str, Any]] = {}


async def handle_verify_deeplink(user_id: int, username: str, token: str) -> Dict[str, Any]:
    """
    Handle Telegram deep link: /start verify_{token}
    
    Args:
        user_id: Telegram user ID
        username: Telegram username
        token: Verification token (VRF-...)
        
    Returns:
        Dict with message and inline keyboard for verification
    """
    db = SessionLocal()
    try:
        # 1. Authenticate and authorize user
        user, error_message = verify_user_authorization(str(user_id), db)
        
        if error_message:
            # Map error messages to user-friendly Telegram responses
            if "not found" in error_message:
                return {
                    'message': (
                        "❌ *Authentication Required*\n\n"
                        "You must register with Voice Ledger before verifying batches.\n"
                        "Use /register to get started."
                    ),
                    'parse_mode': 'Markdown'
                }
            elif "pending" in error_message and "approval" in error_message:
                return {
                    'message': (
                        "⏳ *Pending Approval*\n\n"
                        "Your registration is pending admin approval.\n"
                        "You'll be notified when you can verify batches."
                    ),
                    'parse_mode': 'Markdown'
                }
            else:
                # Insufficient permissions
                return {
                    'message': (
                        f"⚠️ *Insufficient Permissions*\n\n"
                        f"Your role cannot verify batches.\n"
                        f"Only cooperative managers can verify deliveries."
                    ),
                    'parse_mode': 'Markdown'
                }
        
        # 2. Validate token and fetch batch
        batch = db.query(CoffeeBatch).filter_by(
            verification_token=token
        ).first()
        
        if not batch:
            return {
                'message': (
                    "❌ *Invalid Token*\n\n"
                    f"Token: `{token}`\n\n"
                    "This verification link is not valid. Please check the QR code."
                ),
                'parse_mode': 'Markdown'
            }
        
        # Check if already verified
        if batch.verification_used:
            verified_date = batch.verified_at.strftime('%b %d, %Y %H:%M') if batch.verified_at else 'Unknown'
            return {
                'message': (
                    "✅ *Already Verified*\n\n"
                    f"*Batch ID:* `{batch.batch_id}`\n"
                    f"*Verified:* {verified_date}\n"
                    f"*Verified Quantity:* {batch.verified_quantity} kg\n\n"
                    "This batch has already been verified."
                ),
                'parse_mode': 'Markdown'
            }
        
        # Check if expired
        if batch.verification_expires_at and batch.verification_expires_at < datetime.utcnow():
            return {
                'message': (
                    "⏰ *Token Expired*\n\n"
                    f"*Batch ID:* `{batch.batch_id}`\n"
                    f"*Expired:* {batch.verification_expires_at.strftime('%b %d, %Y %H:%M')}\n\n"
                    "This verification token has expired. Please contact the farmer to generate a new one."
                ),
                'parse_mode': 'Markdown'
            }
        
        # 3. Store verification session
        verification_sessions[user_id] = {
            'token': token,
            'batch_id': batch.id,
            'user_did': user.did,
            'user_role': user.role,
            'organization_id': user.organization_id,
            'started_at': datetime.utcnow()
        }
        
        # 4. Show batch details with verification options
        farmer_name = "Unknown"
        if batch.farmer:
            farmer_name = batch.farmer.name or "Unknown"
        
        expires_in = (batch.verification_expires_at - datetime.utcnow()).total_seconds() / 3600
        
        # Generate authenticated web form URL
        base_url = os.getenv('BASE_URL', 'http://localhost:8000')
        web_form_url = f"{base_url}/verify/{token}?telegram_user_id={user_id}"
        
        return {
            'message': (
                f"📦 *Batch Verification Request*\n\n"
                f"*Batch ID:* `{batch.batch_id}`\n"
                f"*Farmer:* {farmer_name}\n"
                f"*Variety:* {batch.variety}\n"
                f"*Claimed Quantity:* {batch.quantity_kg} kg\n"
                f"*Origin:* {batch.origin}\n"
                f"*Harvest Date:* {batch.harvest_date.strftime('%b %d, %Y') if batch.harvest_date else 'N/A'}\n"
                f"*Processing:* {batch.processing_method or 'N/A'}\n\n"
                f"⏱️ *Expires in:* {expires_in:.1f} hours\n\n"
                f"👤 *Verifying as:* {user.telegram_first_name} {user.telegram_last_name or ''}\n"
                f"🏢 *Organization:* {user.organization.name if user.organization else 'N/A'}\n\n"
                f"📸 Please verify the physical batch:\n"
                f"• Use buttons below for quick verification\n"
                f"• Or [open web form]({web_form_url}) to upload photos"
            ),
            'parse_mode': 'Markdown',
            'inline_keyboard': [
                [
                    {'text': f'✅ Verify Full Amount ({batch.quantity_kg} kg)', 'callback_data': f'verify_full_{token}'}
                ],
                [
                    {'text': '📝 Enter Custom Quantity', 'callback_data': f'verify_custom_{token}'}
                ],
                [
                    {'text': '❌ Reject (Discrepancy)', 'callback_data': f'verify_reject_{token}'}
                ]
            ]
        }
        
    finally:
        db.close()


async def handle_verification_callback(user_id: int, callback_data: str) -> Dict[str, Any]:
    """
    Handle verification callback button presses.
    
    Args:
        user_id: Telegram user ID
        callback_data: Button callback (verify_full_TOKEN, verify_custom_TOKEN, verify_reject_TOKEN)
        
    Returns:
        Dict with message or next action
    """
    # Parse callback
    parts = callback_data.split('_', 2)
    if len(parts) < 3:
        return {'message': '❌ Invalid callback data'}
    
    action = parts[1]  # full, custom, reject
    token = parts[2]
    
    # Check session
    session = verification_sessions.get(user_id)
    if not session or session['token'] != token:
        return {
            'message': (
                "⚠️ *Session Expired*\n\n"
                "Please scan the QR code again to start a new verification."
            ),
            'parse_mode': 'Markdown'
        }
    
    db = SessionLocal()
    try:
        batch = db.query(CoffeeBatch).filter_by(verification_token=token).first()
        
        if not batch:
            return {'message': '❌ Batch not found'}
        
        if action == 'full':
            # Verify with full claimed quantity
            return await _process_verification(
                db, batch, user_id, session, 
                verified_quantity=batch.quantity_kg,
                notes="Verified - quantity matches claim"
            )
        
        elif action == 'custom':
            # Request custom quantity input
            session['awaiting_quantity'] = True
            return {
                'message': (
                    f"📝 *Enter Actual Quantity*\n\n"
                    f"*Claimed:* {batch.quantity_kg} kg\n\n"
                    f"Please send the verified quantity in kg as a number.\n"
                    f"Example: `{batch.quantity_kg * 0.95:.1f}`"
                ),
                'parse_mode': 'Markdown'
            }
        
        elif action == 'reject':
            # Reject batch
            batch.status = 'REJECTED'
            batch.verification_used = True
            batch.verified_at = datetime.utcnow()
            batch.verified_by_did = session['user_did']
            batch.verification_notes = "Rejected by cooperative manager - quantity discrepancy or quality issue"
            db.commit()
            
            # Clean up session
            verification_sessions.pop(user_id, None)
            
            return {
                'message': (
                    f"❌ *Batch Rejected*\n\n"
                    f"*Batch ID:* `{batch.batch_id}`\n"
                    f"*Status:* REJECTED\n\n"
                    f"The farmer has been notified."
                ),
                'parse_mode': 'Markdown'
            }
        
        else:
            return {'message': '❌ Unknown action'}
    
    finally:
        db.close()


async def handle_quantity_message(user_id: int, text: str) -> Dict[str, Any]:
    """
    Handle custom quantity input from user.
    
    Args:
        user_id: Telegram user ID
        text: Message text (should be a number)
        
    Returns:
        Dict with verification result
    """
    session = verification_sessions.get(user_id)
    
    if not session or not session.get('awaiting_quantity'):
        # Not in verification flow
        return None
    
    # Parse quantity
    try:
        quantity = float(text.strip())
        if quantity <= 0:
            raise ValueError("Quantity must be positive")
    except ValueError:
        return {
            'message': (
                "⚠️ *Invalid Quantity*\n\n"
                "Please send a valid number (e.g., 45.5)\n"
                "Or use /cancel to abort."
            ),
            'parse_mode': 'Markdown'
        }
    
    db = SessionLocal()
    try:
        batch = db.query(CoffeeBatch).filter_by(
            verification_token=session['token']
        ).first()
        
        if not batch:
            verification_sessions.pop(user_id, None)
            return {'message': '❌ Batch not found'}
        
        # Show confirmation
        session['custom_quantity'] = quantity
        session['awaiting_confirmation'] = True
        session.pop('awaiting_quantity', None)
        
        difference = quantity - batch.quantity_kg
        diff_text = f"+{difference:.1f}" if difference > 0 else f"{difference:.1f}"
        diff_pct = (difference / batch.quantity_kg * 100) if batch.quantity_kg > 0 else 0
        
        return {
            'message': (
                f"📝 *Confirm Verification*\n\n"
                f"*Batch ID:* `{batch.batch_id}`\n"
                f"*Claimed:* {batch.quantity_kg} kg\n"
                f"*Verified:* {quantity} kg\n"
                f"*Difference:* {diff_text} kg ({diff_pct:+.1f}%)\n\n"
                f"Is this correct?"
            ),
            'parse_mode': 'Markdown',
            'inline_keyboard': [
                [
                    {'text': '✅ Confirm', 'callback_data': f'confirm_verify_{session["token"]}'},
                    {'text': '❌ Cancel', 'callback_data': f'cancel_verify_{session["token"]}'}
                ]
            ]
        }
    
    finally:
        db.close()


async def handle_confirmation_callback(user_id: int, callback_data: str) -> Dict[str, Any]:
    """Handle verification confirmation."""
    parts = callback_data.split('_', 2)
    action = parts[0]  # confirm or cancel
    token = parts[2]
    
    session = verification_sessions.get(user_id)
    if not session or session['token'] != token:
        return {'message': '⚠️ Session expired'}
    
    if action == 'cancel':
        session.pop('custom_quantity', None)
        session.pop('awaiting_confirmation', None)
        return {'message': '❌ Verification cancelled. Send new quantity or use /cancel to abort.'}
    
    # Confirm verification
    db = SessionLocal()
    try:
        batch = db.query(CoffeeBatch).filter_by(verification_token=token).first()
        if not batch:
            return {'message': '❌ Batch not found'}
        
        quantity = session.get('custom_quantity')
        if not quantity:
            return {'message': '❌ No quantity specified'}
        
        return await _process_verification(
            db, batch, user_id, session,
            verified_quantity=quantity,
            notes=f"Verified - actual quantity: {quantity} kg"
        )
    
    finally:
        db.close()


async def _process_verification(
    db: SessionLocal, 
    batch: CoffeeBatch, 
    user_id: int, 
    session: Dict[str, Any],
    verified_quantity: float,
    notes: str
) -> Dict[str, Any]:
    """
    Process and commit batch verification.
    
    Args:
        db: Database session
        batch: CoffeeBatch object
        user_id: Telegram user ID
        session: Verification session data
        verified_quantity: Verified quantity in kg
        notes: Verification notes
        
    Returns:
        Success message dict
    """
    # Update batch
    batch.status = 'VERIFIED'
    batch.verified_quantity = verified_quantity
    batch.verified_at = datetime.utcnow()
    batch.verified_by_did = session['user_did']
    batch.verification_used = True
    batch.verification_notes = notes
    batch.verifying_organization_id = session.get('organization_id')
    
    db.commit()
    
    # Mint batch token AFTER verification (cooperative custodial model)
    # Only verified batches get on-chain representation
    try:
        from blockchain.token_manager import mint_batch_token
        import os
        
        # Get cooperative wallet address (custodian)
        cooperative_wallet = os.getenv('COOPERATIVE_WALLET_ADDRESS') or os.getenv('WALLET_ADDRESS_SEP')
        
        if cooperative_wallet:
            # Get IPFS CID from commission event
            from database.models import EPCISEvent
            commission_event = db.query(EPCISEvent).filter(
                EPCISEvent.batch_id == batch.id,
                EPCISEvent.biz_step == 'commissioning'
            ).first()
            
            if commission_event and commission_event.ipfs_cid:
                # Mint token to cooperative
                token_id = mint_batch_token(
                    recipient=cooperative_wallet,
                    quantity_kg=verified_quantity,  # Use VERIFIED quantity, not claimed
                    batch_id=batch.batch_id,
                    metadata={
                        'variety': batch.variety,
                        'origin': batch.origin,
                        'processing_method': batch.processing_method,
                        'quality_grade': batch.quality_grade,
                        'farmer_did': batch.created_by_did,
                        'gtin': batch.gtin,
                        'gln': batch.gln,
                        'verified_by': session['user_did'],
                        'verification_date': datetime.utcnow().isoformat()
                    },
                    ipfs_cid=commission_event.ipfs_cid
                )
                
                # Store token ID in batch record
                if token_id:
                    batch.token_id = token_id
                    db.commit()
                    logger.info(f"✓ Batch {batch.batch_id} token minted: ID {token_id}")
                else:
                    logger.warning(f"⚠ Token minting returned None for batch {batch.batch_id}")
            else:
                logger.warning(f"⚠ No commission event IPFS CID for batch {batch.batch_id}")
    except Exception as e:
        # Don't fail verification if token minting fails
        logger.error(f"⚠ Token minting failed for batch {batch.batch_id}: {e}")
    
    # Clean up session
    verification_sessions.pop(user_id, None)
    
    # Issue verification credential signed by cooperative
    credential = None
    org_id = session.get('organization_id')
    if org_id and batch.created_by_did:
        try:
            from ssi.verification_credentials import issue_verification_credential
            credential = issue_verification_credential(
                batch_id=batch.batch_id,
                farmer_did=batch.created_by_did,
                organization_id=org_id,
                verified_quantity_kg=verified_quantity,
                claimed_quantity_kg=batch.quantity_kg,
                variety=batch.variety,
                origin=batch.origin,
                quality_notes=notes,
                verifier_did=session['user_did'],
                verifier_name=session.get('user_name', 'Manager'),
                has_photo_evidence=False
            )
            logger.info(f"Verification credential issued for batch {batch.batch_id}")
        except Exception as e:
            logger.error(f"Failed to issue verification credential: {e}")
    
    # Create verification EPCIS event (IPFS + blockchain anchored)
    org_id = session.get('organization_id')
    org_did = session.get('organization_did')
    org_name = session.get('organization_name')
    if org_id and org_did and org_name:
        try:
            from voice.verification.verification_events import create_verification_event
            event = create_verification_event(
                batch_id=batch.batch_id,
                verifier_did=session['user_did'],
                verifier_name=session.get('user_name', 'Manager'),
                organization_did=org_did,
                organization_name=org_name,
                verified_quantity_kg=verified_quantity,
                claimed_quantity_kg=batch.quantity_kg,
                quality_notes=notes,
                location=batch.origin or "",
                has_photo_evidence=False
            )
            if event:
                logger.info(
                    f"Verification event created: IPFS={event.ipfs_cid}, "
                    f"Blockchain={event.blockchain_tx_hash}"
                )
        except Exception as e:
            logger.error(f"Failed to create verification event: {e}")
    
    # TODO: Create farmer-cooperative relationship if first verification
    # TODO: Notify farmer of successful verification
    
    farmer_name = batch.farmer.name if batch.farmer else "Unknown"
    
    return {
        'message': (
            f"✅ *Verification Complete*\n\n"
            f"*Batch ID:* `{batch.batch_id}`\n"
            f"*Farmer:* {farmer_name}\n"
            f"*Verified Quantity:* {verified_quantity} kg\n"
            f"*Verified At:* {batch.verified_at.strftime('%b %d, %Y %H:%M')}\n\n"
            f"🎫 A verifiable credential has been issued.\n"
            f"📱 The farmer has been notified."
        ),
        'parse_mode': 'Markdown'
    }
