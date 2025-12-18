"""
CRUD operations for Voice Ledger
"""

from sqlalchemy.orm import Session
from database.models import FarmerIdentity, CoffeeBatch, EPCISEvent, VerifiableCredential
from datetime import datetime
from typing import Optional, List
from ipfs.ipfs_storage import pin_epcis_event, pin_credential
from blockchain.blockchain_anchor import anchor_event_to_blockchain

def create_farmer(db: Session, farmer_data: dict) -> FarmerIdentity:
    """Create new farmer identity."""
    farmer = FarmerIdentity(**farmer_data)
    db.add(farmer)
    db.commit()
    db.refresh(farmer)
    return farmer

def create_batch(db: Session, batch_data: dict) -> CoffeeBatch:
    """Create new coffee batch."""
    batch = CoffeeBatch(**batch_data)
    db.add(batch)
    db.commit()
    db.refresh(batch)
    return batch

def create_event(db: Session, event_data: dict, pin_to_ipfs: bool = True, anchor_to_blockchain: bool = True) -> EPCISEvent:
    """
    Store EPCIS event and optionally pin to IPFS + anchor to blockchain.
    
    Args:
        db: Database session
        event_data: Event data including event_json
        pin_to_ipfs: If True, pin full event to IPFS and store CID
        anchor_to_blockchain: If True, anchor event hash to Base Sepolia
    
    Returns:
        Created EPCISEvent with ipfs_cid and blockchain_tx_hash if successful
    """
    # Extract full event JSON if present
    event_json = event_data.get('event_json')
    event_hash = event_data.get('event_hash')
    batch_id = event_data.get('batch_id')
    
    # Step 1: Pin to IPFS if enabled
    ipfs_cid = None
    if pin_to_ipfs and event_json and event_hash:
        ipfs_cid = pin_epcis_event(event_json, event_hash)
        if ipfs_cid:
            event_data['ipfs_cid'] = ipfs_cid
            print(f"✓ Event pinned to IPFS: {ipfs_cid}")
    
    # Step 2: Anchor to blockchain if enabled
    if anchor_to_blockchain and event_hash and batch_id:
        # Get batch info for blockchain metadata
        batch = db.query(CoffeeBatch).filter(CoffeeBatch.id == batch_id).first()
        
        if batch:
            tx_hash = anchor_event_to_blockchain(
                batch_id=batch.batch_id,
                event_hash=event_hash,
                ipfs_cid=ipfs_cid,
                event_type=event_data.get('event_type', 'ObjectEvent'),
                location=batch.origin or "",
                submitter=event_data.get('submitter_did', '')
            )
            
            if tx_hash:
                event_data['blockchain_tx_hash'] = tx_hash
                event_data['blockchain_confirmed'] = True
                event_data['blockchain_confirmed_at'] = datetime.utcnow()
                print(f"✓ Event anchored to blockchain: {tx_hash}")
    
    # Step 3: Save to database
    event = EPCISEvent(**event_data)
    db.add(event)
    db.commit()
    db.refresh(event)
    return event

def get_batch_by_gtin(db: Session, gtin: str) -> Optional[CoffeeBatch]:
    """Query batch by GTIN."""
    return db.query(CoffeeBatch).filter(CoffeeBatch.gtin == gtin).first()

def get_batch_by_batch_id(db: Session, batch_id: str) -> Optional[CoffeeBatch]:
    """Query batch by batch_id."""
    return db.query(CoffeeBatch).filter(CoffeeBatch.batch_id == batch_id).first()

def get_farmer_by_did(db: Session, did: str) -> Optional[FarmerIdentity]:
    """Query farmer by DID."""
    return db.query(FarmerIdentity).filter(FarmerIdentity.did == did).first()

def get_farmer_by_farmer_id(db: Session, farmer_id: str) -> Optional[FarmerIdentity]:
    """Query farmer by farmer_id."""
    return db.query(FarmerIdentity).filter(FarmerIdentity.farmer_id == farmer_id).first()

def get_batch_events(db: Session, batch_id: int) -> List[EPCISEvent]:
    """Get all events for a batch."""
    return db.query(EPCISEvent)\
        .filter(EPCISEvent.batch_id == batch_id)\
        .order_by(EPCISEvent.event_time)\
        .all()

def store_credential(db: Session, credential_data: dict, pin_to_ipfs: bool = False) -> VerifiableCredential:
    """
    Store Verifiable Credential and optionally pin to IPFS.
    
    Args:
        db: Database session
        credential_data: Credential data including credential_json
        pin_to_ipfs: If True, pin credential to IPFS
    
    Returns:
        Created VerifiableCredential
    """
    # Pin to IPFS if enabled
    if pin_to_ipfs:
        credential_json = credential_data.get('credential_json')
        credential_id = credential_data.get('credential_id')
        if credential_json and credential_id:
            ipfs_cid = pin_credential(credential_json, credential_id)
            if ipfs_cid:
                print(f"✅ Credential {credential_id} pinned to IPFS: {ipfs_cid}")
    
    credential = VerifiableCredential(**credential_data)
    db.add(credential)
    db.commit()
    db.refresh(credential)
    return credential

def get_event_by_hash(db: Session, event_hash: str) -> Optional[EPCISEvent]:
    """Query event by hash."""
    return db.query(EPCISEvent).filter(EPCISEvent.event_hash == event_hash).first()

def update_event_blockchain_tx(db: Session, event_id: int, tx_hash: str) -> EPCISEvent:
    """Update event with blockchain transaction hash and confirmation timestamp."""
    event = db.query(EPCISEvent).filter(EPCISEvent.id == event_id).first()
    if event:
        event.blockchain_tx_hash = tx_hash
        event.blockchain_confirmed = True
        event.blockchain_confirmed_at = datetime.utcnow()
        db.commit()
        db.refresh(event)
    return event

def get_all_batches(db: Session, limit: int = 100) -> List[CoffeeBatch]:
    """Get all batches (for dashboard) with eagerly loaded relationships."""
    from sqlalchemy.orm import joinedload
    return db.query(CoffeeBatch)\
        .options(joinedload(CoffeeBatch.events))\
        .options(joinedload(CoffeeBatch.farmer))\
        .order_by(CoffeeBatch.created_at.desc())\
        .limit(limit)\
        .all()

def get_all_farmers(db: Session, limit: int = 100) -> List[FarmerIdentity]:
    """Get all farmers (for dashboard) with eagerly loaded relationships."""
    from sqlalchemy.orm import joinedload
    return db.query(FarmerIdentity)\
        .options(joinedload(FarmerIdentity.credentials))\
        .options(joinedload(FarmerIdentity.batches))\
        .order_by(FarmerIdentity.created_at.desc())\
        .limit(limit)\
        .all()
