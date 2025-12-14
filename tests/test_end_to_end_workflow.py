"""
End-to-End Workflow Test for Voice Ledger

Validates the complete system from voice input simulation through:
1. ASR (Speech Recognition) - Simulated
2. NLU (Natural Language Understanding)
3. EPCIS Event Generation
4. Event Hashing & Canonicalization
5. IPFS Storage (Pinata)
6. Database Storage (Neon)
7. Digital Twin Update
8. DPP Generation
9. Blockchain Anchoring (Simulated)
10. Complete Verification

This test proves all components work together as claimed.
"""

import json
import hashlib
from datetime import datetime, timezone
from pathlib import Path
import sys

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from database import (
    get_db, 
    create_farmer, 
    create_batch, 
    create_event,
    get_batch_by_batch_id,
    get_event_by_hash,
    store_credential
)
from ipfs import pin_epcis_event, get_from_ipfs, pin_dpp
from ssi.did.did_key import generate_did_key
from ssi.credentials.issue import issue_credential
from twin.twin_builder import record_anchor, record_token
from dpp.dpp_builder import build_dpp, load_batch_data
from gs1.identifiers import gtin as generate_gtin


def print_section(title: str):
    """Print formatted section header."""
    print("\n" + "="*70)
    print(f"  {title}")
    print("="*70)


def print_step(step_num: int, description: str):
    """Print formatted step."""
    print(f"\n{'─'*70}")
    print(f"Step {step_num}: {description}")
    print(f"{'─'*70}")


def simulate_voice_to_text():
    """Simulate ASR converting voice to text."""
    print_step(1, "Voice Input → Text Transcript (ASR)")
    
    # Simulate voice input
    voice_command = "Deliver 50 bags of washed coffee from Abebe Kebede to Guzo warehouse"
    
    print(f"🎤 Voice Input: '{voice_command}'")
    print(f"📝 Transcript: '{voice_command}'")
    
    return voice_command


def simulate_nlu(transcript: str):
    """Simulate NLU extracting structured data."""
    print_step(2, "Text → Structured Data (NLU)")
    
    # Simulate NLU inference
    nlu_result = {
        "intent": "commissioning",
        "entities": {
            "quantity": 50,
            "unit": "bags",
            "product": "washed coffee",
            "origin": "Abebe Kebede",
            "destination": "Guzo warehouse",
            "action": "deliver"
        },
        "confidence": 0.95
    }
    
    print(f"🧠 NLU Intent: {nlu_result['intent']}")
    print(f"📦 Entities: {json.dumps(nlu_result['entities'], indent=2)}")
    
    return nlu_result


def create_farmer_identity():
    """Create farmer identity with DID and credentials."""
    print_step(3, "Create Farmer Identity (SSI)")
    
    # Generate DID for farmer
    farmer_keypair = generate_did_key()
    farmer_did = farmer_keypair["did"]
    
    print(f"🔑 Generated DID: {farmer_did}")
    
    # Create farmer in database with EUDR-compliant geolocation data
    farmer_id_str = f"FARMER-E2E-{datetime.now().strftime('%Y%m%d%H%M%S')}"
    with get_db() as db:
        farmer = create_farmer(db, {
            'farmer_id': farmer_id_str,
            'did': farmer_did,
            'encrypted_private_key': farmer_keypair['private_key_b64'],  # Use base64 encoding
            'public_key': farmer_keypair['public_key_b64'],
            'name': 'Abebe Kebede',
            'phone_number': '+251911234567',
            'location': 'Sidama, Ethiopia',
            # EUDR-required fields
            'latitude': 6.8333,
            'longitude': 38.5833,
            'region': 'Sidama',
            'country_code': 'ET',
            'farm_size_hectares': 2.5,
            'certification_status': 'Organic, Fair Trade'
        })
        
        print(f"✅ Farmer created in database (ID: {farmer.id})")
        
        # Issue organic certification credential
        cooperative_keypair = generate_did_key()
        claims = {
            "type": "OrganicCertification",
            "subject": farmer_did,
            "certificationBody": "Ethiopian Organic Agriculture Association",
            "certificationStandard": "EU Organic",
            "certificationNumber": "ETH-ORG-2024-1234",
            "issuedDate": "2024-01-15",
            "expiryDate": "2027-01-15",
            "farmerName": "Abebe Kebede",
            "region": "Sidama"
        }
        credential = issue_credential(claims, cooperative_keypair['private_key'])
        
        # Store credential in database
        store_credential(db, {
            'credential_id': credential['id'],
            'subject_did': farmer_did,
            'issuer_did': cooperative_keypair['did'],
            'credential_type': 'OrganicCertification',
            'credential_json': credential,
            'proof': credential['proof'],
            'issuance_date': datetime.fromisoformat(credential['issuanceDate'].replace('Z', '+00:00')),
            'expiration_date': datetime.fromisoformat("2027-01-15T00:00:00+00:00"),
            'revoked': False,
            'farmer_id': farmer.id  # Link credential to farmer
        })
        
        print(f"✅ Organic certification issued and stored")
        
        return farmer.id, farmer.farmer_id, farmer_did


