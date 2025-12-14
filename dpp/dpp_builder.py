"""
Digital Product Passport Builder

Translates database batch data into EUDR-compliant DPP format.
Combines on-chain and off-chain data into consumer-facing passport.
"""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Dict, Any, List
from database import get_db, get_batch_by_batch_id, get_batch_events


def load_batch_data(batch_id: str):
    """
    Load batch data from Neon database with eager-loaded relationships.
    
    Args:
        batch_id: Batch identifier (e.g., "BATCH-2025-001")
    
    Returns:
        CoffeeBatch object with relationships loaded, detached from session
    """
    with get_db() as db:
        batch = get_batch_by_batch_id(db, batch_id)
        if not batch:
            return None
        
        # Force load all relationships before expunging from session
        _  = batch.farmer.name  # Load farmer
        _ = batch.farmer.did
        _ = len(batch.farmer.credentials)  # Load credentials collection
        _ = [c.credential_type for c in batch.farmer.credentials]  # Load each credential
        _ = len(batch.events)  # Load events collection
        _ = [e.event_type for e in batch.events]  # Load each event
        
        # Expunge all related objects from session so they can be used outside
        db.expunge_all()
        
        return batch


def build_dpp(
    batch_id: str,
    product_name: Optional[str] = None,
    variety: Optional[str] = None,
    process_method: Optional[str] = None,
    country: Optional[str] = None,
    region: Optional[str] = None,
    cooperative: Optional[str] = None,
    deforestation_risk: str = "none",
    eudr_compliant: bool = True,
    resolver_base_url: str = "https://dpp.voiceledger.io"
) -> Dict[str, Any]:
    """
    Build a Digital Product Passport from database batch data.
    
    Args:
        batch_id: Batch identifier
        product_name: Product name (optional, defaults to batch data)
        variety: Coffee variety (optional, defaults to batch data)
        process_method: Processing method (optional, defaults to batch data)
        country: ISO 3166-1 alpha-2 country code (optional, defaults to batch data)
        region: Region/province (optional, defaults to batch data)
        cooperative: Cooperative name (optional, defaults to batch data)
        deforestation_risk: Risk level (none/low/medium/high)
        eudr_compliant: EUDR compliance status
        resolver_base_url: Base URL for DPP resolver
    
    Returns:
        Complete DPP dictionary
    """
    batch = load_batch_data(batch_id)
    
    if not batch:
        raise ValueError(f"Batch {batch_id} not found in database")
    
    # Generate passport ID
    passport_id = f"DPP-{batch_id}"
    issued_at = datetime.now(timezone.utc).isoformat()
    
    # Build product information from database
    product_info = {
        "productName": product_name or f"{batch.origin_region} {batch.variety} - {batch.process_method}",
        "quantity": batch.quantity_kg,
        "unit": "kg",
        "variety": variety or batch.variety,
        "processMethod": process_method or batch.process_method,
        "gtin": batch.gtin
    }
    
    # Build traceability section from database
    traceability = {
        "origin": {
            "country": country or batch.origin_country,
            "region": region or batch.origin_region,
            "farmName": batch.farm_name,
            "farmer": {
                "name": batch.farmer.name,
                "did": batch.farmer.did,
                "gln": batch.farmer.gln
            }
        },
        "supplyChainActors": [],
        "events": []
    }
    
    # Extract supply chain actors from farmer's credentials
    for cred in batch.farmer.credentials:
        if not cred.revoked:
            actor = {
                "role": cred.credential_type.replace("Certification", "").lower(),
                "name": batch.farmer.name,
                "did": cred.subject_did,
                "credential": {
                    "id": cred.credential_id,
                    "type": cred.credential_type,
                    "issuer": cred.issuer_did,
                    "issuedDate": cred.issuance_date.isoformat()
                }
            }
            traceability["supplyChainActors"].append(actor)
    
    # Extract EPCIS events from database
    for db_event in batch.events:
        event = {
            "eventType": db_event.event_type,
            "timestamp": db_event.event_time.isoformat() if db_event.event_time else issued_at,
            "eventHash": db_event.event_hash,
            "bizStep": db_event.biz_step,
            "blockchainAnchor": {
                "transactionHash": db_event.blockchain_tx_hash or "pending",
                "anchoredAt": db_event.blockchain_confirmed_at.isoformat() if db_event.blockchain_confirmed_at else None
            }
        }
        traceability["events"].append(event)
    
    # Build sustainability section from credentials
    sustainability = {
        "certifications": []
    }
    
    # Add certifications from farmer's credentials
    for cred in batch.farmer.credentials:
        if not cred.revoked and "certification" in cred.credential_type.lower():
            cert = {
                "type": cred.credential_type,
                "issuer": cred.issuer_did,
                "issuedDate": cred.issuance_date.isoformat(),
                "expiryDate": cred.expiration_date.isoformat() if cred.expiration_date else None
            }
            sustainability["certifications"].append(cert)
    
    # Placeholder for carbon footprint (would come from batch metadata)
    sustainability["carbonFootprint"] = {
        "value": 0.85,
        "unit": "kg CO2e/kg",
        "scope": "cradle-to-gate"
    }
    
    # Build due diligence section
    due_diligence = {
        "eudrCompliant": eudr_compliant,
        "riskAssessment": {
            "deforestationRisk": deforestation_risk,
            "assessmentDate": datetime.now(timezone.utc).date().isoformat(),
            "assessor": "Voice Ledger Platform",
            "methodology": "Satellite imagery + blockchain traceability"
        }
    }
    
    # Add due diligence credential reference if available
    dd_creds = [c for c in batch.farmer.credentials if "duediligence" in c.credential_type.lower()]
    if dd_creds:
        due_diligence["dueDiligenceStatement"] = dd_creds[0].credential_id
    
    # Build blockchain section from database events
    blockchain = {
        "network": "local",  # Would be "ethereum", "polygon", etc. in production
        "eventAnchorContract": "0x0000000000000000000000000000000000000000",  # Placeholder
        "anchors": []
    }
    
    # Add token information if available
    if batch.token_id:
        blockchain["tokenContract"] = "0x0000000000000000000000000000000000000000"
        blockchain["tokenId"] = batch.token_id
    
    # Format anchors from database events
    for event in batch.events:
        blockchain_anchor = {
            "eventHash": event.event_hash
        }
        
        if event.blockchain_tx_hash:
            blockchain_anchor["transactionHash"] = event.blockchain_tx_hash
            blockchain_anchor["anchoredAt"] = event.created_at.isoformat() if event.created_at else None
        
        blockchain["anchors"].append(blockchain_anchor)
    
    # Build QR code section
    dpp_url = f"{resolver_base_url}/dpp/{batch_id}"
    qr_code = {
        "url": dpp_url
    }
    
    # Assemble complete DPP
    dpp = {
        "passportId": passport_id,
        "batchId": batch_id,
        "version": "1.0.0",
        "issuedAt": issued_at,
        "productInformation": product_info,
        "traceability": traceability,
        "sustainability": sustainability,
        "dueDiligence": due_diligence,
        "blockchain": blockchain,
        "qrCode": qr_code
    }
    
    return dpp


