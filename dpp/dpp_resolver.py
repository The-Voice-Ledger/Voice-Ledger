"""
DPP Resolver API

FastAPI service that resolves Digital Product Passports by batch ID.
Public-facing API for consumers to access product traceability data.

Updated to query Neon PostgreSQL database instead of JSON files.
"""

import json
from pathlib import Path
from typing import Optional, Dict, Any

from fastapi import FastAPI, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from dpp.dpp_builder import build_dpp, validate_dpp, load_batch_data
from database import get_db, get_all_batches, get_batch_by_batch_id, get_batch_events


# Initialize FastAPI app
app = FastAPI(
    title="Voice Ledger DPP Resolver",
    description="Resolve Digital Product Passports for coffee batches",
    version="1.0.0"
)

# Enable CORS for public access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def health_check():
    """Health check endpoint"""
    return {
        "service": "Voice Ledger DPP Resolver",
        "status": "healthy",
        "version": "1.0.0"
    }


@app.get("/dpp/{batch_id}")
async def resolve_dpp(batch_id: str, format: str = "full") -> Dict[str, Any]:
    """
    Resolve Digital Product Passport by batch ID from database.
    
    Args:
        batch_id: Batch identifier (e.g., "BATCH-2025-001")
        format: Response format - "full", "summary", or "qr"
    
    Returns:
        DPP data in requested format
    
    Raises:
        HTTPException: If batch not found or DPP build fails
    """
    # Check if batch exists in database
    batch = load_batch_data(batch_id)
    if not batch:
        raise HTTPException(
            status_code=404,
            detail=f"Batch {batch_id} not found"
        )
    
    try:
        # Build DPP from database (all data from batch object)
        dpp = build_dpp(
            batch_id=batch_id,
            deforestation_risk="none",
            eudr_compliant=True
        )
        
        # Validate DPP
        is_valid, errors = validate_dpp(dpp)
        if not is_valid:
            raise HTTPException(
                status_code=500,
                detail=f"DPP validation failed: {', '.join(errors)}"
            )
        
        # Return requested format
        if format == "summary":
            return {
                "passportId": dpp["passportId"],
                "batchId": dpp["batchId"],
                "product": dpp["productInformation"]["productName"],
                "quantity": f"{dpp['productInformation']['quantity']} {dpp['productInformation']['unit']}",
                "origin": f"{dpp['traceability']['origin']['region']}, {dpp['traceability']['origin']['country']}",
                "farmer": dpp["traceability"]["origin"]["farmer"]["name"],
                "gtin": dpp["productInformation"]["gtin"],
                "eudrCompliant": dpp["dueDiligence"]["eudrCompliant"],
                "deforestationRisk": dpp["dueDiligence"]["riskAssessment"]["deforestationRisk"],
                "qrUrl": dpp["qrCode"]["url"]
            }
        
        elif format == "qr":
            return {
                "batchId": dpp["batchId"],
                "qrCode": dpp["qrCode"]
            }
        
        else:  # full format
            return dpp
    
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error building DPP: {str(e)}")


@app.get("/dpp/{batch_id}/verify")
async def verify_dpp(batch_id: str) -> Dict[str, Any]:
    """
    Verify DPP authenticity and blockchain anchoring from database.
    
    Args:
        batch_id: Batch identifier
    
    Returns:
        Verification results including blockchain status
    """
    with get_db() as db:
        batch = get_batch_by_batch_id(db, batch_id)
        if not batch:
            raise HTTPException(
                status_code=404,
                detail=f"Batch {batch_id} not found"
            )
        
        # Check blockchain anchors
        events = get_batch_events(db, batch_id)
        anchored_events = [e for e in events if e.blockchain_tx_hash]
        
        # Check credentials
        credentials = batch.farmer.credentials
        verified_credentials = [c for c in credentials if not c.revoked]
        
        # Determine verification status
        has_anchors = len(anchored_events) > 0
        has_credentials = len(verified_credentials) > 0
        
        verification_status = "verified" if (has_anchors and has_credentials) else "partial"
        
        return {
            "batchId": batch_id,
            "verificationStatus": verification_status,
            "blockchain": {
                "anchored": has_anchors,
                "anchoredEvents": len(anchored_events),
                "totalEvents": len(events)
            },
            "credentials": {
                "verified": has_credentials,
                "totalCredentials": len(verified_credentials),
                "types": [c.credential_type for c in verified_credentials]
            },
            "batch": {
                "gtin": batch.gtin,
                "quantity": f"{batch.quantity_kg} kg",
                "farmer": batch.farmer.name
            }
        }


@app.get("/batches")
async def list_batches() -> Dict[str, Any]:
    """
    List all available batches from database.
    
    Returns:
        List of batch IDs with summary information
    """
    with get_db() as db:
        batches = get_all_batches(db)
        
        batch_list = []
        for batch in batches:
            batch_list.append({
                "batchId": batch.batch_id,
                "gtin": batch.gtin,
                "quantity": batch.quantity_kg,
                "unit": "kg",
                "tokenId": batch.token_id,
                "farmer": batch.farmer.name,
                "origin": batch.origin_region,
                "events": len(batch.events),
                "credentials": len(batch.farmer.credentials)
            })
        
        return {
            "total": len(batch_list),
            "batches": batch_list
        }


# For testing/development
if __name__ == "__main__":
    import uvicorn
    
    print("🚀 Starting DPP Resolver API...")
    print("📍 Health check: http://localhost:8001/")
    print("🔍 Resolve DPP: http://localhost:8001/dpp/BATCH-2025-001")
    print("✅ Verify DPP: http://localhost:8001/dpp/BATCH-2025-001/verify")
    print("📋 List batches: http://localhost:8001/batches")
    print()
    
    uvicorn.run(app, host="0.0.0.0", port=8001)
