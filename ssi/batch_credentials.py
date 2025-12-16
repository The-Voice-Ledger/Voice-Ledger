"""
Coffee Batch Credential Issuance

Issues verifiable credentials for coffee batch commission events.
Each credential serves as cryptographic proof that a farmer recorded a batch.
"""

from datetime import datetime, timezone
from ssi.credentials.issue import issue_credential
from ssi.user_identity import get_user_private_key
from database.models import SessionLocal, VerifiableCredential, UserIdentity
import json


def issue_batch_credential(
    batch_id: str,
    user_id: int,
    user_did: str,
    quantity_kg: float,
    variety: str,
    origin: str,
    harvest_date: str = None,
    processing_method: str = None,
    epcis_event_hash: str = None,
    blockchain_tx_hash: str = None
) -> dict:
    """
    Issue a verifiable credential for a coffee batch commission.
    
    This creates cryptographic proof that:
    1. User X (identified by DID) recorded batch Y
    2. Batch has specific characteristics (variety, quantity, origin)
    3. Event was recorded at specific timestamp
    4. Event is anchored to blockchain (if tx_hash provided)
    
    Args:
        batch_id: Unique batch identifier (e.g., "B001")
        user_id: Database user ID
        user_did: User's DID
        quantity_kg: Batch quantity in kilograms
        variety: Coffee variety (e.g., "Yirgacheffe")
        origin: Origin location
        harvest_date: Harvest date (ISO format)
        processing_method: Processing method (e.g., "Washed")
        epcis_event_hash: Hash of EPCIS event
        blockchain_tx_hash: Blockchain transaction hash
        
    Returns:
        Verifiable credential dictionary
        
    Example:
        >>> vc = issue_batch_credential(
        ...     batch_id="B001",
        ...     user_id=1,
        ...     user_did="did:key:z6Mk...",
        ...     quantity_kg=100.0,
        ...     variety="Yirgacheffe",
        ...     origin="Gedeo"
        ... )
    """
    # Build credential claims
    claims = {
        "type": "CoffeeBatchCredential",
        "id": user_did,
        "batchId": batch_id,
        "quantityKg": quantity_kg,
        "variety": variety,
        "origin": origin,
        "recordedAt": datetime.now(timezone.utc).isoformat()
    }
    
    # Add optional fields
    if harvest_date:
        claims["harvestDate"] = harvest_date
    if processing_method:
        claims["processingMethod"] = processing_method
    if epcis_event_hash:
        claims["epcisEventHash"] = epcis_event_hash
    if blockchain_tx_hash:
        claims["blockchainTx"] = blockchain_tx_hash
    
    # Get user's private key for signing
    user_private_key = get_user_private_key(user_id)
    
    # Issue the credential (signs with user's key)
    credential = issue_credential(claims, user_private_key)
    
    # Store credential in database
    db = SessionLocal()
    try:
        vc_record = VerifiableCredential(
            credential_id=credential["id"],
            credential_type="CoffeeBatchCredential",
            subject_did=user_did,
            issuer_did=user_did,  # Self-issued (farmer signs their own record)
            issuance_date=datetime.fromisoformat(credential["issuanceDate"].replace("Z", "+00:00")),
            credential_json=credential,
            proof=credential["proof"],
            farmer_id=None,  # Not linked to FarmerIdentity (this is UserIdentity)
            revoked=False
        )
        
        db.add(vc_record)
        db.commit()
        db.refresh(vc_record)
        
        return credential
        
    finally:
        db.close()


def get_user_credentials(user_did: str, credential_type: str = None) -> list:
    """
    Retrieve all credentials for a user.
    
    Args:
        user_did: User's DID
        credential_type: Optional filter by credential type
        
    Returns:
        List of credential dictionaries
    """
    db = SessionLocal()
    try:
        query = db.query(VerifiableCredential).filter_by(
            subject_did=user_did,
            revoked=False
        )
        
        if credential_type:
            query = query.filter_by(credential_type=credential_type)
        
        credentials = query.order_by(VerifiableCredential.issuance_date.desc()).all()
        
        return [vc.credential_json for vc in credentials]
        
    finally:
        db.close()