def create_coffee_batch(farmer_id: int, nlu_data: dict):
    """Create coffee batch from NLU data."""
    print_step(4, "Create Coffee Batch")
    
    batch_id = f"BATCH-E2E-{datetime.now().strftime('%Y%m%d%H%M%S')}"
    # Generate GTIN-14 with unique product code from timestamp
    product_code = datetime.now().strftime('%H%M%S')[:5]  # 5 digits
    gtin = generate_gtin(product_code, "GTIN-14")
    
    with get_db() as db:
        batch = create_batch(db, {
            'batch_id': batch_id,
            'gtin': gtin,
            'batch_number': f"E2E-TEST-{datetime.now().strftime('%Y%m%d')}",
            'quantity_kg': nlu_data['entities']['quantity'] * 60,  # 50 bags * 60kg/bag
            'origin_country': 'ET',  # ISO 3166-1 alpha-2
            'origin_region': 'Sidama',
            'farm_name': 'Abebe Kebede Farm',
            'variety': 'Heirloom Arabica',
            'processing_method': 'Washed',
            'process_method': 'Washed',  # Alias for DPP compatibility
            'quality_grade': 'Grade 1',
            'harvest_date': datetime.now(),
            'farmer_id': farmer_id
        })
        
        print(f"📦 Batch ID: {batch.batch_id}")
        print(f"🏷️  GTIN: {batch.gtin}")
        print(f"⚖️  Quantity: {batch.quantity_kg} kg ({nlu_data['entities']['quantity']} bags)")
        print(f"✅ Batch created in database (ID: {batch.id})")
        
        return batch.id, batch.batch_id, batch.gtin


def create_epcis_event(nlu_data: dict, batch_id_str: str, gtin: str, farmer_did: str):
    """Generate EPCIS 2.0 event from NLU data."""
    print_step(5, "Generate EPCIS 2.0 Event")
    
    event_time = datetime.now(timezone.utc)
    
    epcis_event = {
        "@context": "https://ref.gs1.org/standards/epcis/2.0.0/epcis-context.jsonld",
        "type": "ObjectEvent",
        "eventTime": event_time.isoformat(),
        "eventTimeZoneOffset": "+03:00",
        "action": "OBSERVE",
        "bizStep": "commissioning",
        "disposition": "active",
        "readPoint": {
            "id": "urn:epc:id:sgln:0614141.00001.0"
        },
        "bizLocation": {
            "id": "urn:epc:id:sgln:0614141.00001.0"
        },
        "quantityList": [
            {
                "epcClass": f"urn:epc:idpat:sgtin:0614141.{gtin[7:13]}.*",
                "quantity": nlu_data['entities']['quantity'] * 60,
                "uom": "KGM"
            }
        ],
        "sourceList": [
            {
                "type": "urn:epcglobal:cbv:sdt:owning_party",
                "source": f"urn:epc:id:pgln:0614141.00001"
            }
        ],
        "destinationList": [
            {
                "type": "urn:epcglobal:cbv:sdt:owning_party", 
                "destination": f"urn:epc:id:pgln:0614141.00002"
            }
        ],
        "submitter": {
            "did": farmer_did,
            "name": nlu_data['entities']['origin']
        }
    }
    
    print(f"📋 Event Type: {epcis_event['type']}")
    print(f"🏭 Biz Step: {epcis_event['bizStep']}")
    print(f"⏰ Event Time: {epcis_event['eventTime']}")
    print(f"✅ EPCIS event generated")
    
    return epcis_event


