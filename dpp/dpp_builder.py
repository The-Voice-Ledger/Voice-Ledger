"""
Digital Product Passport Builder

Translates database batch data into EUDR-compliant DPP format.
Combines on-chain and off-chain data into consumer-facing passport.

v2.0 Enhancement: Multi-batch DPP generation for aggregated containers.
Implements Aggregation Implementation Roadmap Section 1.1.
"""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Dict, Any, List
from database import get_db, get_batch_by_batch_id, get_batch_events
from database.models import CoffeeBatch, AggregationRelationship, EPCISEvent
from sqlalchemy.orm import Session


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


def build_aggregated_dpp(container_id: str) -> Dict[str, Any]:
    """
    Generate DPP for aggregated container with multiple source batches.
    
    Implements Roadmap Section 1.1.1: Multi-Batch DPP Generation
    
    Args:
        container_id: Parent container ID (SSCC or container identifier)
        
    Returns:
        DPP dict with contributors list, aggregation history, EUDR data
        
    Example:
        >>> dpp = build_aggregated_dpp("306141411234567892")
        >>> print(f"{dpp['productInformation']['numberOfContributors']} farmers")
        >>> for c in dpp['traceability']['contributors']:
        ...     print(f"{c['farmer']}: {c['contributionPercent']}")
    """
    with get_db() as db:
        # Step 1: Get aggregation relationships for this container
        # This is more reliable than parsing event JSON
        relationships = db.query(AggregationRelationship).filter(
            AggregationRelationship.parent_sscc == container_id,
            AggregationRelationship.is_active == True
        ).all()
        
        if not relationships:
            raise ValueError(f"No active batches found in container {container_id}")
        
        # Step 2: Get aggregation events for this container (for blockchain proofs)
        # Query by the relationship IDs to find events that created these relationships
        relationship_event_ids = [rel.aggregation_event_id for rel in relationships if rel.aggregation_event_id]
        
        container_events = []
        if relationship_event_ids:
            container_events = db.query(EPCISEvent).filter(
                EPCISEvent.id.in_(relationship_event_ids)
            ).all()
        
        # Step 3: Extract child batch IDs
        child_batch_ids = [rel.child_identifier for rel in relationships]
        
        # Step 4: Retrieve farmer data for each batch
        contributors = []
        total_quantity = 0
        
        for batch_id in child_batch_ids:
            batch = db.query(CoffeeBatch).filter(
                CoffeeBatch.batch_id == batch_id
            ).first()
            
            if not batch or not batch.farmer:
                continue
            
            # Load farmer credentials
            credentials = batch.farmer.credentials
            organic_certified = any(
                'organic' in c.credential_type.lower() and not c.revoked 
                for c in credentials
            )
            
            # Get commission event for IPFS CID
            commission_event = db.query(EPCISEvent).filter(
                EPCISEvent.batch_id == batch.id,
                EPCISEvent.event_type == 'ObjectEvent',
                EPCISEvent.biz_step == 'commissioning'
            ).first()
            
            contributor = {
                "farmer": batch.farmer.name,
                "did": batch.farmer.did,
                "contribution": batch.quantity_kg,
                "origin": {
                    "lat": batch.farmer.latitude,
                    "lon": batch.farmer.longitude,
                    "region": batch.origin_region,
                    "country": batch.origin_country
                },
                "organic": organic_certified,
                "batchId": batch_id,
                "ipfsCid": commission_event.ipfs_cid if commission_event else None
            }
            contributors.append(contributor)
            total_quantity += batch.quantity_kg
        
        # Step 5: Calculate contribution percentages
        for contributor in contributors:
            percentage = (contributor['contribution'] / total_quantity) * 100
            contributor['contributionPercent'] = f"{percentage:.1f}%"
        
        # Step 6: Retrieve aggregation event blockchain anchors
        blockchain_proofs = []
        for event in container_events:
            blockchain_proofs.append({
                "eventType": "AggregationEvent",
                "eventHash": event.event_hash,
                "ipfsCid": event.ipfs_cid,
                "blockchainTx": event.blockchain_tx_hash,
                "timestamp": event.event_time.isoformat() if event.event_time else None
            })
        
        # Step 7: Build aggregated DPP
        issued_at = datetime.now(timezone.utc).isoformat()
        passport_id = f"DPP-AGGREGATED-{container_id}"
        
        dpp = {
            "passportId": passport_id,
            "containerId": container_id,
            "version": "2.0.0",
            "issuedAt": issued_at,
            "type": "AggregatedProductPassport",
            "productInformation": {
                "productName": "Multi-Origin Coffee Blend",
                "containerID": container_id,
                "totalQuantity": f"{total_quantity} kg",
                "numberOfContributors": len(contributors),
                "unit": "kg"
            },
            "traceability": {
                "contributors": contributors,
                "aggregationEvents": blockchain_proofs
            },
            "dueDiligence": {
                "eudrCompliant": all(
                    c['origin'].get('lat') and c['origin'].get('lon') 
                    for c in contributors
                ),
                "allFarmersGeolocated": all(
                    c['origin'].get('lat') and c['origin'].get('lon') 
                    for c in contributors
                ),
                "riskAssessment": {
                    "deforestationRisk": "none",
                    "assessmentDate": datetime.now(timezone.utc).date().isoformat(),
                    "assessor": "Voice Ledger Platform v2.0",
                    "methodology": "Multi-farmer aggregation + blockchain traceability"
                }
            },
            "blockchain": {
                "network": "Base Sepolia",
                "aggregationProofs": blockchain_proofs,
                "anchors": blockchain_proofs
            },
            "qrCode": {
                "url": f"https://dpp.voiceledger.io/container/{container_id}"
            }
        }
        
        return dpp


