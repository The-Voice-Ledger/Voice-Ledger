"""
Admin endpoints for registration approval
"""

from fastapi import APIRouter, HTTPException, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from database.models import SessionLocal, PendingRegistration, UserIdentity, Organization, Exporter, Buyer, UserReputation
from ssi.org_identity import generate_organization_did
from ssi.user_identity import get_or_create_user_identity
from datetime import datetime
import logging
import os
import requests

logger = logging.getLogger(__name__)
router = APIRouter()


async def send_approval_notification(telegram_user_id: int, registration_id: int, role: str, organization_name: str):
    """Send Telegram notification when registration is approved"""
    try:
        bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
        if not bot_token:
            logger.warning("TELEGRAM_BOT_TOKEN not set, skipping approval notification")
            return
        
        role_display = role.replace('_', ' ').title()
        
        message = f"""✅ *Registration Approved!*

Your Voice Ledger registration has been approved.

Registration ID: `REG-{registration_id:04d}`
Role: *{role_display}*
Organization: {organization_name}

You now have access to cooperative features. Use the bot to:
• View your organization details
• Verify coffee batches
• Issue credentials to farmers

Start by exploring available commands!"""
        
        response = requests.post(
            f"https://api.telegram.org/bot{bot_token}/sendMessage",
            json={
                'chat_id': telegram_user_id,
                'text': message,
                'parse_mode': 'Markdown'
            },
            timeout=30
        )
        response.raise_for_status()
        
        logger.info(f"Sent approval notification to user {telegram_user_id}")
        
    except Exception as e:
        logger.error(f"Failed to send approval notification: {e}", exc_info=True)


async def send_rejection_notification(telegram_user_id: int, registration_id: int, reason: str = None):
    """Send Telegram notification when registration is rejected"""
    try:
        bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
        if not bot_token:
            logger.warning("TELEGRAM_BOT_TOKEN not set, skipping rejection notification")
            return
        
        message = f"""❌ *Registration Rejected*

Your Voice Ledger registration has been rejected.

Registration ID: `REG-{registration_id:04d}`

{f'Reason: {reason}' if reason else 'Please contact support for more information.'}

You can submit a new registration request with /register"""
        
        response = requests.post(
            f"https://api.telegram.org/bot{bot_token}/sendMessage",
            json={
                'chat_id': telegram_user_id,
                'text': message,
                'parse_mode': 'Markdown'
            },
            timeout=30
        )
        response.raise_for_status()
        
        logger.info(f"Sent rejection notification to user {telegram_user_id}")
        
    except Exception as e:
        logger.error(f"Failed to send rejection notification: {e}", exc_info=True)


