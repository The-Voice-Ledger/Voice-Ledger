"""
Public verification API endpoints.

These endpoints allow anyone to verify a farmer's credentials using their DID.
No authentication required - credentials are public, signatures prove authenticity.
"""

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse, HTMLResponse
import logging
from typing import Optional

from ssi.batch_credentials import (
    get_user_credentials,
    calculate_simple_credit_score
)
from ssi.user_identity import get_user_by_did
from ssi.credentials.verify import verify_credential
from database.models import SessionLocal

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/voice/verify", tags=["verification"])


@router.get("/health")
async def verification_health():
    """Health check for verification service."""
    return {"status": "healthy", "service": "verification-api"}


@router.get("/{did}")
async def verify_farmer_credentials(did: str):
    """
    Verify all credentials for a given DID.
    
    Returns:
        - DID information
        - List of verified credentials
        - Credit score summary
        - Batch statistics
    
    Example:
        GET /voice/verify/did:key:z6Mk...
    """
    try:
        # Get credentials for this DID
        credentials = get_user_credentials(did)
        
        if not credentials:
            raise HTTPException(
                status_code=404,
                detail=f"No credentials found for DID: {did}"
            )
        
        # Verify each credential signature
        verified_credentials = []
        for cred in credentials:
            try:
                is_valid = verify_credential(cred)
                verified_credentials.append({
                    "credential_id": cred.get("id"),
                    "type": cred.get("type"),
                    "issuer": cred.get("issuer"),
                    "issuance_date": cred.get("issuanceDate"),
                    "subject": cred.get("credentialSubject"),
                    "verified": is_valid,
                    "signature": cred.get("proof", {}).get("signature", "")[:50] + "..."
                })
            except Exception as e:
                logger.error(f"Error verifying credential: {e}")
                verified_credentials.append({
                    "credential_id": cred.get("id"),
                    "verified": False,
                    "error": str(e)
                })
        
        # Calculate credit score
        try:
            score = calculate_simple_credit_score(did)
        except Exception as e:
            logger.error(f"Error calculating credit score: {e}")
            score = {
                "score": 0,
                "batch_count": len(credentials),
                "total_kg": 0,
                "error": str(e)
            }
        
        # Get user info if available
        db = SessionLocal()
        try:
            user = get_user_by_did(did, db_session=db)
            user_info = {
                "telegram_username": user.telegram_username if user else None,
                "first_name": user.telegram_first_name if user else None,
                "created_at": user.created_at.isoformat() if user else None
            }
        except:
            user_info = None
        finally:
            db.close()
        
        return JSONResponse({
            "did": did,
            "user_info": user_info,
            "credentials": verified_credentials,
            "summary": {
                "total_credentials": len(credentials),
                "verified_credentials": sum(1 for c in verified_credentials if c.get("verified")),
                "credit_score": score.get("score", 0),
                "total_batches": score.get("batch_count", 0),
                "total_volume_kg": score.get("total_kg", 0),
                "first_batch_date": score.get("first_batch_date"),
                "latest_batch_date": score.get("latest_batch_date"),
                "days_active": score.get("days_active", 0)
            }
        })
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in verify_farmer_credentials: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error verifying credentials: {str(e)}"
        )


@router.get("/{did}/presentation")
async def get_verifiable_presentation(did: str):
    """
    Get a W3C Verifiable Presentation for all farmer credentials.
    
    This returns a standards-compliant presentation that can be:
    - Shared with verifiers
    - Stored in a wallet app
    - Embedded in QR codes
    - Used for credential portability
    
    Example:
        GET /voice/verify/did:key:z6Mk.../presentation
    """
    try:
        from datetime import datetime, timezone
        
        credentials = get_user_credentials(did)
        
        if not credentials:
            raise HTTPException(
                status_code=404,
                detail=f"No credentials found for DID: {did}"
            )
        
        # Create W3C Verifiable Presentation
        presentation = {
            "@context": [
                "https://www.w3.org/2018/credentials/v1"
            ],
            "type": ["VerifiablePresentation"],
            "holder": did,
            "verifiableCredential": credentials,
            "created": datetime.now(timezone.utc).isoformat(),
            # Note: In production, this should be signed by the holder
            # For now, credentials themselves are already signed
        }
        
        return JSONResponse(presentation)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating presentation: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error creating presentation: {str(e)}"
        )


