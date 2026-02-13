"""
Tool Registry

Maps tool names → callable handler functions.
Wraps the existing command_integration handlers so the agent can call them
without any changes to the battle-tested handler code.

Also adds new READ-ONLY tools (query_batches, search_knowledge) that the
old NLU pipeline couldn't express (it only had write intents).
"""

import logging
from typing import Dict, Any, Tuple, Callable, Optional
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


class ToolRegistry:
    """
    Registry that connects OpenAI tool names → Voice Ledger handler functions.
    
    Each handler returns (message: str, result_data: dict) on success,
    or raises VoiceCommandError on failure.
    """
    
    def __init__(self):
        self._tools: Dict[str, Callable] = {}
        self._register_defaults()
    
    def _register_defaults(self):
        """Register the built-in supply chain tools."""
        # Write tools — delegate to command_integration.py handlers
        self._tools["record_commission"] = self._wrap_commission
        self._tools["record_shipment"] = self._wrap_shipment
        self._tools["record_receipt"] = self._wrap_receipt
        self._tools["record_transformation"] = self._wrap_transformation
        self._tools["pack_batches"] = self._wrap_pack
        self._tools["unpack_batches"] = self._wrap_unpack
        self._tools["split_batch"] = self._wrap_split
        
        # Read tools — new capabilities the old pipeline didn't have
        self._tools["query_batches"] = self._query_batches
        self._tools["search_knowledge"] = self._search_knowledge
    
    def register(self, name: str, handler: Callable):
        """Register a custom tool handler."""
        self._tools[name] = handler
    
    def get(self, name: str) -> Optional[Callable]:
        """Get handler by tool name."""
        return self._tools.get(name)
    
    def has(self, name: str) -> bool:
        return name in self._tools
    
    @property
    def tool_names(self):
        return list(self._tools.keys())
    
    # ------------------------------------------------------------------
    # Write tool wrappers (delegate to existing handlers)
    # ------------------------------------------------------------------
    
    def _wrap_commission(
        self, db: Session, args: Dict[str, Any],
        user_id: int = None, user_did: str = None
    ) -> Tuple[str, Dict[str, Any]]:
        """Wrap handle_record_commission."""
        from voice.command_integration import handle_record_commission
        
        # Map agent args → handler entities
        entities = {
            "quantity": args.get("quantity_kg", 0),
            "origin": args.get("origin", "Unknown"),
            "product": args.get("variety", "Arabica Coffee"),
            "unit": "kg",  # Agent already converts bags→kg
            "grade": args.get("grade", "A"),
        }
        return handle_record_commission(db, entities, user_id=user_id, user_did=user_did)
    
    def _wrap_shipment(
        self, db: Session, args: Dict[str, Any],
        user_id: int = None, user_did: str = None
    ) -> Tuple[str, Dict[str, Any]]:
        """Wrap handle_record_shipment."""
        from voice.command_integration import handle_record_shipment
        
        entities = {
            "batch_id": args.get("batch_id"),
            "destination": args.get("destination"),
            "carrier": args.get("carrier"),
            "transport_mode": args.get("transport_mode"),
        }
        return handle_record_shipment(db, entities, user_id=user_id)
    
    def _wrap_receipt(
        self, db: Session, args: Dict[str, Any],
        user_id: int = None, user_did: str = None
    ) -> Tuple[str, Dict[str, Any]]:
        """Wrap handle_record_receipt."""
        from voice.command_integration import handle_record_receipt
        
        entities = {
            "batch_id": args.get("batch_id"),
            "condition": args.get("condition", "good"),
            "location": args.get("location", ""),
        }
        return handle_record_receipt(db, entities, user_id=user_id, user_did=user_did)
    
    def _wrap_transformation(
        self, db: Session, args: Dict[str, Any],
        user_id: int = None, user_did: str = None
    ) -> Tuple[str, Dict[str, Any]]:
        """Wrap handle_record_transformation."""
        from voice.command_integration import handle_record_transformation
        
        entities = {
            "batch_id": args.get("batch_id"),
            "input_batch_id": args.get("batch_id"),
            "transformation_type": args.get("transformation_type", "processing"),
            "output_quantity_kg": args.get("output_quantity_kg"),
            "output_variety": args.get("output_variety"),
        }
        return handle_record_transformation(db, entities, user_id=user_id, user_did=user_did)
    
    def _wrap_pack(
        self, db: Session, args: Dict[str, Any],
        user_id: int = None, user_did: str = None
    ) -> Tuple[str, Dict[str, Any]]:
        """Wrap handle_pack_batches."""
        from voice.command_integration import handle_pack_batches
        
        entities = {
            "batch_ids": args.get("batch_ids", []),
            "container_id": args.get("container_id"),
            "container_type": args.get("container_type", "pallet"),
        }
        return handle_pack_batches(db, entities, user_id=user_id, user_did=user_did)
    
    def _wrap_unpack(
        self, db: Session, args: Dict[str, Any],
        user_id: int = None, user_did: str = None
    ) -> Tuple[str, Dict[str, Any]]:
        """Wrap handle_unpack_batches."""
        from voice.command_integration import handle_unpack_batches
        
        entities = {
            "container_id": args.get("container_id"),
        }
        return handle_unpack_batches(db, entities, user_id=user_id, user_did=user_did)
    
    def _wrap_split(
        self, db: Session, args: Dict[str, Any],
        user_id: int = None, user_did: str = None
    ) -> Tuple[str, Dict[str, Any]]:
        """Wrap handle_split_batch."""
        from voice.command_integration import handle_split_batch
        
        entities = {
            "batch_id": args.get("batch_id"),
            "parent_batch_id": args.get("batch_id"),
            "splits": args.get("splits", []),
        }
        return handle_split_batch(db, entities, user_id=user_id, user_did=user_did)
    
    # ------------------------------------------------------------------
    # Read tool implementations (new — not in old pipeline)
    # ------------------------------------------------------------------
    
    def _query_batches(
        self, db: Session, args: Dict[str, Any],
        user_id: int = None, user_did: str = None
    ) -> Tuple[str, Dict[str, Any]]:
        """
        Query coffee batches from the database.
        Replaces the old OPERATIONAL query type from hybrid_router.
        """
        from database.models import CoffeeBatch
        
        batch_id = args.get("batch_id")
        status = args.get("status")
        origin = args.get("origin")
        limit = args.get("limit", 10)
        
        query = db.query(CoffeeBatch)
        
        # Filter by specific batch
        if batch_id:
            from database.crud import get_batch_by_id_or_gtin
            batch = get_batch_by_id_or_gtin(db, batch_id)
            if batch:
                return (
                    f"Found batch {batch.batch_id}",
                    {
                        "batch_id": batch.batch_id,
                        "gtin": batch.gtin,
                        "origin": batch.origin,
                        "variety": batch.variety,
                        "quantity_kg": batch.quantity_kg,
                        "status": batch.status,
                        "created_at": str(batch.created_at) if batch.created_at else None,
                        "quality_grade": batch.quality_grade,
                    },
                )
            else:
                return (f"Batch '{batch_id}' not found", {"found": False})
        
        # Apply filters
        if status:
            query = query.filter(CoffeeBatch.status == status.upper())
        if origin:
            query = query.filter(CoffeeBatch.origin.ilike(f"%{origin}%"))
        if user_id:
            query = query.filter(CoffeeBatch.created_by_user_id == user_id)
        
        batches = query.order_by(CoffeeBatch.created_at.desc()).limit(limit).all()
        
        if not batches:
            return ("No batches found matching your criteria", {"batches": [], "count": 0})
        
        batch_list = []
        for b in batches:
            batch_list.append({
                "batch_id": b.batch_id,
                "origin": b.origin,
                "variety": b.variety,
                "quantity_kg": b.quantity_kg,
                "status": b.status,
                "created_at": str(b.created_at) if b.created_at else None,
            })
        
        summary = f"Found {len(batch_list)} batch(es)"
        return (summary, {"batches": batch_list, "count": len(batch_list)})
    
    def _search_knowledge(
        self, db: Session, args: Dict[str, Any],
        user_id: int = None, user_did: str = None
    ) -> Tuple[str, Dict[str, Any]]:
        """
        Search the RAG knowledge base (ChromaDB).
        Replaces the old DOCUMENTATION query type from hybrid_router.
        """
        query_text = args.get("query", "")
        
        try:
            from voice.rag.hybrid_router import search_documentation
            results = search_documentation(query_text, top_k=3)
            
            if not results:
                return ("No relevant documentation found", {"results": []})
            
            # Format results for the agent's context
            context_chunks = []
            for r in results:
                chunk = r.get("content", r.get("text", ""))
                source = r.get("source", "unknown")
                context_chunks.append(f"[{source}]: {chunk}")
            
            combined = "\n\n---\n\n".join(context_chunks)
            return (
                f"Found {len(results)} relevant document(s)",
                {"context": combined, "source_count": len(results)},
            )
        except Exception as e:
            logger.warning(f"Knowledge search failed: {e}")
            return (
                "Knowledge base search is currently unavailable",
                {"error": str(e)},
            )


# Module-level singleton
_registry: Optional[ToolRegistry] = None


def get_tool_registry() -> ToolRegistry:
    """Get or create the global tool registry."""
    global _registry
    if _registry is None:
        _registry = ToolRegistry()
    return _registry