def save_dpp(dpp: Dict[str, Any], output_dir: Optional[Path] = None) -> Path:
    """
    Save DPP to JSON file.
    
    Args:
        dpp: DPP dictionary
        output_dir: Output directory (defaults to dpp/passports/)
    
    Returns:
        Path to saved DPP file
    """
    if output_dir is None:
        output_dir = Path(__file__).parent / "passports"
    
    output_dir.mkdir(parents=True, exist_ok=True)
    
    batch_id = dpp["batchId"]
    output_file = output_dir / f"{batch_id}_dpp.json"
    
    with open(output_file, "w") as f:
        json.dump(dpp, f, indent=2, ensure_ascii=False)
    
    return output_file


def validate_dpp(dpp: Dict[str, Any]) -> tuple[bool, List[str]]:
    """
    Validate DPP against required fields.
    
    Args:
        dpp: DPP dictionary
    
    Returns:
        Tuple of (is_valid, list of errors)
    """
    errors = []
    
    # Check required top-level fields
    required_fields = [
        "passportId", "batchId", "version", "productInformation",
        "traceability", "dueDiligence", "blockchain"
    ]
    
    for field in required_fields:
        if field not in dpp:
            errors.append(f"Missing required field: {field}")
    
    # Check EUDR compliance fields
    if "dueDiligence" in dpp:
        dd = dpp["dueDiligence"]
        if "eudrCompliant" not in dd:
            errors.append("Missing dueDiligence.eudrCompliant")
        if "riskAssessment" not in dd:
            errors.append("Missing dueDiligence.riskAssessment")
        elif "deforestationRisk" not in dd["riskAssessment"]:
            errors.append("Missing dueDiligence.riskAssessment.deforestationRisk")
    
    # Check traceability origin
    if "traceability" in dpp:
        trace = dpp["traceability"]
        if "origin" not in trace:
            errors.append("Missing traceability.origin")
        elif "country" not in trace["origin"]:
            errors.append("Missing traceability.origin.country")
    
    return len(errors) == 0, errors