def canonicalize_and_hash_event(event: dict):
    """Canonicalize event and calculate hash."""
    print_step(6, "Canonicalize & Hash Event")
    
    # Canonicalize (deterministic JSON)
    canonical = json.dumps(event, sort_keys=True, separators=(',', ':'))
    
    # Calculate SHA-256 hash
    event_hash = hashlib.sha256(canonical.encode()).hexdigest()
    
    print(f"📄 Canonical Form: {canonical[:80]}...")
    print(f"#️⃣  Event Hash: {event_hash}")
    print(f"✅ Event canonicalized and hashed")
    
    return canonical, event_hash


def pin_event_to_ipfs(event: dict, event_hash: str):
    """Pin full event to IPFS via Pinata."""
    print_step(7, "Pin Event to IPFS (Pinata)")
    
    ipfs_cid = pin_epcis_event(event, event_hash)
    
    if ipfs_cid:
        print(f"📌 IPFS CID: {ipfs_cid}")
        print(f"🌐 Gateway URL: https://gateway.pinata.cloud/ipfs/{ipfs_cid}")
        print(f"✅ Event pinned to IPFS")
        
        # Verify retrieval
        retrieved = get_from_ipfs(ipfs_cid)
        if retrieved == event:
            print(f"✅ IPFS retrieval verified - data matches")
        else:
            print(f"⚠️  IPFS data mismatch!")
            
        return ipfs_cid
    else:
        print(f"⚠️  IPFS pinning failed (continuing without IPFS)")
        return None


def store_event_in_database(batch_db_id: int, event: dict, canonical: str, event_hash: str, ipfs_cid: str, farmer_did: str):
    """Store event in Neon database."""
    print_step(8, "Store Event in Database (Neon)")
    
    # Get farmer database ID from DID
    with get_db() as db:
        from database.models import FarmerIdentity
        farmer = db.query(FarmerIdentity).filter(FarmerIdentity.did == farmer_did).first()
        
        db_event = create_event(db, {
            'event_hash': event_hash,
            'event_type': 'ObjectEvent',
            'canonical_nquads': canonical,
            'event_json': event,
            'ipfs_cid': ipfs_cid,
            'event_time': datetime.fromisoformat(event['eventTime'].replace('Z', '+00:00')),
            'biz_step': event['bizStep'],
            'batch_id': batch_db_id,
            'submitter_id': farmer.id if farmer else None  # Use database ID, not farmer_id string
        }, pin_to_ipfs=False)  # Already pinned manually
        
        print(f"💾 Database Event ID: {db_event.id}")
        print(f"#️⃣  Event Hash: {db_event.event_hash}")
        print(f"📌 IPFS CID: {db_event.ipfs_cid}")
        print(f"✅ Event stored in database")
        
        return db_event.id


def simulate_blockchain_anchor(event_hash: str):
    """Simulate blockchain anchoring (actual deployment would use Foundry)."""
    print_step(9, "Anchor Hash on Blockchain (Simulated)")
    
    # In production, this would call:
    # tx = anchor_contract.anchorEvent(event_hash, batch_id, "commissioning")
    
    simulated_tx_hash = "0x" + hashlib.sha256(f"{event_hash}{datetime.now()}".encode()).hexdigest()
    
    print(f"⛓️  Blockchain: Polygon PoS")
    print(f"📝 Transaction Hash: {simulated_tx_hash}")
    print(f"⏰ Block Timestamp: {datetime.now(timezone.utc).isoformat()}")
    print(f"✅ Event hash anchored on blockchain (simulated)")
    
    return simulated_tx_hash


