"""
Verification Credential Issuance

Issues verifiable credentials signed by cooperatives after batch verification.
These credentials provide third-party attestation of coffee batch quality and quantity.
"""

from datetime import datetime, timezone
from ssi.credentials.issue import issue_credential
from ssi.org_identity import decrypt_organization_private_key
from database.models import SessionLocal, VerifiableCredential, Organization
import logging

logger = logging.getLogger(__name__)


def issue_verification_credential(
    batch_id: str,
    farmer_did: str,
    organization_id: int,
    verified_quantity_kg: float,
    claimed_quantity_kg: float,
    variety: str,
    origin: str,
    quality_notes: str = None,
    verifier_did: str = None,
    verifier_name: str = None,
    has_photo_evidence: bool = False
) -> dict:
    """
    Issue a verifiable credential for batch verification.
    
    This creates cryptographic proof that:
    1. Organization X verified batch Y from farmer Z
    2. Batch was inspected and quantity/quality confirmed
    3. Verification was performed by authorized cooperative manager
    4. Evidence (photos, notes) was collected
    
    The credential is signed with the organization's DID, providing
    trusted third-party attestation.
    
    Args:
        batch_id: Unique batch identifier (e.g., "B001")
        farmer_did: Farmer's DID (credential subject)
        organization_id: Database ID of verifying organization
        verified_quantity_kg: Actual verified quantity
        claimed_quantity_kg: Originally claimed quantity
        variety: Coffee variety
        origin: Origin location
        quality_notes: Quality assessment notes
        verifier_did: DID of the person who verified
        verifier_name: Name of verifier
        has_photo_evidence: Whether photos were uploaded
        
    Returns:
        Verifiable credential dictionary
        
    Example:
        >>> vc = issue_verification_credential(
        ...     batch_id="B001",
        ...     farmer_did="did:key:z6Mk...",
        ...     organization_id=1,
        ...     verified_quantity_kg=98.5,
        ...     claimed_quantity_kg=100.0,
        ...     variety="Yirgacheffe",
        ...     origin="Gedeo"
        ... )
    """
    db = SessionLocal()
    try:
        # Get organization details
        org = db.query(Organization).filter_by(id=organization_id).first()
        
        if not org:
            raise ValueError(f"Organization {organization_id} not found")
        
        # Build credential claims
        claims = {
            "type": "CoffeeVerificationCredential",
            "id": farmer_did,  # Subject is the farmer
            "batchId": batch_id,
            "verifiedQuantityKg": verified_quantity_kg,
            "claimedQuantityKg": claimed_quantity_kg,
            "variety": variety,
            "origin": origin,
            "verifiedAt": datetime.now(timezone.utc).isoformat(),
            "verifyingOrganization": {
                "id": org.id,
                "name": org.name,
                "type": org.type,
                "did": org.did
            }
        }
        
        # Add optional fields
        if quality_notes:
            claims["qualityNotes"] = quality_notes
        if verifier_did:
            claims["verifierDid"] = verifier_did
        if verifier_name:
            claims["verifierName"] = verifier_name
        if has_photo_evidence:
            claims["hasPhotoEvidence"] = True
        
        # Calculate verification accuracy
        if claimed_quantity_kg > 0:
            accuracy = (verified_quantity_kg / claimed_quantity_kg) * 100
            claims["verificationAccuracy"] = round(accuracy, 2)
        
        # Decrypt organization's private key for signing
        org_private_key_bytes = decrypt_organization_private_key(org.encrypted_private_key)
        org_private_key_hex = org_private_key_bytes.hex()
        
        # Issue the credential (signed by organization)
        credential = issue_credential(claims, org_private_key_hex)
        
        # Override issuer to be organization DID (issue_credential uses public key hex)
        credential["issuer"] = org.did
        
        # Store credential in database
        vc_record = VerifiableCredential(
            credential_id=credential["id"],
            credential_type="CoffeeVerificationCredential",
            subject_did=farmer_did,
            issuer_did=org.did,  # Organization is the issuer
            issuance_date=datetime.fromisoformat(credential["issuanceDate"].replace("Z", "+00:00")),
            credential_json=credential,
            proof=credential["proof"],
            farmer_id=None,  # Could link to FarmerIdentity if available
            revoked=False
        )
        
        db.add(vc_record)
        db.commit()
        db.refresh(vc_record)
        
        logger.info(
            f"Issued verification credential for batch {batch_id} "
            f"by {org.name} (DID: {org.did[:30]}...)"
        )
        
        return credential
        
    except Exception as e:
        logger.error(f"Failed to issue verification credential: {e}", exc_info=True)
        db.rollback()
        raise
    finally:
        db.close()