# Demo/test code
if __name__ == "__main__":
    print("🏗️  Building Digital Product Passport...")
    print()
    
    # Build DPP from digital twin
    try:
        dpp = build_dpp(
            batch_id="BATCH-2025-001",
            product_name="Ethiopian Yirgacheffe - Washed Arabica",
            variety="Arabica",
            process_method="Washed",
            country="ET",
            region="Yirgacheffe, Gedeo Zone",
            cooperative="Guzo Farmers Cooperative",
            deforestation_risk="none",
            eudr_compliant=True
        )
        
        print(f"✅ Built DPP: {dpp['passportId']}")
        print(f"   Batch: {dpp['batchId']}")
        print(f"   Product: {dpp['productInformation']['productName']}")
        print(f"   Quantity: {dpp['productInformation']['quantity']} {dpp['productInformation']['unit']}")
        print(f"   Origin: {dpp['traceability']['origin']['region']}, {dpp['traceability']['origin']['country']}")
        print(f"   EUDR Compliant: {dpp['dueDiligence']['eudrCompliant']}")
        print(f"   Deforestation Risk: {dpp['dueDiligence']['riskAssessment']['deforestationRisk']}")
        print(f"   Events: {len(dpp['traceability']['events'])} EPCIS events")
        print(f"   Actors: {len(dpp['traceability']['supplyChainActors'])} supply chain actors")
        print(f"   Blockchain Anchors: {len(dpp['blockchain']['anchors'])} on-chain anchors")
        print()
        
        # Validate DPP
        is_valid, validation_errors = validate_dpp(dpp)
        if is_valid:
            print("✅ DPP validation passed")
        else:
            print("❌ DPP validation failed:")
            for error in validation_errors:
                print(f"   - {error}")
        print()
        
        # Save DPP
        output_file = save_dpp(dpp)
        print(f"💾 Saved DPP to: {output_file}")
        print()
        
        # Display DPP snippet
        print("📄 DPP Preview:")
        print(json.dumps({
            "passportId": dpp["passportId"],
            "batchId": dpp["batchId"],
            "productInformation": dpp["productInformation"],
            "dueDiligence": {
                "eudrCompliant": dpp["dueDiligence"]["eudrCompliant"],
                "riskAssessment": {
                    "deforestationRisk": dpp["dueDiligence"]["riskAssessment"]["deforestationRisk"]
                }
            },
            "qrCode": dpp["qrCode"]
        }, indent=2))
        
    except ValueError as e:
        print(f"❌ Error: {e}")