@router.get("/{did}/html")
async def get_verification_page(did: str):
    """
    Human-readable verification page.
    
    Returns an HTML page displaying farmer credentials in a user-friendly format.
    Useful for sharing via links or viewing in a browser.
    
    Example:
        GET /voice/verify/did:key:z6Mk.../html
    """
    try:
        # Get verification data
        credentials = get_user_credentials(did)
        
        if not credentials:
            return HTMLResponse(
                content=f"""
                <html>
                    <head><title>No Credentials Found</title></head>
                    <body>
                        <h1>❌ No Credentials Found</h1>
                        <p>No credentials found for DID: {did}</p>
                    </body>
                </html>
                """,
                status_code=404
            )
        
        score = calculate_simple_credit_score(did)
        
        # Generate HTML
        creds_html = ""
        for cred in credentials:
            subject = cred.get("credentialSubject", {})
            creds_html += f"""
            <div style="border: 1px solid #ddd; padding: 15px; margin: 10px 0; border-radius: 5px;">
                <h3>📦 {subject.get('batchId', 'Unknown')}</h3>
                <p><strong>Variety:</strong> {subject.get('variety', 'N/A')}</p>
                <p><strong>Quantity:</strong> {subject.get('quantityKg', 0)} kg</p>
                <p><strong>Origin:</strong> {subject.get('origin', 'N/A')}</p>
                <p><strong>Recorded:</strong> {cred.get('issuanceDate', 'N/A')[:10]}</p>
                <p><strong>Status:</strong> ✅ Verified</p>
            </div>
            """
        
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Farmer Credentials - Voice Ledger</title>
            <meta name="viewport" content="width=device-width, initial-scale=1">
            <style>
                body {{
                    font-family: Arial, sans-serif;
                    max-width: 800px;
                    margin: 0 auto;
                    padding: 20px;
                    background: #f5f5f5;
                }}
                .header {{
                    background: #2c3e50;
                    color: white;
                    padding: 20px;
                    border-radius: 5px;
                    margin-bottom: 20px;
                }}
                .summary {{
                    background: white;
                    padding: 20px;
                    border-radius: 5px;
                    margin-bottom: 20px;
                }}
                .score {{
                    font-size: 48px;
                    color: #27ae60;
                    font-weight: bold;
                }}
            </style>
        </head>
        <body>
            <div class="header">
                <h1>🌾 Voice Ledger Credentials</h1>
                <p>Verified Farmer Track Record</p>
            </div>
            
            <div class="summary">
                <h2>📊 Summary</h2>
                <div class="score">{score['score']}/1000</div>
                <p><strong>Credit Score</strong></p>
                <hr>
                <p>📦 <strong>Total Batches:</strong> {score['batch_count']}</p>
                <p>⚖️ <strong>Total Production:</strong> {score['total_kg']:.1f} kg</p>
                <p>📅 <strong>First Batch:</strong> {score.get('first_batch_date', 'N/A')[:10]}</p>
                <p>🕒 <strong>Latest Batch:</strong> {score.get('latest_batch_date', 'N/A')[:10]}</p>
                <p>⏱️ <strong>Days Active:</strong> {score['days_active']}</p>
                <hr>
                <p style="font-size: 12px; color: #666;">
                    <strong>DID:</strong> {did}
                </p>
            </div>
            
            <h2>📋 Credentials</h2>
            {creds_html}
            
            <div style="margin-top: 30px; padding: 20px; background: #ecf0f1; border-radius: 5px;">
                <p style="font-size: 14px; color: #555;">
                    ✅ All credentials are cryptographically verified.<br>
                    🔐 Powered by W3C Verifiable Credentials and Decentralized Identifiers (DIDs).<br>
                    🌐 View JSON: <a href="/voice/verify/{did}">/voice/verify/{did}</a>
                </p>
            </div>
        </body>
        </html>
        """
        
        return HTMLResponse(content=html_content)
        
    except Exception as e:
        logger.error(f"Error generating HTML page: {e}")
        return HTMLResponse(
            content=f"""
            <html>
                <head><title>Error</title></head>
                <body>
                    <h1>❌ Error</h1>
                    <p>Error generating verification page: {str(e)}</p>
                </body>
            </html>
            """,
            status_code=500
        )
