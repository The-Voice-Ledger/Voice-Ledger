"""
Batch Verification Web Interface

Endpoints for cooperative managers to verify farmer batches.
Displays verification form with photo upload capability.
"""

from fastapi import APIRouter, HTTPException, Form, File, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse
from typing import Optional, List
from datetime import datetime
import os
import logging

from database.connection import SessionLocal
from database.models import CoffeeBatch, Organization, UserIdentity, VerificationEvidence
from voice.verification.verification_tokens import is_token_expired, is_token_valid
from voice.verification.auth_checker import verify_user_authorization

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/verify/{token}", response_class=HTMLResponse)
async def get_batch_verification_page(token: str, telegram_user_id: Optional[str] = None):
    """
    Display batch verification form.
    
    Requires authentication via telegram_user_id parameter.
    Only accessible to authorized cooperative managers.
    
    Shows batch details and verification form for cooperative managers.
    """
    # Validate token format
    if not is_token_valid(token):
        return _error_page("Invalid Token", "This verification link is invalid or has been tampered with.")
    
    # Look up batch
    db = SessionLocal()
    try:
        # SECURITY: Authenticate user if telegram_user_id provided
        authenticated_user = None
        if telegram_user_id:
            authenticated_user, error_message = verify_user_authorization(telegram_user_id, db)
            
            if error_message:
                # User is not authorized - show error page
                if "not found" in error_message:
                    return _error_page("Authentication Failed", error_message)
                elif "pending approval" in error_message:
                    return _error_page("Pending Approval", error_message)
                else:
                    return _error_page("Insufficient Permissions", error_message)
        
        batch = db.query(CoffeeBatch).filter_by(verification_token=token).first()
        
        if not batch:
            return _error_page("Batch Not Found", "No batch found with this verification token.")
        
        # Check expiration
        if batch.verification_expires_at and is_token_expired(batch.verification_expires_at):
            return _error_page(
                "Token Expired",
                f"This verification token expired on {batch.verification_expires_at.strftime('%Y-%m-%d %H:%M')}."
            )
        
        # Check if already verified
        if batch.verification_used:
            return _already_verified_page(batch)
        
        # Show verification form (with user info if authenticated)
        return _verification_form_page(batch, token, authenticated_user)
        
    finally:
        db.close()


@router.post("/verify/{token}")
async def submit_batch_verification(
    token: str,
    verified_quantity: float = Form(...),
    telegram_user_id: str = Form(...),  # REQUIRED for authentication
    verification_notes: Optional[str] = Form(None),
    photos: List[UploadFile] = File(default=[])
):
    """
    Process batch verification submission.
    
    SECURITY: Requires telegram_user_id for authentication.
    Validates user role and approval status before allowing verification.
    
    Updates batch status and issues credential.
    """
    if not is_token_valid(token):
        raise HTTPException(status_code=400, detail="Invalid token")
    
    db = SessionLocal()
    try:
        # SECURITY: Authenticate and authorize user
        user, error_message = verify_user_authorization(telegram_user_id, db)
        
        if error_message:
            # Determine appropriate HTTP status code
            if "not found" in error_message:
                status_code = 401
            else:
                status_code = 403
            raise HTTPException(status_code=status_code, detail=error_message)
        
        # Validate batch
        batch = db.query(CoffeeBatch).filter_by(verification_token=token).first()
        
        if not batch:
            raise HTTPException(status_code=404, detail="Batch not found")
        
        if batch.verification_expires_at and is_token_expired(batch.verification_expires_at):
            raise HTTPException(status_code=410, detail="Token expired")
        
        if batch.verification_used:
            raise HTTPException(status_code=409, detail="Already verified")
        
        # Update batch with authenticated user's DID
        batch.status = "VERIFIED"
        batch.verified_quantity = verified_quantity
        batch.verification_notes = verification_notes
        batch.verified_by_did = user.did  # Use authenticated user's DID
        batch.verifying_organization_id = user.organization_id
        batch.verified_at = datetime.utcnow()
        batch.verification_used = True
        batch.has_photo_evidence = len(photos) > 0
        
        logger.info(
            f"Batch {batch.batch_id} verified by {user.telegram_first_name} "
            f"(role={user.role}, did={user.did})"
        )
        
        # TODO: Photo upload to storage (S3/Spaces)
        # TODO: Credential issuance with organization DID as issuer
        # TODO: Create farmer-cooperative relationship on first verification
        # TODO: Send notifications to farmer and manager
        
        db.commit()
        
        return RedirectResponse(url=f"/verify/{token}/success", status_code=303)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Verification error: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail="Verification failed")
    finally:
        db.close()


@router.get("/verify/{token}/success", response_class=HTMLResponse)
async def verification_success_page(token: str):
    """Display verification success message."""
    return HTMLResponse(content="""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Verification Complete</title>
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <style>
            body {
                font-family: -apple-system, BlinkMacSystemFont, sans-serif;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                min-height: 100vh;
                display: flex;
                align-items: center;
                justify-content: center;
                padding: 20px;
            }
            .container {
                background: white;
                border-radius: 12px;
                box-shadow: 0 10px 40px rgba(0,0,0,0.2);
                padding: 40px;
                max-width: 500px;
                text-align: center;
            }
            .checkmark { font-size: 64px; }
            h1 { color: #388e3c; }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="checkmark">✅</div>
            <h1>Verification Complete!</h1>
            <p>The batch has been successfully verified and a credential has been issued.</p>
        </div>
    </body>
    </html>
    """)


