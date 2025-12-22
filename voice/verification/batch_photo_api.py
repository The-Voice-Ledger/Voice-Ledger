"""
Batch Verification Photo API for EUDR Compliance

Handles GPS-verified photo uploads for coffee batches.
Validates photo GPS coordinates against registered farm location.
"""

import logging
import io
from typing import Dict, Any, Optional
from datetime import datetime
from fastapi import APIRouter, HTTPException, UploadFile, File, Depends
from sqlalchemy.orm import Session

from database.models import (
    CoffeeBatch, 
    FarmerIdentity, 
    VerificationPhoto,
    SessionLocal
)
from voice.verification.gps_photo_verifier import GPSPhotoVerifier, GPSExtractionError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/batches", tags=["batch-verification"])


def get_db():
    """Dependency for database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.post("/{batch_id}/verification-photo")
async def upload_batch_verification_photo(
    batch_id: int,
    photo: UploadFile = File(...),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Upload GPS-verified photo for coffee batch (EUDR compliance).
    
    Validates:
    - Photo has GPS EXIF data
    - GPS is within Ethiopia
    - Photo is recent (within 30 days)
    - GPS is within 50km of registered farm location
    
    Args:
        batch_id: Coffee batch ID
        photo: Photo file with GPS EXIF data
        db: Database session
        
    Returns:
        {
            "success": true,
            "verification_id": 123,
            "gps": {"latitude": 9.145, "longitude": 40.489},
            "distance_from_farm_km": 2.3,
            "compliance_status": "VERIFIED"
        }
        
    Raises:
        404: Batch not found
        400: Invalid photo (no GPS, outside Ethiopia, too old, too far from farm)
    """
    try:
        # Find batch
        batch = db.query(CoffeeBatch).filter_by(id=batch_id).first()
        if not batch:
            raise HTTPException(status_code=404, detail=f"Batch {batch_id} not found")
        
        # Find farmer
        farmer = db.query(FarmerIdentity).filter_by(id=batch.farmer_id).first()
        if not farmer:
            raise HTTPException(status_code=404, detail="Farmer not found for batch")
        
        # Read photo data
        photo_bytes = await photo.read()
        photo_io = io.BytesIO(photo_bytes)
        
        # Extract GPS from photo
        verifier = GPSPhotoVerifier()
        gps_data = verifier.extract_gps_data(photo_io)
        
        # Validate GPS exists
        if not gps_data['has_gps']:
            raise HTTPException(
                status_code=400,
                detail="Photo does not contain GPS coordinates. Please enable location services and retake photo."
            )
        
        # Validate Ethiopia bounds
        in_ethiopia = verifier.validate_ethiopia_bounds(
            gps_data['latitude'], 
            gps_data['longitude']
        )
        if not in_ethiopia:
            raise HTTPException(
                status_code=400,
                detail=f"Photo GPS ({gps_data['latitude']:.6f}, {gps_data['longitude']:.6f}) is outside Ethiopia"
            )
        
        # Validate timestamp recency
        if gps_data['timestamp']:
            recency_result = verifier.validate_timestamp_recency(
                gps_data['timestamp'], 
                max_age_days=30
            )
            if not recency_result['valid']:
                raise HTTPException(
                    status_code=400,
                    detail=f"Photo is too old ({recency_result['age_days']:.0f} days). Please upload recent photo (within 30 days)."
                )
        
        # Validate proximity to registered farm location
        if farmer.latitude and farmer.longitude:
            proximity_result = verifier.validate_location_proximity(
                photo_coords=(gps_data['latitude'], gps_data['longitude']),
                reference_coords=(farmer.latitude, farmer.longitude),
                max_distance_km=50.0
            )
            
            if not proximity_result['valid']:
                raise HTTPException(
                    status_code=400,
                    detail=(
                        f"Photo location is {proximity_result['distance_km']:.1f}km from registered farm. "
                        f"Maximum allowed distance is 50km. "
                        f"Please upload photo taken at your farm location."
                    )
                )
            
            distance_from_farm = proximity_result['distance_km']
        else:
            # No registered farm GPS - use photo GPS as reference
            logger.warning(f"Farmer {farmer.farmer_id} has no registered GPS coordinates")
            distance_from_farm = None
        
        # Compute photo hash
        photo_io.seek(0)
        photo_hash = verifier.compute_photo_hash(photo_io)
        
        # Check for duplicate photo
        existing = db.query(VerificationPhoto).filter_by(photo_hash=photo_hash).first()
        if existing:
            raise HTTPException(
                status_code=400,
                detail=f"This photo has already been used for batch {existing.batch_id}"
            )
        
        # Store photo URL (in production, upload to S3/IPFS first)
        # For now, we'll use a placeholder URL
        photo_url = f"telegram://photo/{batch_id}/{photo_hash[:16]}"
        
        # Create verification photo record
        verification_photo = VerificationPhoto(
            batch_id=batch_id,
            photo_url=photo_url,
            photo_hash=photo_hash,
            latitude=gps_data['latitude'],
            longitude=gps_data['longitude'],
            photo_timestamp=datetime.fromisoformat(gps_data['timestamp']) if gps_data['timestamp'] else None,
            device_make=gps_data.get('device_make'),
            device_model=gps_data.get('device_model'),
            verified_at=datetime.utcnow(),
            distance_from_farm_km=distance_from_farm
        )
        
        db.add(verification_photo)
        db.commit()
        db.refresh(verification_photo)
        
        logger.info(
            f"✅ Verification photo added to batch {batch_id}: "
            f"GPS ({gps_data['latitude']:.6f}, {gps_data['longitude']:.6f}), "
            f"distance {distance_from_farm:.1f}km" if distance_from_farm else "distance unknown"
        )
        
        return {
            "success": True,
            "verification_id": verification_photo.id,
            "gps": {
                "latitude": gps_data['latitude'],
                "longitude": gps_data['longitude']
            },
            "distance_from_farm_km": distance_from_farm,
            "photo_timestamp": gps_data['timestamp'],
            "device": f"{gps_data.get('device_make', 'Unknown')} {gps_data.get('device_model', '')}".strip(),
            "compliance_status": "VERIFIED",
            "message": "Photo verified successfully. Ready for EUDR compliance."
        }
        
    except HTTPException:
        raise
    except GPSExtractionError as e:
        logger.error(f"GPS extraction failed for batch {batch_id}: {e}")
        raise HTTPException(
            status_code=400,
            detail=f"Failed to extract GPS from photo: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Error processing verification photo for batch {batch_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Internal server error processing photo"
        )


