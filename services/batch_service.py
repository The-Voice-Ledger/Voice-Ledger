"""
Batch Service — shared business logic for coffee batch operations.

Called by:
  - voice/agent/registry.py (Telegram / Mini App path)
  - voice/livekit_agent.py  (LiveKit web agent path)
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


def query_batches(
    db: Session,
    *,
    batch_id: Optional[str] = None,
    status: Optional[str] = None,
    origin: Optional[str] = None,
    user_id: Optional[int] = None,
    limit: int = 10,
) -> Dict[str, Any]:
    """
    Query coffee batches from the database.

    Returns:
        {
            "found": bool,
            "single": bool,          # True if a specific batch was looked up
            "batch": {...} | None,    # Single batch dict (when single=True)
            "batches": [...],         # List of batch dicts (when single=False)
            "count": int,
        }
    """
    from database.models import CoffeeBatch

    # --- Single batch lookup ---
    if batch_id:
        from database.crud import get_batch_by_id_or_gtin

        batch = get_batch_by_id_or_gtin(db, batch_id)
        if batch:
            return {
                "found": True,
                "single": True,
                "batch": {
                    "batch_id": batch.batch_id,
                    "gtin": batch.gtin,
                    "origin": batch.origin,
                    "variety": batch.variety,
                    "quantity_kg": batch.quantity_kg,
                    "status": batch.status,
                    "quality_grade": batch.quality_grade,
                    "created_at": str(batch.created_at) if batch.created_at else None,
                },
                "batches": [],
                "count": 1,
            }
        return {
            "found": False,
            "single": True,
            "batch": None,
            "batches": [],
            "count": 0,
            "query_batch_id": batch_id,
        }

    # --- Filtered list query ---
    query = db.query(CoffeeBatch)
    if status:
        query = query.filter(CoffeeBatch.status == status.upper())
    if origin:
        query = query.filter(CoffeeBatch.origin.ilike(f"%{origin}%"))
    if user_id:
        query = query.filter(CoffeeBatch.created_by_user_id == user_id)

    batches = query.order_by(CoffeeBatch.created_at.desc()).limit(limit).all()

    batch_list = [
        {
            "batch_id": b.batch_id,
            "origin": b.origin,
            "variety": b.variety,
            "quantity_kg": b.quantity_kg,
            "status": b.status,
            "created_at": str(b.created_at) if b.created_at else None,
        }
        for b in batches
    ]

    return {
        "found": len(batch_list) > 0,
        "single": False,
        "batch": None,
        "batches": batch_list,
        "count": len(batch_list),
    }
