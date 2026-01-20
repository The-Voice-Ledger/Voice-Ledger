"""
Mini App API endpoints for Voice Ledger.

Provides RESTful API for Telegram Mini Apps to query batch data.
"""

import logging
from typing import List, Dict, Any
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse
from pathlib import Path
from database import get_db
from database.models import CoffeeBatch, EPCISEvent, UserIdentity, VerificationEvidence
from sqlalchemy.orm import joinedload

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/miniapp", tags=["miniapp"])


def get_user_batches(db, user_id: int) -> List[Dict[str, Any]]:
    """
    Get all coffee batches for a user with COMPLETE details.
    
    Args:
        db: Database session
        user_id: Telegram user ID
        
    Returns:
        List of batch dictionaries with ALL relevant fields from CoffeeBatch model
    """
    try:
        # Get user identity
        user_identity = db.query(UserIdentity).filter(
            UserIdentity.telegram_user_id == str(user_id)
        ).first()
        
        if not user_identity:
            logger.warning(f"User identity not found for telegram_user_id: {user_id}")
            return []
        
        # Query batches created by this user
        batches = db.query(CoffeeBatch).filter(
            CoffeeBatch.created_by_user_id == user_identity.id
        ).order_by(CoffeeBatch.created_at.desc()).all()
        
        # Convert to dictionaries with ALL relevant fields from the model
        batch_list = []
        for batch in batches:
            # Determine display status
            display_status = 'pending'
            if batch.verified_at:
                display_status = 'verified'
            elif batch.status == 'REJECTED':
                display_status = 'rejected'
            
            # Check if shipped (has shipping events)
            shipping_events = db.query(EPCISEvent).filter(
                EPCISEvent.batch_id == batch.id,
                EPCISEvent.biz_step == 'shipping'
            ).first()
            if shipping_events:
                display_status = 'shipped'
            
            batch_dict = {
                # Core identifiers
                'id': batch.id,
                'batch_id': batch.batch_id,
                'gtin': batch.gtin,
                'gln': batch.gln,
                'batch_number': batch.batch_number,
                
                # Quantity and origin
                'quantity_kg': float(batch.quantity_kg) if batch.quantity_kg else 0,
                'origin': batch.origin,
                'origin_country': batch.origin_country,
                'origin_region': batch.origin_region,
                'farm_name': batch.farm_name,
                
                # Coffee attributes
                'variety': batch.variety,
                'harvest_date': batch.harvest_date.isoformat() if batch.harvest_date else None,
                'processing_method': batch.processing_method,
                'process_method': batch.process_method,
                'quality_grade': batch.quality_grade,
                
                # Blockchain
                'token_id': batch.token_id,
                
                # Verification status
                'status': batch.status,
                'display_status': display_status,
                'verification_token': batch.verification_token,
                'verification_expires_at': batch.verification_expires_at.isoformat() if batch.verification_expires_at else None,
                'verification_used': batch.verification_used,
                'verified_quantity': float(batch.verified_quantity) if batch.verified_quantity else None,
                'verified_by_did': batch.verified_by_did,
                'verified_at': batch.verified_at.isoformat() if batch.verified_at else None,
                'verification_notes': batch.verification_notes,
                'has_photo_evidence': batch.has_photo_evidence,
                'verifying_organization_id': batch.verifying_organization_id,
                
                # Timestamps
                'created_at': batch.created_at.isoformat() if batch.created_at else None,
                'updated_at': batch.updated_at.isoformat() if batch.updated_at else None,
                
                # Owner info
                'created_by_user_id': batch.created_by_user_id,
                'created_by_did': batch.created_by_did,
                'farmer_id': batch.farmer_id
            }
            
            batch_list.append(batch_dict)
        
        return batch_list
        
    except Exception as e:
        logger.error(f"Error getting user batches: {e}", exc_info=True)
        return []


