"""
Digital Product Passport Builder

Translates digital twin data into EUDR-compliant DPP format.
Combines on-chain and off-chain data into consumer-facing passport.
"""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Dict, Any, List


def load_twin_data(batch_id: str) -> Optional[Dict[str, Any]]:
    """
    Load digital twin data for a batch.
    
    Args:
        batch_id: Batch identifier (e.g., "BATCH-2025-001")
    
    Returns:
        Digital twin data or None if batch not found
    """
    twin_file = Path(__file__).parent.parent / "twin" / "digital_twin.json"
    
    if not twin_file.exists():
        return None
    
    with open(twin_file, "r") as f:
        twin_data = json.load(f)
    
    return twin_data.get("batches", {}).get(batch_id)


def build_dpp(
    batch_id: str,
    product_name: str = "Arabica Coffee - Washed",
    variety: str = "Arabica",
    process_method: str = "Washed",
    country: str = "ET",
    region: str = "Yirgacheffe",
    cooperative: str = "Guzo Farmers Cooperative",
    deforestation_risk: str = "none",
    eudr_compliant: bool = True,
    resolver_base_url: str = "https://dpp.voiceledger.io"
) -> Dict[str, Any]:
    """
    Build a Digital Product Passport from digital twin data.
    
    Args:
        batch_id: Batch identifier
        product_name: Product name
        variety: Coffee variety
        process_method: Processing method
        country: ISO 3166-1 alpha-2 country code
        region: Region/province
        cooperative: Cooperative name
        deforestation_risk: Risk level (none/low/medium/high)
        eudr_compliant: EUDR compliance status
        resolver_base_url: Base URL for DPP resolver
    
    Returns:
        Complete DPP dictionary
    """
    twin = load_twin_data(batch_id)
    
    if not twin:
        raise ValueError(f"Batch {batch_id} not found in digital twin")
    
    # Generate passport ID
    passport_id = f"DPP-{batch_id}"
    issued_at = datetime.now(timezone.utc).isoformat()
    
    # Build product information
    product_info = {
        "productName": product_name,
        "quantity": twin.get("quantity", 0),
        "unit": "bags",
        "variety": variety,
        "processMethod": process_method
    }
    
    # Add GTIN if available
    if "gtin" in twin.get("metadata", {}):
        product_info["gtin"] = twin["metadata"]["gtin"]
    
    # Build traceability section
    traceability = {
        "origin": {
            "country": country,
            "region": region,
            "cooperative": cooperative
        },
        "supplyChainActors": [],
        "events": []
    }
    
    # Add geolocation if available
    metadata = twin.get("metadata", {})
    if "geolocation" in metadata:
        traceability["origin"]["geolocation"] = metadata["geolocation"]
    
    # Extract supply chain actors from credentials
    for cred in twin.get("credentials", []):
        cred_subject = cred.get("credentialSubject", {})
        actor = {
            "role": cred_subject.get("role", "unknown"),
            "name": cred_subject.get("name", "Unknown"),
            "did": cred.get("issuer", "")
        }
        
        if "gln" in cred_subject:
            actor["gln"] = cred_subject["gln"]
        
        actor["credential"] = {
            "id": cred.get("id"),
            "type": cred.get("type", [])
        }
        
        traceability["supplyChainActors"].append(actor)
    
    # Extract EPCIS events from anchors
    for anchor in twin.get("anchors", []):
        event = {
            "eventType": anchor.get("eventType", "unknown"),
            "timestamp": anchor.get("timestamp") or issued_at,
            "eventHash": anchor.get("eventHash", "")
        }
        
        if "location" in anchor:
            event["location"] = anchor["location"]
        
        if "description" in anchor:
            event["description"] = anchor["description"]
        
        traceability["events"].append(event)
    
    # Build sustainability section
    sustainability = {}
    
    # Add certifications if available
    if "certifications" in metadata:
        sustainability["certifications"] = metadata["certifications"]
    
    # Add carbon footprint if available
    if "carbonFootprint" in metadata:
        sustainability["carbonFootprint"] = metadata["carbonFootprint"]
    
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
    
    # Add land use rights if available
    if "landUseRights" in metadata:
        due_diligence["landUseRights"] = metadata["landUseRights"]
    
    # Add due diligence credential reference if available
    dd_creds = [c for c in twin.get("credentials", []) if "DueDiligence" in c.get("type", [])]
    if dd_creds:
        due_diligence["dueDiligenceStatement"] = dd_creds[0].get("id", "")
    
    # Build blockchain section
    blockchain = {
        "network": "local",  # Would be "ethereum", "polygon", etc. in production
        "eventAnchorContract": "0x0000000000000000000000000000000000000000",  # Placeholder
        "anchors": []
    }
    
    # Add token information if available
    if "tokenId" in twin:
        blockchain["tokenContract"] = "0x0000000000000000000000000000000000000000"
        blockchain["tokenId"] = twin["tokenId"]
    
    # Add settlement contract if settled
    if twin.get("settlement", {}).get("settled"):
        blockchain["settlementContract"] = "0x0000000000000000000000000000000000000000"
    
    # Format anchors for blockchain section
    for anchor in twin.get("anchors", []):
        blockchain_anchor = {
            "eventHash": anchor.get("eventHash", "")
        }
        
        if "txHash" in anchor and anchor["txHash"]:
            blockchain_anchor["transactionHash"] = anchor["txHash"]
        
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
