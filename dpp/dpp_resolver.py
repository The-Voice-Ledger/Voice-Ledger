"""
DPP Resolver API

FastAPI service that resolves Digital Product Passports by batch ID.
Public-facing API for consumers to access product traceability data.
"""

import json
from pathlib import Path
from typing import Optional, Dict, Any

from fastapi import FastAPI, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from dpp.dpp_builder import build_dpp, validate_dpp, load_twin_data


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
    Resolve Digital Product Passport by batch ID.
    
    Args:
        batch_id: Batch identifier (e.g., "BATCH-2025-001")
        format: Response format - "full", "summary", or "qr"
    
    Returns:
        DPP data in requested format
    
    Raises:
        HTTPException: If batch not found or DPP build fails
    """
    # Check if batch exists in digital twin
    twin = load_twin_data(batch_id)
    if not twin:
        raise HTTPException(
            status_code=404,
            detail=f"Batch {batch_id} not found"
        )
    
    try:
        # Build DPP from digital twin
        # In production, these values would come from database
        dpp = build_dpp(
            batch_id=batch_id,
            product_name="Ethiopian Yirgacheffe - Washed Arabica",
            variety="Arabica",
            process_method="Washed",
            country="ET",
            region="Yirgacheffe, Gedeo Zone",
            cooperative=twin.get("metadata", {}).get("cooperative", "Unknown Cooperative"),
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
    Verify DPP authenticity and blockchain anchoring.
    
    Args:
        batch_id: Batch identifier
    
    Returns:
        Verification results including blockchain status
    """
    twin = load_twin_data(batch_id)
    if not twin:
        raise HTTPException(
            status_code=404,
            detail=f"Batch {batch_id} not found"
        )
    
    # Check blockchain anchors
    anchors = twin.get("anchors", [])
    anchored_events = len([a for a in anchors if a.get("eventHash")])
    
    # Check credentials
    credentials = twin.get("credentials", [])
    
    # Check settlement status
    settlement = twin.get("settlement", {})
    is_settled = settlement.get("settled", False)
    
    # Determine verification status
    has_anchors = anchored_events > 0
    has_credentials = len(credentials) > 0
    
    verification_status = "verified" if (has_anchors and has_credentials) else "partial"
    
    return {
        "batchId": batch_id,
        "verificationStatus": verification_status,
        "blockchain": {
            "anchored": has_anchors,
            "anchoredEvents": anchored_events,
            "totalAnchors": len(anchors)
        },
        "credentials": {
            "verified": has_credentials,
            "totalCredentials": len(credentials),
            "types": [c.get("type", []) for c in credentials]
        },
        "settlement": {
            "recorded": is_settled,
            "amount": settlement.get("amount"),
            "recipient": settlement.get("recipient")
        },
        "timestamp": twin.get("metadata", {}).get("lastUpdated")
    }


@app.get("/batches")
async def list_batches() -> Dict[str, Any]:
    """
    List all available batches.
    
    Returns:
        List of batch IDs with summary information
    """
    twin_file = Path(__file__).parent.parent / "twin" / "digital_twin.json"
    
    if not twin_file.exists():
        return {"batches": []}
    
    with open(twin_file, "r") as f:
        twin_data = json.load(f)
    
    batches = []
    for batch_id, data in twin_data.get("batches", {}).items():
        batches.append({
            "batchId": batch_id,
            "quantity": data.get("quantity"),
            "tokenId": data.get("tokenId"),
            "anchors": len(data.get("anchors", [])),
            "credentials": len(data.get("credentials", [])),
            "settled": data.get("settlement", {}).get("settled", False)
        })
    
    return {
        "total": len(batches),
        "batches": batches
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