def get_batch_details(db, batch_identifier: str, user_id: int) -> Dict[str, Any]:
    """
    Get detailed information for a specific batch with ALL fields and related data.
    
    Args:
        db: Database session
        batch_identifier: GTIN or batch_id
        user_id: Telegram user ID (for authorization)
        
    Returns:
        Dictionary with complete batch details, EPCIS events, and relationships
    """
    try:
        # Get user identity
        user_identity = db.query(UserIdentity).filter(
            UserIdentity.telegram_user_id == str(user_id)
        ).first()
        
        if not user_identity:
            raise ValueError("User not found")
        
        # Find batch by GTIN or batch_id
        batch = db.query(CoffeeBatch).filter(
            (CoffeeBatch.gtin == batch_identifier) | 
            (CoffeeBatch.batch_id == batch_identifier)
        ).first()
        
        if not batch:
            raise ValueError(f"Batch not found: {batch_identifier}")
        
        # Check authorization (user must be creator)
        if batch.created_by_user_id != user_identity.id:
            raise ValueError("Unauthorized access to batch")
        
        # Get EPCIS events for this batch
        events = db.query(EPCISEvent).filter(
            EPCISEvent.batch_id == batch.id
        ).order_by(EPCISEvent.event_time.asc()).all()
        
        # Get verification evidence (if table exists)
        try:
            evidence_items = db.query(VerificationEvidence).filter(
                VerificationEvidence.batch_id == batch.id
            ).all()
        except Exception as e:
            logger.warning(f"Could not load verification evidence: {e}")
            evidence_items = []
        
        # Determine display status
        display_status = 'pending'
        if batch.verified_at:
            display_status = 'verified'
        elif batch.status == 'REJECTED':
            display_status = 'rejected'
        
        if any(e.biz_step == 'shipping' for e in events):
            display_status = 'shipped'
        
        # Build complete response
        result = {
            'batch': {
                # Core identifiers
                'id': batch.id,
                'batch_id': batch.batch_id,
                'gtin': batch.gtin,
                'gln': batch.gln,
                'batch_number': batch.batch_number,
                
                # Quantity and origin
                'quantity_kg': float(batch.quantity_kg) if batch.quantity_kg else 0,
                'origin': batch.origin,
                'origin_country': batch.origin_country,
                'origin_region': batch.origin_region,
                'farm_name': batch.farm_name,
                
                # Coffee attributes
                'variety': batch.variety,
                'harvest_date': batch.harvest_date.isoformat() if batch.harvest_date else None,
                'processing_method': batch.processing_method,
                'process_method': batch.process_method,
                'quality_grade': batch.quality_grade,
                
                # Blockchain
                'token_id': batch.token_id,
                
                # Verification status
                'status': batch.status,
                'display_status': display_status,
                'verification_token': batch.verification_token,
                'verification_expires_at': batch.verification_expires_at.isoformat() if batch.verification_expires_at else None,
                'verification_used': batch.verification_used,
                'verified_quantity': float(batch.verified_quantity) if batch.verified_quantity else None,
                'verified_by_did': batch.verified_by_did,
                'verified_at': batch.verified_at.isoformat() if batch.verified_at else None,
                'verification_notes': batch.verification_notes,
                'has_photo_evidence': batch.has_photo_evidence,
                'verifying_organization_id': batch.verifying_organization_id,
                
                # Timestamps
                'created_at': batch.created_at.isoformat() if batch.created_at else None,
                'updated_at': batch.updated_at.isoformat() if batch.updated_at else None,
                
                # Owner info
                'created_by_user_id': batch.created_by_user_id,
                'created_by_did': batch.created_by_did,
                'farmer_id': batch.farmer_id
            },
            'events': [],
            'evidence': []
        }
        
        # Add EPCIS events
        for event in events:
            result['events'].append({
                'id': event.id,
                'event_hash': event.event_hash,
                'event_type': event.event_type,
                'event_time': event.event_time.isoformat() if event.event_time else None,
                'biz_step': event.biz_step,
                'biz_location': event.biz_location,
                'ipfs_cid': event.ipfs_cid,
                'blockchain_tx_hash': event.blockchain_tx_hash,
                'blockchain_confirmed': event.blockchain_confirmed,
                'blockchain_confirmed_at': event.blockchain_confirmed_at.isoformat() if event.blockchain_confirmed_at else None,
                'created_at': event.created_at.isoformat() if event.created_at else None
            })
        
        # Add verification evidence
        for item in evidence_items:
            result['evidence'].append({
                'id': item.id,
                'evidence_type': item.evidence_type,
                'content_hash': item.content_hash,
                'storage_url': item.storage_url,
                'created_at': item.created_at.isoformat() if item.created_at else None
            })
        
        return result
        
    except Exception as e:
        logger.error(f"Error getting batch details: {e}", exc_info=True)
        raise