def build_recursive_dpp(product_id: str, max_depth: int = 5) -> Dict[str, Any]:
    """
    Generate DPP by recursively traversing aggregation hierarchy.
    
    Implements Roadmap Section 1.1.2: Recursive DPP Generation
    
    Handles: Retail Bag → Roasted Lot → Import Container → Export Container → Farmer Batches
    
    Args:
        product_id: Product/container identifier to start from
        max_depth: Maximum recursion depth (default 5 levels)
        
    Returns:
        DPP with complete farmer lineage from all aggregation levels
        
    Example:
        >>> # Retail bag that contains coffee from 3 cooperatives, 100 farmers
        >>> dpp = build_recursive_dpp("RETAIL-BAG-001")
        >>> print(f"{len(dpp['traceability']['contributors'])} farmers total")
    """
    def traverse_hierarchy(node_id: str, depth: int = 0) -> List[Dict]:
        """Recursively find all farmer batches in aggregation tree."""
        if depth > max_depth:
            return []
        
        with get_db() as db:
            # Check if node has children (is aggregated)
            children = db.query(AggregationRelationship).filter(
                AggregationRelationship.parent_sscc == node_id,
                AggregationRelationship.is_active == True
            ).all()
            
            if not children:
                # Leaf node (farmer batch) - get batch data
                batch = db.query(CoffeeBatch).filter(
                    CoffeeBatch.batch_id == node_id
                ).first()
                
                if batch and batch.farmer:
                    return [{
                        "batch_id": batch.batch_id,
                        "farmer_name": batch.farmer.name,
                        "farmer_did": batch.farmer.did,
                        "quantity_kg": batch.quantity_kg,
                        "lat": batch.farmer.latitude,
                        "lon": batch.farmer.longitude,
                        "region": batch.origin_region,
                        "country": batch.origin_country
                    }]
                return []
            
            # Internal node (aggregation) - traverse children
            all_batches = []
            for child in children:
                all_batches.extend(
                    traverse_hierarchy(child.child_identifier, depth + 1)
                )
            
            return all_batches
    
    # Start traversal from product_id
    farmer_batches = traverse_hierarchy(product_id)
    
    if not farmer_batches:
        raise ValueError(f"No farmer batches found for product {product_id}")
    
    # Calculate totals and percentages
    total_quantity = sum(b['quantity_kg'] for b in farmer_batches)
    
    contributors = []
    for batch in farmer_batches:
        percentage = (batch['quantity_kg'] / total_quantity) * 100
        contributors.append({
            "farmer": batch['farmer_name'],
            "did": batch['farmer_did'],
            "contribution": batch['quantity_kg'],
            "contributionPercent": f"{percentage:.1f}%",
            "origin": {
                "lat": batch['lat'],
                "lon": batch['lon'],
                "region": batch['region'],
                "country": batch['country']
            },
            "batchId": batch['batch_id']
        })
    
    # Build DPP
    issued_at = datetime.now(timezone.utc).isoformat()
    passport_id = f"DPP-RECURSIVE-{product_id}"
    
    dpp = {
        "passportId": passport_id,
        "productId": product_id,
        "version": "2.0.0",
        "issuedAt": issued_at,
        "type": "RecursiveAggregatedPassport",
        "productInformation": {
            "productName": "Multi-Level Aggregated Coffee Product",
            "productID": product_id,
            "totalQuantity": f"{total_quantity} kg",
            "numberOfContributors": len(contributors),
            "aggregationLevels": "Recursively traced through supply chain"
        },
        "traceability": {
            "contributors": contributors,
            "traceMethod": f"Recursive traversal (max depth: {max_depth})"
        },
        "dueDiligence": {
            "eudrCompliant": True,
            "allFarmersGeolocated": all(
                c['origin'].get('lat') and c['origin'].get('lon')
                for c in contributors
            ),
            "riskAssessment": {
                "deforestationRisk": "none",
                "assessmentDate": datetime.now(timezone.utc).date().isoformat()
            }
        },
        "qrCode": {
            "url": f"https://dpp.voiceledger.io/product/{product_id}"
        }
    }
    
    return dpp


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