def get_credential_count(user_did: str, credential_type: str = None) -> int:
    """
    Count credentials for a user (for credit scoring).
    
    Args:
        user_did: User's DID
        credential_type: Optional filter by type
        
    Returns:
        Number of credentials
    """
    db = SessionLocal()
    try:
        query = db.query(VerifiableCredential).filter_by(
            subject_did=user_did,
            revoked=False
        )
        
        if credential_type:
            query = query.filter_by(credential_type=credential_type)
        
        return query.count()
        
    finally:
        db.close()


def calculate_simple_credit_score(user_did: str) -> dict:
    """
    Calculate a simple credit score based on batch credentials.
    
    This is a basic implementation. Production system would include:
    - Time-weighted scoring (recent activity matters more)
    - Quality metrics (verified vs unverified)
    - Consistency scoring (regular production)
    - Volume scoring (total kg produced)
    
    Args:
        user_did: User's DID
        
    Returns:
        Dictionary with:
        - score: Credit score (0-1000)
        - batch_count: Number of batches recorded
        - total_kg: Total coffee produced (if calculable)
        - first_batch_date: Date of first batch
        - latest_batch_date: Date of latest batch
    """
    credentials = get_user_credentials(user_did, "CoffeeBatchCredential")
    
    if not credentials:
        return {
            "score": 0,
            "batch_count": 0,
            "total_kg": 0,
            "first_batch_date": None,
            "latest_batch_date": None
        }
    
    # Calculate metrics
    batch_count = len(credentials)
    total_kg = sum(vc["credentialSubject"].get("quantityKg", 0) for vc in credentials)
    
    dates = [datetime.fromisoformat(vc["issuanceDate"].replace("Z", "+00:00")) for vc in credentials]
    first_batch_date = min(dates)
    latest_batch_date = max(dates)
    
    # Calculate days active
    days_active = (latest_batch_date - first_batch_date).days + 1
    
    # Simple scoring formula
    score = 0
    score += batch_count * 10  # 10 points per batch
    score += min(total_kg / 10, 100)  # Up to 100 points for volume
    score += min(days_active / 30 * 5, 100)  # Up to 100 points for longevity
    
    # Consistency bonus (batches per month)
    if days_active > 30:
        batches_per_month = batch_count / (days_active / 30)
        score += min(batches_per_month * 20, 100)  # Up to 100 for consistency
    
    score = min(score, 1000)  # Cap at 1000
    
    return {
        "score": int(score),
        "batch_count": batch_count,
        "total_kg": total_kg,
        "first_batch_date": first_batch_date.isoformat(),
        "latest_batch_date": latest_batch_date.isoformat(),
        "days_active": days_active
    }


if __name__ == "__main__":
    print("Testing Coffee Batch Credential Issuance...\n")
    
    from ssi.user_identity import get_or_create_user_identity
    
    # Create test user
    db = SessionLocal()
    identity = get_or_create_user_identity(
        telegram_user_id="test_farmer_456",
        telegram_username="coffee_farmer",
        telegram_first_name="Almaz",
        telegram_last_name="Tesfaye",
        db_session=db
    )
    db.close()
    
    print(f"✓ User: {identity['did']}\n")
    
    # Issue batch credential
    vc = issue_batch_credential(
        batch_id="TEST_BATCH_001",
        user_id=identity["user_id"],
        user_did=identity["did"],
        quantity_kg=50.0,
        variety="Yirgacheffe",
        origin="Gedeo",
        processing_method="Washed"
    )
    
    print(f"✓ Issued Credential:")
    print(f"  ID: {vc['id']}")
    print(f"  Type: {vc['type']}")
    print(f"  Batch ID: {vc['credentialSubject']['batchId']}")
    print(f"  Quantity: {vc['credentialSubject']['quantityKg']} kg")
    
    # Calculate credit score
    score = calculate_simple_credit_score(identity["did"])
    print(f"\n✓ Credit Score: {score['score']}/1000")
    print(f"  Batches: {score['batch_count']}")
    print(f"  Total Production: {score['total_kg']} kg")