def get_verification_credentials(farmer_did: str) -> list:
    """
    Retrieve all verification credentials for a farmer.
    
    These are credentials issued BY cooperatives TO farmers,
    attesting to verified batches.
    
    Args:
        farmer_did: Farmer's DID
        
    Returns:
        List of verification credential dictionaries
    """
    db = SessionLocal()
    try:
        credentials = db.query(VerifiableCredential).filter_by(
            subject_did=farmer_did,
            credential_type="CoffeeVerificationCredential",
            revoked=False
        ).order_by(VerifiableCredential.issuance_date.desc()).all()
        
        return [vc.credential_json for vc in credentials]
        
    finally:
        db.close()


def get_verification_count(farmer_did: str) -> int:
    """
    Count verification credentials for a farmer.
    
    This represents the number of times cooperatives have
    verified the farmer's batches.
    
    Args:
        farmer_did: Farmer's DID
        
    Returns:
        Number of verification credentials
    """
    db = SessionLocal()
    try:
        count = db.query(VerifiableCredential).filter_by(
            subject_did=farmer_did,
            credential_type="CoffeeVerificationCredential",
            revoked=False
        ).count()
        
        return count
        
    finally:
        db.close()


def calculate_verification_trust_score(farmer_did: str) -> dict:
    """
    Calculate trust score based on verification credentials.
    
    Factors:
    - Number of verifications
    - Number of different organizations that verified
    - Verification accuracy (claimed vs verified quantity)
    - Consistency over time
    
    Args:
        farmer_did: Farmer's DID
        
    Returns:
        dict: Trust score metrics
    """
    credentials = get_verification_credentials(farmer_did)
    
    if not credentials:
        return {
            "trust_score": 0,
            "verification_count": 0,
            "unique_verifiers": 0,
            "avg_accuracy": 0,
            "message": "No verifications yet"
        }
    
    # Count unique verifying organizations
    unique_orgs = set(
        cred.get("credentialSubject", {}).get("verifyingOrganization", {}).get("did")
        for cred in credentials
    )
    
    # Calculate average verification accuracy
    accuracies = [
        cred.get("credentialSubject", {}).get("verificationAccuracy", 100)
        for cred in credentials
        if "verificationAccuracy" in cred.get("credentialSubject", {})
    ]
    avg_accuracy = sum(accuracies) / len(accuracies) if accuracies else 100
    
    # Calculate trust score (0-1000)
    score = 0
    score += min(len(credentials) * 50, 400)  # Up to 400 for verification count
    score += min(len(unique_orgs) * 100, 300)  # Up to 300 for diverse verifiers
    score += (avg_accuracy / 100) * 300  # Up to 300 for accuracy
    
    return {
        "trust_score": int(score),
        "verification_count": len(credentials),
        "unique_verifiers": len(unique_orgs),
        "avg_accuracy": round(avg_accuracy, 2),
        "message": f"Verified by {len(unique_orgs)} organization(s)"
    }


if __name__ == "__main__":
    print("Testing Verification Credential Issuance...\n")
    
    # This would be called after a cooperative manager verifies a batch
    print("Example: Cooperative verifies farmer's batch")
    print("- Farmer brings batch to cooperative")
    print("- Manager inspects, weighs, grades")
    print("- Manager uploads photos, enters notes")
    print("- System issues credential signed by cooperative")
    print("\nCredential Structure:")
    print("""{
    "@context": ["https://www.w3.org/2018/credentials/v1"],
    "type": ["VerifiableCredential", "CoffeeVerificationCredential"],
    "issuer": "did:key:z6Mk... (Cooperative DID)",
    "credentialSubject": {
        "id": "did:key:z6Mk... (Farmer DID)",
        "batchId": "B001",
        "verifiedQuantityKg": 98.5,
        "claimedQuantityKg": 100.0,
        "variety": "Yirgacheffe",
        "origin": "Gedeo",
        "verifyingOrganization": {
            "name": "Guzo Cooperative",
            "type": "COOPERATIVE"
        },
        "qualityNotes": "Grade 1, 11% moisture, no defects"
    },
    "proof": {
        "type": "Ed25519Signature2020",
        "signature": "..."
    }
}""")