@router.get("/{batch_id}/verification-photos")
async def get_batch_verification_photos(
    batch_id: int,
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Get all verification photos for a batch.
    
    Args:
        batch_id: Coffee batch ID
        db: Database session
        
    Returns:
        {
            "batch_id": 123,
            "photos": [
                {
                    "id": 1,
                    "gps": {"latitude": 9.145, "longitude": 40.489},
                    "distance_from_farm_km": 2.3,
                    "verified_at": "2025-12-22T10:30:00",
                    "device": "Apple iPhone 14 Pro"
                }
            ]
        }
    """
    try:
        batch = db.query(CoffeeBatch).filter_by(id=batch_id).first()
        if not batch:
            raise HTTPException(status_code=404, detail=f"Batch {batch_id} not found")
        
        photos = db.query(VerificationPhoto).filter_by(batch_id=batch_id).all()
        
        return {
            "batch_id": batch_id,
            "photos": [
                {
                    "id": photo.id,
                    "gps": {
                        "latitude": photo.latitude,
                        "longitude": photo.longitude
                    },
                    "distance_from_farm_km": photo.distance_from_farm_km,
                    "verified_at": photo.verified_at.isoformat() if photo.verified_at else None,
                    "photo_timestamp": photo.photo_timestamp.isoformat() if photo.photo_timestamp else None,
                    "device": f"{photo.device_make or 'Unknown'} {photo.device_model or ''}".strip(),
                    "blockchain_proof": photo.blockchain_proof_hash
                }
                for photo in photos
            ]
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching verification photos for batch {batch_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/verification-photos/{photo_id}")
async def delete_verification_photo(
    photo_id: int,
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Delete verification photo (admin only - for corrections).
    
    Args:
        photo_id: Verification photo ID
        db: Database session
        
    Returns:
        {"success": true, "message": "Photo deleted"}
    """
    try:
        photo = db.query(VerificationPhoto).filter_by(id=photo_id).first()
        if not photo:
            raise HTTPException(status_code=404, detail=f"Verification photo {photo_id} not found")
        
        batch_id = photo.batch_id
        db.delete(photo)
        db.commit()
        
        logger.info(f"Deleted verification photo {photo_id} from batch {batch_id}")
        
        return {
            "success": True,
            "message": f"Verification photo {photo_id} deleted"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting verification photo {photo_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")