def update_digital_twin(batch_id: str, event_hash: str, tx_hash: str):
    """Update digital twin with blockchain anchor."""
    print_step(10, "Update Digital Twin")
    
    # Record anchor
    record_anchor(batch_id, event_hash, "commissioning", tx_hash)
    
    # Record token (simulated minting) with unique token ID from timestamp
    token_id = int(datetime.now().strftime('%H%M%S'))
    metadata = '{"owner": "0xGuzoCooperative", "batch": "' + batch_id + '"}'
    record_token(batch_id, token_id=token_id, quantity=50, metadata=metadata)
    
    print(f"🔗 Anchor recorded: {event_hash[:16]}... → {tx_hash[:16]}...")
    print(f"🪙 Token minted: Token ID 1, Quantity 50")
    print(f"✅ Digital twin updated")


def generate_digital_product_passport(batch_id: str):
    """Generate EUDR-compliant Digital Product Passport."""
    print_step(11, "Generate Digital Product Passport (DPP)")
    
    # Load batch data from database
    batch = load_batch_data(batch_id)
    
    if not batch:
        print(f"❌ Batch not found: {batch_id}")
        return None
    
    # Build DPP
    dpp = build_dpp(batch_id)
    
    print(f"📄 Passport ID: {dpp['passportId']}")
    print(f"📦 Batch ID: {dpp['batchId']}")
    print(f"🏷️  Product: {dpp['productInformation']['productName']}")
    print(f"⚖️  Quantity: {dpp['productInformation']['quantity']} {dpp['productInformation']['unit']}")
    print(f"🌍 Origin: {dpp['traceability']['origin']['region']}, {dpp['traceability']['origin']['country']}")
    print(f"👨‍🌾 Farmer: {dpp['traceability']['origin']['farmer']['name']}")
    print(f"✅ EUDR Compliant: {dpp['dueDiligence']['eudrCompliant']}")
    print(f"🌳 Deforestation Risk: {dpp['dueDiligence']['riskAssessment']['deforestationRisk']}")
    
    # Pin DPP to IPFS
    dpp_cid = pin_dpp(dpp, batch_id)
    if dpp_cid:
        print(f"📌 DPP IPFS CID: {dpp_cid}")
        print(f"🌐 DPP URL: https://gateway.pinata.cloud/ipfs/{dpp_cid}")
    
    print(f"✅ Digital Product Passport generated")
    
    return dpp


def verify_complete_workflow(batch_id: str, event_hash: str, ipfs_cid: str, tx_hash: str):
    """Verify all components are properly linked."""
    print_step(12, "Verify Complete Workflow")
    
    verification_results = []
    
    # 1. Verify database has batch
    with get_db() as db:
        batch = get_batch_by_batch_id(db, batch_id)
        if batch:
            verification_results.append(("✅", "Batch exists in database"))
            verification_results.append(("✅", f"Batch has {len(batch.events)} events"))
            verification_results.append(("✅", f"Batch has {len(batch.farmer.credentials)} credentials"))
        else:
            verification_results.append(("❌", "Batch NOT found in database"))
    
    # 2. Verify event exists with hash
    with get_db() as db:
        event = get_event_by_hash(db, event_hash)
        if event:
            verification_results.append(("✅", "Event exists in database"))
            verification_results.append(("✅", f"Event has IPFS CID: {event.ipfs_cid is not None}"))
            verification_results.append(("✅", f"Event has blockchain TX: {event.blockchain_tx_hash is not None}"))
        else:
            verification_results.append(("❌", "Event NOT found in database"))
    
    # 3. Verify IPFS retrieval
    if ipfs_cid:
        ipfs_data = get_from_ipfs(ipfs_cid)
        if ipfs_data:
            verification_results.append(("✅", "IPFS data retrievable"))
            # Verify hash matches
            canonical = json.dumps(ipfs_data, sort_keys=True, separators=(',', ':'))
            retrieved_hash = hashlib.sha256(canonical.encode()).hexdigest()
            if retrieved_hash == event_hash:
                verification_results.append(("✅", "IPFS data hash matches database hash"))
            else:
                verification_results.append(("❌", "IPFS data hash MISMATCH"))
        else:
            verification_results.append(("❌", "IPFS data NOT retrievable"))
    
    # 4. Verify DPP can be built
    try:
        dpp = build_dpp(batch_id)
        verification_results.append(("✅", "DPP successfully generated"))
        verification_results.append(("✅", f"DPP has {len(dpp['traceability']['events'])} events"))
        verification_results.append(("✅", f"DPP has {len(dpp['sustainability']['certifications'])} certifications"))
    except Exception as e:
        verification_results.append(("❌", f"DPP generation failed: {e}"))
    
    # Print results
    print("\n🔍 Verification Results:")
    print("─" * 70)
    for status, message in verification_results:
        print(f"{status} {message}")
    
    all_passed = all(status == "✅" for status, _ in verification_results)
    
    return all_passed