def _error_page(title: str, message: str) -> HTMLResponse:
    """Generate error page HTML."""
    return HTMLResponse(content=f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>{title}</title>
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <style>
            body {{
                font-family: -apple-system, BlinkMacSystemFont, sans-serif;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                min-height: 100vh;
                display: flex;
                align-items: center;
                justify-content: center;
                padding: 20px;
            }}
            .container {{
                background: white;
                border-radius: 12px;
                box-shadow: 0 10px 40px rgba(0,0,0,0.2);
                padding: 40px;
                max-width: 500px;
                text-align: center;
            }}
            h1 {{ color: #d32f2f; }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>❌ {title}</h1>
            <p>{message}</p>
        </div>
    </body>
    </html>
    """, status_code=400)


def _already_verified_page(batch: CoffeeBatch) -> HTMLResponse:
    """Generate already verified page HTML."""
    verified_date = batch.verified_at.strftime('%Y-%m-%d %H:%M') if batch.verified_at else 'Unknown'
    return HTMLResponse(content=f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Already Verified</title>
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <style>
            body {{
                font-family: -apple-system, BlinkMacSystemFont, sans-serif;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                min-height: 100vh;
                display: flex;
                align-items: center;
                justify-content: center;
                padding: 20px;
            }}
            .container {{
                background: white;
                border-radius: 12px;
                box-shadow: 0 10px 40px rgba(0,0,0,0.2);
                padding: 40px;
                max-width: 500px;
                text-align: center;
            }}
            h1 {{ color: #388e3c; }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>✅ Already Verified</h1>
            <p><strong>Batch:</strong> {batch.batch_id}</p>
            <p><strong>Verified:</strong> {verified_date}</p>
            <p><strong>Quantity:</strong> {batch.verified_quantity} kg</p>
            <p>This batch has already been verified.</p>
        </div>
    </body>
    </html>
    """)


def _verification_form_page(batch: CoffeeBatch, token: str, user: Optional[UserIdentity] = None) -> HTMLResponse:
    """Generate verification form page HTML."""
    return HTMLResponse(content=f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Verify Batch</title>
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <style>
            * {{ box-sizing: border-box; }}
            body {{
                font-family: -apple-system, BlinkMacSystemFont, sans-serif;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                min-height: 100vh;
                padding: 20px;
            }}
            .container {{
                max-width: 800px;
                margin: 0 auto;
                background: white;
                border-radius: 12px;
                box-shadow: 0 10px 40px rgba(0,0,0,0.2);
                overflow: hidden;
            }}
            .header {{
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                padding: 30px;
                text-align: center;
            }}
            .content {{ padding: 30px; }}
            .batch-info {{
                background: #f5f5f5;
                border-radius: 8px;
                padding: 20px;
                margin-bottom: 30px;
            }}
            .info-row {{
                display: flex;
                justify-content: space-between;
                padding: 10px 0;
                border-bottom: 1px solid #e0e0e0;
            }}
            .info-row:last-child {{ border-bottom: none; }}
            .form-section {{
                margin-bottom: 25px;
            }}
            .form-section label {{
                display: block;
                font-weight: 600;
                margin-bottom: 8px;
            }}
            .form-section input,
            .form-section textarea {{
                width: 100%;
                padding: 12px;
                border: 2px solid #e0e0e0;
                border-radius: 8px;
                font-size: 16px;
            }}
            .submit-btn {{
                width: 100%;
                padding: 16px;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                border: none;
                border-radius: 8px;
                font-size: 18px;
                font-weight: 600;
                cursor: pointer;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>📦 Batch Verification</h1>
            </div>
            <div class="content">
                <div class="batch-info">
                    <h3>Batch Details</h3>
                    <div class="info-row">
                        <span>Batch ID:</span>
                        <span>{batch.batch_id}</span>
                    </div>
                    <div class="info-row">
                        <span>Variety:</span>
                        <span>{batch.variety}</span>
                    </div>
                    <div class="info-row">
                        <span>Claimed Quantity:</span>
                        <span>{batch.quantity_kg} kg</span>
                    </div>
                    <div class="info-row">
                        <span>Origin:</span>
                        <span>{batch.origin}</span>
                    </div>
                </div>
                
                {'<div style="background: #e8f5e9; padding: 15px; border-radius: 8px; margin-bottom: 20px;">' if user else ''}
                {'<p style="margin: 0; color: #2e7d32;"><strong>✓ Authenticated as:</strong> ' + (user.telegram_first_name or 'User') + ' (' + user.role + ')</p>' if user else ''}
                {'</div>' if user else ''}
                
                {'<div style="background: #fff3cd; padding: 15px; border-radius: 8px; margin-bottom: 20px;">' if not user else ''}
                {'<p style="margin: 0; color: #856404;"><strong>⚠️ Authentication Required:</strong> Add ?telegram_user_id=YOUR_ID to the URL</p>' if not user else ''}
                {'</div>' if not user else ''}
                
                <form method="POST" action="/verify/{token}" enctype="multipart/form-data">
                    <input type="hidden" name="telegram_user_id" value="{user.telegram_user_id if user else ''}"
                    
                    <div class="form-section">
                        <label>Actual Quantity (kg) *</label>
                        <input type="number" name="verified_quantity" step="0.1" value="{batch.quantity_kg}" required>
                    </div>
                    
                    <div class="form-section">
                        <label>Quality Notes</label>
                        <textarea name="verification_notes" rows="4" placeholder="Grade, moisture content, defects..."></textarea>
                    </div>
                    
                    <div class="form-section">
                        <label>Photos (Optional)</label>
                        <input type="file" name="photos" multiple accept="image/*" capture="environment">
                    </div>
                    
                    <button type="submit" class="submit-btn">✓ Verify and Issue Credential</button>
                </form>
            </div>
        </div>
    </body>
    </html>
    """)
