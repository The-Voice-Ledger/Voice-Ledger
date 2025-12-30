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
from database.models import CoffeeBatch, EPCISEvent, UserIdentity
from sqlalchemy.orm import joinedload

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/miniapp", tags=["miniapp"])


def get_user_batches(db, user_id: int) -> List[Dict[str, Any]]:
    """
    Get all coffee batches for a user's cooperative.
    
    Args:
        db: Database session
        user_id: Telegram user ID
        
    Returns:
        List of batch dictionaries
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
        
        # Convert to dictionaries
        batch_list = []
        for batch in batches:
            batch_dict = {
                'batch_id': batch.batch_id,
                'gtin': batch.gtin,
                'weight_kg': float(batch.weight_kg) if batch.weight_kg else 0,
                'coffee_type': batch.coffee_type or 'Arabica Coffee',
                'status': 'active',  # Default status
                'created_at': batch.created_at.isoformat() if batch.created_at else None,
                'blockchain_hash': batch.ipfs_hash  # Using IPFS hash as blockchain reference
            }
            
            # Determine status from verification
            if batch.verified_at:
                batch_dict['status'] = 'verified'
            # Check if shipped (has shipping events)
            shipping_events = db.query(EPCISEvent).filter(
                EPCISEvent.gtin == batch.gtin,
                EPCISEvent.biz_step == 'shipping'
            ).first()
            if shipping_events:
                batch_dict['status'] = 'shipped'
            
            batch_list.append(batch_dict)
        
        return batch_list
        
    except Exception as e:
        logger.error(f"Error getting user batches: {e}", exc_info=True)
        return []


def get_batch_details(db, batch_identifier: str, user_id: int) -> Dict[str, Any]:
    """
    Get detailed information for a specific batch.
    
    Args:
        db: Database session
        batch_identifier: GTIN or batch_id
        user_id: Telegram user ID (for authorization)
        
    Returns:
        Dictionary with batch details and EPCIS events
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
            EPCISEvent.gtin == batch.gtin
        ).order_by(EPCISEvent.event_time.asc()).all()
        
        # Build response
        result = {
            'batch': {
                'batch_id': batch.batch_id,
                'gtin': batch.gtin,
                'weight_kg': float(batch.weight_kg) if batch.weight_kg else 0,
                'coffee_type': batch.coffee_type or 'Arabica Coffee',
                'status': 'active',
                'created_at': batch.created_at.isoformat() if batch.created_at else None,
                'verified_at': batch.verified_at.isoformat() if batch.verified_at else None,
                'blockchain_hash': batch.ipfs_hash,
                'farmer_gln': batch.farmer_gln,
                'origin_location': batch.origin_location
            },
            'events': []
        }
        
        # Add events
        for event in events:
            result['events'].append({
                'biz_step': event.biz_step,
                'event_time': event.event_time.isoformat() if event.event_time else None,
                'location': event.biz_location,
                'event_id': event.event_id
            })
        
        # Determine status
        if batch.verified_at:
            result['batch']['status'] = 'verified'
        elif len(result['events']) > 1:
            result['batch']['status'] = 'shipped'
        
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
        db = next(get_db())
        batches = get_user_batches(db, user_id)
        db.close()
        
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
        db = next(get_db())
        details = get_batch_details(db, batch_identifier, user_id)
        db.close()
        
        return {
            "success": True,
            **details
        }
        
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error in get_batch: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# Serve mini app HTML
mini_app_router = APIRouter(prefix="/miniapps", tags=["miniapp-pages"])

@mini_app_router.get("/batches")
async def serve_batch_browser():
    """Serve the batch browser mini app HTML page."""
    html_path = Path(__file__).parent.parent.parent / "miniapps" / "batch_browser.html"
    
    if not html_path.exists():
        raise HTTPException(status_code=404, detail="Mini app not found")
    
    return FileResponse(html_path, media_type="text/html")