@router.get("/registrations", response_class=HTMLResponse)
async def list_registrations():
    """
    Show all pending registrations in HTML table with approve/reject buttons
    """
    db = SessionLocal()
    try:
        # Query all pending registrations
        pending = db.query(PendingRegistration)\
            .filter(PendingRegistration.status == 'PENDING')\
            .order_by(PendingRegistration.created_at.desc())\
            .all()
        
        # Generate HTML
        html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Registration Approvals - Voice Ledger Admin</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }}
        
        .container {{
            max-width: 1200px;
            margin: 0 auto;
        }}
        
        .header {{
            background: white;
            padding: 30px;
            border-radius: 12px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
            margin-bottom: 30px;
        }}
        
        h1 {{
            color: #333;
            font-size: 28px;
            margin-bottom: 10px;
        }}
        
        .subtitle {{
            color: #666;
            font-size: 14px;
        }}
        
        .stats {{
            display: flex;
            gap: 20px;
            margin-top: 20px;
        }}
        
        .stat-card {{
            background: #f8f9fa;
            padding: 15px 20px;
            border-radius: 8px;
            flex: 1;
        }}
        
        .stat-number {{
            font-size: 32px;
            font-weight: bold;
            color: #667eea;
        }}
        
        .stat-label {{
            color: #666;
            font-size: 12px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }}
        
        .registration-card {{
            background: white;
            border-radius: 12px;
            padding: 25px;
            margin-bottom: 20px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            transition: transform 0.2s, box-shadow 0.2s;
        }}
        
        .registration-card:hover {{
            transform: translateY(-2px);
            box-shadow: 0 4px 8px rgba(0,0,0,0.15);
        }}
        
        .reg-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 20px;
            padding-bottom: 15px;
            border-bottom: 2px solid #f0f0f0;
        }}
        
        .reg-id {{
            font-size: 18px;
            font-weight: bold;
            color: #667eea;
        }}
        
        .reg-date {{
            color: #999;
            font-size: 13px;
        }}
        
        .reg-content {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 15px;
            margin-bottom: 20px;
        }}
        
        .field {{
            padding: 10px;
            background: #f8f9fa;
            border-radius: 6px;
        }}
        
        .field-label {{
            font-size: 11px;
            color: #666;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            margin-bottom: 5px;
        }}
        
        .field-value {{
            font-size: 15px;
            color: #333;
            font-weight: 500;
        }}
        
        .role-badge {{
            display: inline-block;
            padding: 4px 12px;
            border-radius: 20px;
            font-size: 12px;
            font-weight: 600;
            background: #667eea;
            color: white;
        }}
        
        .actions {{
            display: flex;
            gap: 10px;
            justify-content: flex-end;
        }}
        
        .btn {{
            padding: 12px 24px;
            border: none;
            border-radius: 8px;
            font-size: 14px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.2s;
            text-decoration: none;
            display: inline-block;
        }}
        
        .btn-approve {{
            background: #10b981;
            color: white;
        }}
        
        .btn-approve:hover {{
            background: #059669;
            transform: scale(1.05);
        }}
        
        .btn-reject {{
            background: #ef4444;
            color: white;
        }}
        
        .btn-reject:hover {{
            background: #dc2626;
            transform: scale(1.05);
        }}
        
        .empty-state {{
            background: white;
            border-radius: 12px;
            padding: 60px;
            text-align: center;
        }}
        
        .empty-icon {{
            font-size: 64px;
            margin-bottom: 20px;
        }}
        
        .empty-text {{
            color: #666;
            font-size: 18px;
        }}
        
        @media (max-width: 768px) {{
            .reg-content {{
                grid-template-columns: 1fr;
            }}
            
            .stats {{
                flex-direction: column;
            }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🔐 Registration Approvals</h1>
            <p class="subtitle">Voice Ledger Admin Panel</p>
            <div class="stats">
                <div class="stat-card">
                    <div class="stat-number">{len(pending)}</div>
                    <div class="stat-label">Pending Requests</div>
                </div>
            </div>
        </div>
"""
        
        if pending:
            for reg in pending:
                role_display = reg.requested_role.replace('_', ' ').title()
                created_date = reg.created_at.strftime('%b %d, %Y at %I:%M %p')
                
                html += f"""
        <div class="registration-card">
            <div class="reg-header">
                <div class="reg-id">REG-{reg.id:04d}</div>
                <div class="reg-date">{created_date}</div>
            </div>
            
            <div class="reg-content">
                <div class="field">
                    <div class="field-label">Role</div>
                    <div class="field-value">
                        <span class="role-badge">{role_display}</span>
                    </div>
                </div>
                
                <div class="field">
                    <div class="field-label">Full Name</div>
                    <div class="field-value">{reg.full_name}</div>
                </div>
                
                <div class="field">
                    <div class="field-label">Organization</div>
                    <div class="field-value">{reg.organization_name}</div>
                </div>
                
                <div class="field">
                    <div class="field-label">Location</div>
                    <div class="field-value">{reg.location}</div>
                </div>
                
                <div class="field">
                    <div class="field-label">Phone Number</div>
                    <div class="field-value">{reg.phone_number}</div>
                </div>
                
                <div class="field">
                    <div class="field-label">Registration Number</div>
                    <div class="field-value">{reg.registration_number or 'Not provided'}</div>
                </div>
"""
                
                # Add role-specific fields
                if reg.requested_role == 'EXPORTER':
                    html += f"""
                <div class="field">
                    <div class="field-label">Export License</div>
                    <div class="field-value">{reg.export_license or 'Not provided'}</div>
                </div>
                
                <div class="field">
                    <div class="field-label">Primary Port</div>
                    <div class="field-value">{reg.port_access or 'Not provided'}</div>
                </div>
                
                <div class="field">
                    <div class="field-label">Shipping Capacity</div>
                    <div class="field-value">{reg.shipping_capacity_tons or 'Not provided'} tons/year</div>
                </div>
"""
                elif reg.requested_role == 'BUYER':
                    html += f"""
                <div class="field">
                    <div class="field-label">Business Type</div>
                    <div class="field-value">{(reg.business_type or 'Not provided').replace('_', ' ').title()}</div>
                </div>
                
                <div class="field">
                    <div class="field-label">Country</div>
                    <div class="field-value">{reg.country or 'Not provided'}</div>
                </div>
                
                <div class="field">
                    <div class="field-label">Target Volume</div>
                    <div class="field-value">{reg.target_volume_tons_annual or 'Not provided'} tons/year</div>
                </div>
"""
                
                html += f"""
            </div>
            
            {f'''
            <div class="field" style="margin-bottom: 20px;">
                <div class="field-label">Reason for Joining</div>
                <div class="field-value">{reg.reason}</div>
            </div>
            ''' if reg.reason else ''}
            
            <div class="actions">
                <form method="POST" action="/admin/registrations/{reg.id}/reject" style="display: inline;">
                    <button type="submit" class="btn btn-reject">✗ Reject</button>
                </form>
                <form method="POST" action="/admin/registrations/{reg.id}/approve" style="display: inline;">
                    <button type="submit" class="btn btn-approve">✓ Approve</button>
                </form>
            </div>
        </div>
"""
        else:
            html += """
        <div class="empty-state">
            <div class="empty-icon">✅</div>
            <div class="empty-text">No pending registrations</div>
        </div>
"""
        
        html += """
    </div>
</body>
</html>
"""
        
        return html
        
    finally:
        db.close()


@router.post("/registrations/{registration_id}/approve")
async def approve_registration(registration_id: int):
    """
    Approve a pending registration:
    1. Create or find organization
    2. Update user identity with role and organization
    3. Update registration status
    4. Send Telegram notification to user
    """
    db = SessionLocal()
    try:
        # Get the pending registration
        registration = db.query(PendingRegistration).filter_by(
            id=registration_id,
            status='PENDING'
        ).first()
        
        if not registration:
            raise HTTPException(status_code=404, detail="Registration not found or already processed")
        
        # TODO: Implement organization DID generation in next step
        # For now, we'll create organization without DID
        
        # Check if organization already exists
        existing_org = db.query(Organization).filter(
            Organization.name.ilike(f"%{registration.organization_name}%")
        ).first()
        
        if existing_org:
            organization_id = existing_org.id
            logger.info(f"Using existing organization: {existing_org.name} (ID: {existing_org.id})")
        else:
            # Create new organization with real DID
            org_type = {
                'COOPERATIVE_MANAGER': 'COOPERATIVE',
                'EXPORTER': 'EXPORTER',
                'BUYER': 'BUYER'
            }.get(registration.requested_role, 'COOPERATIVE')
            
            # Generate DID for organization
            logger.info(f"Generating DID for organization: {registration.organization_name}")
            org_identity = generate_organization_did()
            
            new_org = Organization(
                name=registration.organization_name,
                type=org_type,
                location=registration.location,
                phone_number=registration.phone_number,
                registration_number=registration.registration_number,
                did=org_identity['did'],
                public_key=org_identity['public_key'],
                encrypted_private_key=org_identity['encrypted_private_key']
            )
            db.add(new_org)
            db.flush()
            organization_id = new_org.id
            logger.info(f"Created organization: {new_org.name} (ID: {new_org.id}, DID: {new_org.did[:30]}...)")
            
            # Create role-specific records
            if registration.requested_role == 'EXPORTER':
                exporter = Exporter(
                    organization_id=organization_id,
                    export_license=registration.export_license,
                    port_access=registration.port_access,
                    shipping_capacity_tons=registration.shipping_capacity_tons,
                    active_shipping_lines=[],
                    customs_clearance_capability=False
                )
                db.add(exporter)
                logger.info(f"Created exporter record for org {organization_id}")
                
            elif registration.requested_role == 'BUYER':
                buyer = Buyer(
                    organization_id=organization_id,
                    business_type=registration.business_type,
                    country=registration.country,
                    target_volume_tons_annual=registration.target_volume_tons_annual,
                    quality_preferences=registration.quality_preferences,
                    import_licenses=[],
                    certifications_required=[]
                )
                db.add(buyer)
                logger.info(f"Created buyer record for org {organization_id}")
        
        # Get or create user identity with DID
        # This ensures every user has a DID (personal identity) AND links to organization DID (for verification authority)
        user_identity = get_or_create_user_identity(
            telegram_user_id=str(registration.telegram_user_id),
            telegram_first_name=registration.full_name.split()[0] if registration.full_name else "User",
            telegram_last_name=" ".join(registration.full_name.split()[1:]) if len(registration.full_name.split()) > 1 else None,
            db_session=db
        )
        
        logger.info(f"User identity: {'created' if user_identity['created'] else 'found'} (DID: {user_identity['did'][:30]}...)")
        
        # Update user with role and organization
        user = db.query(UserIdentity).filter_by(
            telegram_user_id=str(registration.telegram_user_id)
        ).first()
        
        # Extract language preference from reason field
        preferred_language = 'en'  # Default
        if registration.reason and registration.reason.startswith('[LANG:'):
            try:
                lang_marker = registration.reason.split(']')[0]
                preferred_language = lang_marker.replace('[LANG:', '')
            except:
                pass
        
        user.role = registration.requested_role
        user.organization_id = organization_id
        user.is_approved = True
        user.approved_at = datetime.utcnow()
        user.preferred_language = preferred_language
        user.language_set_at = datetime.utcnow()
        logger.info(f"Updated user: {user.telegram_first_name} - Role: {user.role}, Org: {organization_id}, Lang: {preferred_language}")
        
        # Initialize reputation record for user
        existing_reputation = db.query(UserReputation).filter_by(user_id=user.id).first()
        if not existing_reputation:
            reputation = UserReputation(
                user_id=user.id,
                completed_transactions=0,
                total_volume_kg=0,
                on_time_deliveries=0,
                quality_disputes=0,
                average_rating=None,
                reputation_level='BRONZE'
            )
            db.add(reputation)
            logger.info(f"Initialized reputation record for user {user.id}")
        
        # Update registration status
        registration.status = 'APPROVED'
        registration.reviewed_at = datetime.utcnow()
        
        db.commit()
        
        # Send Telegram notification to user
        await send_approval_notification(
            telegram_user_id=registration.telegram_user_id,
            registration_id=registration_id,
            role=registration.requested_role,
            organization_name=registration.organization_name
        )
        
        logger.info(f"Approved registration REG-{registration_id:04d}")
        
        # Redirect back to registrations page
        return RedirectResponse(url="/admin/registrations", status_code=303)
        
    except Exception as e:
        db.rollback()
        logger.error(f"Error approving registration: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()


@router.post("/registrations/{registration_id}/reject")
async def reject_registration(registration_id: int):
    """
    Reject a pending registration
    """
    db = SessionLocal()
    try:
        registration = db.query(PendingRegistration).filter_by(
            id=registration_id,
            status='PENDING'
        ).first()
        
        if not registration:
            raise HTTPException(status_code=404, detail="Registration not found or already processed")
        
        registration.status = 'REJECTED'
        registration.reviewed_at = datetime.utcnow()
        registration.rejection_reason = "Rejected by admin"
        
        db.commit()
        
        # Send Telegram notification to user
        await send_rejection_notification(
            telegram_user_id=registration.telegram_user_id,
            registration_id=registration_id,
            reason=registration.rejection_reason
        )
        
        logger.info(f"Rejected registration REG-{registration_id:04d}")
        
        return RedirectResponse(url="/admin/registrations", status_code=303)
        
    except Exception as e:
        db.rollback()
        logger.error(f"Error rejecting registration: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()