def build_split_batch_dpp(batch_id: str) -> Dict[str, Any]:
    """
    Build DPP for a batch created from split/transformation.
    
    Includes metadata linking back to parent batch and transformation event.
    Each split batch inherits farmer data from parent for EUDR compliance.
    
    Args:
        batch_id: Child batch ID from transformation
    
    Returns:
        DPP with split metadata and inherited farmer data
    
    Example:
        Parent BATCH-001 (10,000kg) split into:
        - BATCH-001-A (6,000kg) → DPP shows 60% of parent farmers
        - BATCH-001-B (4,000kg) → DPP shows 40% of parent farmers
    """
    with get_db() as db:
        # Get child batch
        batch = db.query(CoffeeBatch).filter(
            CoffeeBatch.batch_id == batch_id
        ).first()
        
        if not batch:
            raise ValueError(f"Batch {batch_id} not found")
        
        # Find TransformationEvent that created this batch
        # Query all transformation events and filter in Python (PostgreSQL JSON querying is complex)
        transformation_event = None
        for event in db.query(EPCISEvent).filter(EPCISEvent.event_type == "TransformationEvent").all():
            output_list = event.event_json.get('outputEPCList', [])
            # Check if any output SGTIN contains our batch_id
            if any(batch_id in sgtin for sgtin in output_list):
                transformation_event = event
                break
        
        parent_batch_id = None
        transformation_id = None
        
        if transformation_event:
            parent_batch_id = transformation_event.event_json.get("ilmd", {}).get("parentBatch")
            transformation_id = transformation_event.event_json.get("transformationID")
        
        # Build standard DPP
        dpp = build_dpp(batch_id)
        
        # Add split metadata
        dpp["splitMetadata"] = {
            "isSplitBatch": True,
            "parentBatchId": parent_batch_id,
            "transformationId": transformation_id,
            "splitRatio": f"{batch.quantity_kg}kg from parent batch",
            "note": "This batch was created by splitting a larger parent batch. Farmer data inherited from parent."
        }
        
        # Add parent batch link
        if parent_batch_id:
            dpp["parentage"] = {
                "parentBatch": parent_batch_id,
                "relationship": "split_from",
                "inheritedFields": ["farmer", "origin", "harvest_date", "processing_method"]
            }
        
        return dpp