@router.get("/batches")
async def list_batches(
    user_id: int = Query(..., description="Telegram user ID")
):
    """
    Get list of all batches for a user.
    
    Query Parameters:
        user_id: Telegram user ID from initDataUnsafe
        
    Returns:
        JSON with batches array
    """
    try:
        with get_db() as db:
            batches = get_user_batches(db, user_id)
        
        return {
            "success": True,
            "batches": batches,
            "count": len(batches)
        }
        
    except Exception as e:
        logger.error(f"Error in list_batches: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/batch/{batch_identifier}")
async def get_batch(
    batch_identifier: str,
    user_id: int = Query(..., description="Telegram user ID")
):
    """
    Get detailed information for a specific batch.
    
    Path Parameters:
        batch_identifier: GTIN or batch_id
        
    Query Parameters:
        user_id: Telegram user ID from initDataUnsafe
        
    Returns:
        JSON with batch details and events
    """
    try:
        with get_db() as db:
            details = get_batch_details(db, batch_identifier, user_id)
        
        return {
            "success": True,
            **details
        }
        
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error in get_batch: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/trace/{batch_identifier}")
async def trace_batch(
    batch_identifier: str,
    user_id: int = Query(..., description="Telegram user ID")
):
    """
    Get traceability information for a specific batch (alias for get_batch).
    Used by the trace mini app for supply chain visualization.
    
    Path Parameters:
        batch_identifier: GTIN or batch_id
        
    Query Parameters:
        user_id: Telegram user ID from initDataUnsafe
        
    Returns:
        JSON with batch details, EPCIS events timeline, and blockchain info
    """
    try:
        with get_db() as db:
            details = get_batch_details(db, batch_identifier, user_id)
        
        return {
            "success": True,
            **details
        }
        
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error in trace_batch: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# Serve mini app HTML
mini_app_router = APIRouter(prefix="/miniapps", tags=["miniapp-pages"])

@mini_app_router.get("/index")
async def serve_index():
    """Serve the main menu hub mini app."""
    html_path = Path(__file__).parent.parent.parent / "miniapps" / "index.html"
    if not html_path.exists():
        raise HTTPException(status_code=404, detail="Mini app not found")
    return FileResponse(html_path, media_type="text/html")

@mini_app_router.get("/batch_browser")
async def serve_batch_browser():
    """Serve the batch browser mini app HTML page."""
    html_path = Path(__file__).parent.parent.parent / "miniapps" / "batch_browser.html"
    if not html_path.exists():
        raise HTTPException(status_code=404, detail="Mini app not found")
    return FileResponse(html_path, media_type="text/html")

@mini_app_router.get("/batches")
async def serve_batches_alias():
    """Alias for batch_browser for backward compatibility."""
    return await serve_batch_browser()

@mini_app_router.get("/marketplace")
async def serve_marketplace():
    """Serve the marketplace mini app HTML page."""
    html_path = Path(__file__).parent.parent.parent / "miniapps" / "marketplace.html"
    if not html_path.exists():
        raise HTTPException(status_code=404, detail="Mini app not found")
    return FileResponse(html_path, media_type="text/html")

@mini_app_router.get("/trace")
async def serve_trace():
    """Serve the traceability mini app HTML page."""
    html_path = Path(__file__).parent.parent.parent / "miniapps" / "trace.html"
    if not html_path.exists():
        raise HTTPException(status_code=404, detail="Mini app not found")
    return FileResponse(html_path, media_type="text/html")

@mini_app_router.get("/admin")
async def serve_admin():
    """Serve the admin dashboard mini app HTML page."""
    html_path = Path(__file__).parent.parent.parent / "miniapps" / "admin.html"
    if not html_path.exists():
        raise HTTPException(status_code=404, detail="Mini app not found")
    return FileResponse(html_path, media_type="text/html")

@mini_app_router.get("/profile")
async def serve_profile():
    """Serve the user profile mini app HTML page."""
    html_path = Path(__file__).parent.parent.parent / "miniapps" / "profile.html"
    if not html_path.exists():
        raise HTTPException(status_code=404, detail="Mini app not found")
    return FileResponse(html_path, media_type="text/html")