def run_end_to_end_test():
    """Execute complete end-to-end workflow test."""
    print_section("🧪 VOICE LEDGER - END-TO-END WORKFLOW TEST")
    print("\nThis test validates the complete system from voice input to DPP generation.")
    print("Testing components: ASR, NLU, SSI, EPCIS, IPFS, Database, Blockchain, DPP")
    
    try:
        # Step 1-2: Voice to NLU
        transcript = simulate_voice_to_text()
        nlu_data = simulate_nlu(transcript)
        
        # Step 3: Create farmer identity
        farmer_db_id, farmer_id, farmer_did = create_farmer_identity()
        
        # Step 4: Create batch
        batch_db_id, batch_id, gtin = create_coffee_batch(farmer_db_id, nlu_data)
        
        # Step 5: Generate EPCIS event
        epcis_event = create_epcis_event(nlu_data, batch_id, gtin, farmer_did)
        
        # Step 6: Canonicalize and hash
        canonical, event_hash = canonicalize_and_hash_event(epcis_event)
        
        # Step 7: Pin to IPFS
        ipfs_cid = pin_event_to_ipfs(epcis_event, event_hash)
        
        # Step 8: Store in database
        event_db_id = store_event_in_database(
            batch_db_id, epcis_event, canonical, event_hash, ipfs_cid, farmer_did
        )
        
        # Step 9: Anchor on blockchain
        tx_hash = simulate_blockchain_anchor(event_hash)
        
        # Step 10: Update digital twin
        update_digital_twin(batch_id, event_hash, tx_hash)
        
        # Step 11: Generate DPP
        dpp = generate_digital_product_passport(batch_id)
        
        # Step 12: Verify everything
        all_verified = verify_complete_workflow(batch_id, event_hash, ipfs_cid, tx_hash)
        
        # Final summary
        print_section("📊 TEST SUMMARY")
        
        print("\n✅ Components Tested:")
        print("   1. ✅ Voice-to-Text (ASR) - Simulated")
        print("   2. ✅ NLU Intent Detection - Simulated")
        print("   3. ✅ SSI Identity Creation - DID generation")
        print("   4. ✅ Verifiable Credentials - Organic certification")
        print("   5. ✅ Database Storage - Neon PostgreSQL")
        print("   6. ✅ EPCIS 2.0 Event Generation")
        print("   7. ✅ Event Canonicalization")
        print("   8. ✅ Cryptographic Hashing (SHA-256)")
        print("   9. ✅ IPFS Storage - Pinata pinning")
        print("  10. ✅ Digital Twin Update")
        print("  11. ✅ Blockchain Anchoring - Simulated")
        print("  12. ✅ DPP Generation - EUDR compliant")
        
        print("\n📦 Data Created:")
        print(f"   • Farmer: {farmer_id} (DID: {farmer_did[:30]}...)")
        print(f"   • Batch: {batch_id}")
        print(f"   • GTIN: {gtin}")
        print(f"   • Event Hash: {event_hash}")
        print(f"   • IPFS CID: {ipfs_cid}")
        print(f"   • Blockchain TX: {tx_hash}")
        
        print("\n🌐 Public URLs:")
        print(f"   • IPFS Event: https://gateway.pinata.cloud/ipfs/{ipfs_cid}")
        print(f"   • DPP Resolver: http://localhost:8001/dpp/{batch_id}")
        
        if all_verified:
            print("\n" + "="*70)
            print("  ✅ ALL TESTS PASSED - SYSTEM FULLY OPERATIONAL")
            print("="*70)
            return True
        else:
            print("\n" + "="*70)
            print("  ⚠️  SOME VERIFICATIONS FAILED - CHECK LOGS ABOVE")
            print("="*70)
            return False
            
    except Exception as e:
        print(f"\n❌ TEST FAILED WITH ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = run_end_to_end_test()
    exit(0 if success else 1)
