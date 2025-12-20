"""
Database package for Voice Ledger (Neon PostgreSQL)
"""

from .models import Base, FarmerIdentity, CoffeeBatch, EPCISEvent, VerifiableCredential, OfflineQueue
from .connection import get_db, engine
from .crud import (
    create_farmer,
    create_batch,
    create_event,
    get_batch_by_gtin,
    get_batch_by_batch_id,
    get_batch_by_id_or_gtin,
    get_farmer_by_did,
    get_farmer_by_farmer_id,
    get_batch_events,
    store_credential,
    get_event_by_hash,
    update_event_blockchain_tx,
    get_all_batches,
    get_all_farmers
)

__all__ = [
    "Base",
    "FarmerIdentity",
    "CoffeeBatch",
    "EPCISEvent",
    "VerifiableCredential",
    "OfflineQueue",
    "get_db",
    "engine",
    "create_farmer",
    "create_batch",
    "create_event",
    "get_batch_by_gtin",
    "get_batch_by_batch_id",
    "get_batch_by_id_or_gtin",
    "get_farmer_by_did",
    "get_farmer_by_farmer_id",
    "get_batch_events",
    "store_credential",
    "get_event_by_hash",
    "update_event_blockchain_tx",
    "get_all_batches",
    "get_all_farmers",
]
