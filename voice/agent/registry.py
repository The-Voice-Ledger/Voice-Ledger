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
        
        # Marketplace tools (Agent #3)
        self._tools["create_rfq"] = self._create_rfq
        self._tools["browse_rfqs"] = self._browse_rfqs
        self._tools["submit_offer"] = self._submit_offer
        self._tools["accept_offer"] = self._accept_offer
        self._tools["list_my_offers"] = self._list_my_offers
        
        # Compliance tools (Agent #4)
        self._tools["check_eudr_compliance"] = self._check_eudr_compliance
        self._tools["check_mass_balance"] = self._check_mass_balance
        
        # DPP / Traceability tools (Agent #5)
        self._tools["get_dpp"] = self._get_dpp
        self._tools["get_container_dpp"] = self._get_container_dpp
        self._tools["trace_lineage"] = self._trace_lineage
        self._tools["validate_dpp"] = self._validate_dpp

        # Verification tools (Agent #6)
        self._tools["list_pending_verifications"] = self._list_pending_verifications
        self._tools["verify_batch"] = self._verify_batch

        # Blockchain tools (Agent #7)
        self._tools["check_blockchain_anchor"] = self._check_blockchain_anchor
        self._tools["get_token_info"] = self._get_token_info
        self._tools["verify_batch_hash"] = self._verify_batch_hash

        # Chainlink CRE / DON Attestation tools (Agent #8)
        self._tools["request_don_attestation"] = self._request_don_attestation
        self._tools["check_don_attestation"] = self._check_don_attestation
        self._tools["get_don_provenance_metrics"] = self._get_don_provenance_metrics
    
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
        """Wrap handle_record_commission with CRE auto-attestation."""
        from voice.command_integration import handle_record_commission
        
        # Map agent args → handler entities
        entities = {
            "quantity": args.get("quantity_kg", 0),
            "origin": args.get("origin", "Unknown"),
            "product": args.get("variety", "Arabica Coffee"),
            "unit": "kg",  # Agent already converts bags→kg
            "grade": args.get("grade", "A"),
        }
        msg, data = handle_record_commission(db, entities, user_id=user_id, user_did=user_did)

        # ── Post-commission CRE hook ──
        # If the farmer has GPS coords, automatically request a DON
        # deforestation attestation. Best-effort — never blocks commission.
        try:
            self._auto_request_don_attestation(db, user_id, data)
        except Exception as e:
            logger.debug("CRE auto-attestation skipped: %s", e)

        return msg, data
    
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

    # ------------------------------------------------------------------
    # Marketplace tool implementations (Agent #3)
    # ------------------------------------------------------------------

    def _create_rfq(
        self, db: Session, args: Dict[str, Any],
        user_id: int = None, user_did: str = None
    ) -> Tuple[str, Dict[str, Any]]:
        """Create a new RFQ on the marketplace (buyers only)."""
        from database.models import RFQ, UserIdentity, Organization, RFQBroadcast
        from datetime import datetime, timedelta

        # Validate user is a buyer
        user = db.query(UserIdentity).filter_by(id=user_id).first()
        if not user:
            return ("User not found. Please register first.", {"error": "user_not_found"})
        if user.role not in ("BUYER", "ADMIN"):
            return (
                "Only buyers can create RFQs. Your role is "
                f"{user.role}.",
                {"error": "role_not_buyer"},
            )

        quantity_kg = args.get("quantity_kg", 0)
        if quantity_kg <= 0:
            return ("Quantity must be greater than zero.", {"error": "invalid_quantity"})

        # Generate RFQ number
        count = db.query(RFQ).count() + 1
        rfq_number = f"RFQ-{count:06d}"

        rfq = RFQ(
            buyer_id=user.id,
            rfq_number=rfq_number,
            quantity_kg=quantity_kg,
            variety=args.get("variety"),
            processing_method=args.get("processing_method"),
            grade=args.get("grade"),
            delivery_location=args.get("delivery_location"),
            status="OPEN",
            expires_at=datetime.utcnow() + timedelta(days=30),
        )
        db.add(rfq)
        db.flush()  # Assign rfq.id without committing (get_db context auto-commits)

        # Smart broadcast to cooperatives
        from database.models import Organization as Org
        cooperatives = db.query(Org).filter_by(type="COOPERATIVE").all()
        broadcast_count = 0
        for coop in cooperatives:
            broadcast = RFQBroadcast(
                rfq_id=rfq.id,
                cooperative_id=coop.id,
                broadcast_reason="SMART_MATCH",
                relevance_score=0.75,
                notified_at=datetime.utcnow(),
            )
            db.add(broadcast)
            broadcast_count += 1
        db.flush()  # Ensure all broadcast records are staged

        variety_str = f" ({rfq.variety})" if rfq.variety else ""
        return (
            f"RFQ {rfq_number} created for {quantity_kg} kg{variety_str}. "
            f"Broadcasted to {broadcast_count} cooperative(s).",
            {
                "rfq_id": rfq.id,
                "rfq_number": rfq_number,
                "quantity_kg": quantity_kg,
                "variety": rfq.variety,
                "broadcast_count": broadcast_count,
            },
        )

    def _browse_rfqs(
        self, db: Session, args: Dict[str, Any],
        user_id: int = None, user_did: str = None
    ) -> Tuple[str, Dict[str, Any]]:
        """Browse open RFQs on the marketplace."""
        from database.models import RFQ, RFQOffer, UserIdentity, Organization

        query = db.query(RFQ)

        status = args.get("status", "OPEN")
        if status:
            query = query.filter(RFQ.status == status.upper())
        variety = args.get("variety")
        if variety:
            query = query.filter(RFQ.variety.ilike(f"%{variety}%"))

        limit = args.get("limit", 10)
        rfqs = query.order_by(RFQ.created_at.desc()).limit(limit).all()

        if not rfqs:
            return ("No open RFQs found on the marketplace.", {"rfqs": [], "count": 0})

        rfq_list = []
        for rfq in rfqs:
            buyer = db.query(UserIdentity).filter_by(id=rfq.buyer_id).first()
            buyer_org = (
                db.query(Organization).filter_by(id=buyer.organization_id).first()
                if buyer and buyer.organization_id
                else None
            )
            offer_count = db.query(RFQOffer).filter_by(rfq_id=rfq.id).count()
            rfq_list.append({
                "rfq_id": rfq.id,
                "rfq_number": rfq.rfq_number,
                "buyer": buyer_org.name if buyer_org else "Unknown",
                "quantity_kg": rfq.quantity_kg,
                "variety": rfq.variety,
                "grade": rfq.grade,
                "delivery_location": rfq.delivery_location,
                "status": rfq.status,
                "offer_count": offer_count,
                "expires_at": str(rfq.expires_at) if rfq.expires_at else None,
            })

        return (
            f"Found {len(rfq_list)} open RFQ(s) on the marketplace.",
            {"rfqs": rfq_list, "count": len(rfq_list)},
        )

    def _submit_offer(
        self, db: Session, args: Dict[str, Any],
        user_id: int = None, user_did: str = None
    ) -> Tuple[str, Dict[str, Any]]:
        """Submit an offer on an RFQ (cooperative managers only)."""
        from database.models import (
            RFQ, RFQOffer, RFQBroadcast, UserIdentity, Organization,
        )
        from datetime import datetime

        user = db.query(UserIdentity).filter_by(id=user_id).first()
        if not user:
            return ("User not found. Please register first.", {"error": "user_not_found"})
        if user.role not in ("COOPERATIVE_MANAGER", "ADMIN"):
            return (
                f"Only cooperative managers can submit offers. Your role is {user.role}.",
                {"error": "role_not_cooperative_manager"},
            )

        # Resolve RFQ by id or number
        rfq_id = args.get("rfq_id")
        rfq_number = args.get("rfq_number")
        rfq = None
        if rfq_id:
            rfq = db.query(RFQ).filter_by(id=rfq_id).first()
        elif rfq_number:
            rfq = db.query(RFQ).filter_by(rfq_number=rfq_number).first()

        if not rfq:
            return ("RFQ not found. Use browse_rfqs to see available requests.", {"error": "rfq_not_found"})
        if rfq.status != "OPEN":
            return (f"RFQ {rfq.rfq_number} is {rfq.status}, not open for offers.", {"error": "rfq_not_open"})

        quantity = args.get("quantity_offered_kg", 0)
        price = args.get("price_per_kg", 0)
        if quantity <= 0 or price <= 0:
            return ("Quantity and price must be greater than zero.", {"error": "invalid_values"})

        count = db.query(RFQOffer).count() + 1
        offer_number = f"OFF-{count:06d}"

        offer = RFQOffer(
            rfq_id=rfq.id,
            cooperative_id=user.organization_id,
            offer_number=offer_number,
            quantity_offered_kg=quantity,
            price_per_kg=price,
            delivery_timeline=args.get("delivery_timeline"),
            status="PENDING",
        )
        db.add(offer)

        # Update broadcast record
        broadcast = db.query(RFQBroadcast).filter_by(
            rfq_id=rfq.id, cooperative_id=user.organization_id,
        ).first()
        if broadcast:
            broadcast.responded_at = datetime.utcnow()

        db.flush()  # Ensure offer gets an ID (get_db context auto-commits)

        coop_org = db.query(Organization).filter_by(id=user.organization_id).first()
        return (
            f"Offer {offer_number} submitted on {rfq.rfq_number}: "
            f"{quantity} kg at ${price}/kg.",
            {
                "offer_id": offer.id,
                "offer_number": offer_number,
                "rfq_number": rfq.rfq_number,
                "quantity_offered_kg": quantity,
                "price_per_kg": price,
                "cooperative": coop_org.name if coop_org else "Unknown",
            },
        )

    def _accept_offer(
        self, db: Session, args: Dict[str, Any],
        user_id: int = None, user_did: str = None
    ) -> Tuple[str, Dict[str, Any]]:
        """Accept an offer (buyers only)."""
        from database.models import (
            RFQ, RFQOffer, RFQAcceptance, UserIdentity, Organization,
        )
        from datetime import datetime

        user = db.query(UserIdentity).filter_by(id=user_id).first()
        if not user:
            return ("User not found.", {"error": "user_not_found"})

        rfq_id = args.get("rfq_id")
        offer_id = args.get("offer_id")

        rfq = db.query(RFQ).filter_by(id=rfq_id).first()
        if not rfq:
            return ("RFQ not found.", {"error": "rfq_not_found"})
        if rfq.buyer_id != user.id and user.role != "ADMIN":
            return ("You can only accept offers on your own RFQs.", {"error": "not_owner"})

        offer = db.query(RFQOffer).filter_by(id=offer_id, rfq_id=rfq_id).first()
        if not offer:
            return ("Offer not found.", {"error": "offer_not_found"})
        if offer.status != "PENDING":
            return (f"Offer is {offer.status}, cannot accept.", {"error": "offer_not_pending"})

        quantity_accepted = args.get("quantity_accepted_kg", offer.quantity_offered_kg)
        if quantity_accepted > offer.quantity_offered_kg:
            return (
                f"Cannot accept more than offered ({offer.quantity_offered_kg} kg).",
                {"error": "exceeds_offered"},
            )

        count = db.query(RFQAcceptance).count() + 1
        acceptance_number = f"ACC-{count:06d}"

        acceptance = RFQAcceptance(
            rfq_id=rfq.id,
            offer_id=offer.id,
            acceptance_number=acceptance_number,
            quantity_accepted_kg=quantity_accepted,
            payment_terms=args.get("payment_terms"),
            payment_status="PENDING",
            delivery_status="PENDING",
            accepted_at=datetime.utcnow(),
        )
        db.add(acceptance)
        offer.status = "ACCEPTED"

        # Update RFQ status
        if quantity_accepted >= rfq.quantity_kg:
            rfq.status = "FULFILLED"
        else:
            rfq.status = "PARTIALLY_FILLED"

        db.flush()  # Ensure acceptance gets an ID (get_db context auto-commits)

        coop_org = db.query(Organization).filter_by(id=offer.cooperative_id).first()
        return (
            f"Offer accepted! Acceptance {acceptance_number}: "
            f"{quantity_accepted} kg from {coop_org.name if coop_org else 'cooperative'}.",
            {
                "acceptance_id": acceptance.id,
                "acceptance_number": acceptance_number,
                "rfq_number": rfq.rfq_number,
                "offer_number": offer.offer_number,
                "quantity_accepted_kg": quantity_accepted,
                "cooperative": coop_org.name if coop_org else "Unknown",
            },
        )

    def _list_my_offers(
        self, db: Session, args: Dict[str, Any],
        user_id: int = None, user_did: str = None
    ) -> Tuple[str, Dict[str, Any]]:
        """List offers submitted by the current cooperative."""
        from database.models import RFQOffer, RFQ, UserIdentity, Organization

        user = db.query(UserIdentity).filter_by(id=user_id).first()
        if not user:
            return ("User not found.", {"error": "user_not_found"})

        query = db.query(RFQOffer).filter_by(cooperative_id=user.organization_id)
        status = args.get("status")
        if status:
            query = query.filter(RFQOffer.status == status.upper())

        offers = query.order_by(RFQOffer.created_at.desc()).limit(20).all()
        if not offers:
            return ("You have no offers yet.", {"offers": [], "count": 0})

        offer_list = []
        for offer in offers:
            rfq = db.query(RFQ).filter_by(id=offer.rfq_id).first()
            offer_list.append({
                "offer_id": offer.id,
                "offer_number": offer.offer_number,
                "rfq_number": rfq.rfq_number if rfq else "Unknown",
                "quantity_offered_kg": offer.quantity_offered_kg,
                "price_per_kg": offer.price_per_kg,
                "status": offer.status,
                "created_at": str(offer.created_at) if offer.created_at else None,
            })

        return (
            f"You have {len(offer_list)} offer(s).",
            {"offers": offer_list, "count": len(offer_list)},
        )

    # ------------------------------------------------------------------
    # Compliance tool implementations (Agent #4)
    # ------------------------------------------------------------------

    def _check_eudr_compliance(
        self, db: Session, args: Dict[str, Any],
        user_id: int = None, user_did: str = None
    ) -> Tuple[str, Dict[str, Any]]:
        """Check EUDR compliance for a list of batch IDs."""
        from voice.epcis.validators import validate_eudr_compliance

        batch_ids = args.get("batch_ids", [])
        if not batch_ids:
            return ("No batch IDs provided. Please specify which batches to check.", {"error": "no_batch_ids"})

        is_valid, error_msg = validate_eudr_compliance(batch_ids, db)

        if is_valid:
            return (
                f"All {len(batch_ids)} batch(es) are EUDR compliant. "
                "GPS coordinates verified for all farmers.",
                {
                    "compliant": True,
                    "batch_count": len(batch_ids),
                    "batch_ids": batch_ids,
                },
            )
        else:
            return (
                f"EUDR compliance issue: {error_msg}",
                {
                    "compliant": False,
                    "batch_count": len(batch_ids),
                    "batch_ids": batch_ids,
                    "error": error_msg,
                },
            )

    def _check_mass_balance(
        self, db: Session, args: Dict[str, Any],
        user_id: int = None, user_did: str = None
    ) -> Tuple[str, Dict[str, Any]]:
        """Validate mass balance between inputs and outputs."""
        from voice.epcis.validators import validate_mass_balance

        input_quantities = args.get("input_quantities", [])
        output_quantities = args.get("output_quantities", [])
        allow_loss = args.get("allow_loss", False)

        if not input_quantities or not output_quantities:
            return (
                "Both input and output quantities are required.",
                {"error": "missing_quantities"},
            )

        is_valid, error_msg = validate_mass_balance(
            input_quantities, output_quantities, allow_loss=allow_loss,
        )

        total_input = sum(float(q.get("quantity", 0)) for q in input_quantities)
        total_output = sum(float(q.get("quantity", 0)) for q in output_quantities)

        if is_valid:
            return (
                f"Mass balance valid. Input: {total_input} kg, Output: {total_output} kg.",
                {
                    "valid": True,
                    "total_input_kg": total_input,
                    "total_output_kg": total_output,
                    "difference_kg": round(total_input - total_output, 2),
                },
            )
        else:
            return (
                f"Mass balance violation: {error_msg}",
                {
                    "valid": False,
                    "total_input_kg": total_input,
                    "total_output_kg": total_output,
                    "error": error_msg,
                },
            )

    # ------------------------------------------------------------------
    # DPP / Traceability tool implementations (Agent #5)
    # ------------------------------------------------------------------

    def _get_dpp(
        self, db: Session, args: Dict[str, Any],
        user_id: int = None, user_did: str = None
    ) -> Tuple[str, Dict[str, Any]]:
        """Generate or retrieve the Digital Product Passport for a batch."""
        batch_id = args.get("batch_id")
        if not batch_id:
            return ("Please specify a batch ID.", {"error": "no_batch_id"})

        try:
            from dpp.dpp_builder import build_dpp
            dpp = build_dpp(batch_id=batch_id)
        except ValueError as e:
            return (f"Could not generate DPP: {e}", {"error": str(e)})
        except Exception as e:
            logger.warning(f"DPP generation failed for {batch_id}: {e}")
            return (f"DPP generation failed for batch '{batch_id}'.", {"error": str(e)})

        # ── Embed DON attestation if available ──
        try:
            from dpp.dpp_builder import build_don_attestation_section
            don_section = build_don_attestation_section(batch_id, db)
            if don_section and don_section.get("attestationExists"):
                dpp["donAttestation"] = don_section
        except Exception as e:
            logger.debug("DON attestation section skipped: %s", e)

        # Build a concise summary for the voice response
        product = dpp.get("productInformation", {})
        trace = dpp.get("traceability", {})
        origin = trace.get("origin", {})
        dd = dpp.get("dueDiligence", {})
        bc = dpp.get("blockchain", {})
        don = dpp.get("donAttestation", {})

        don_line = ""
        if don.get("attestationExists"):
            don_line = (
                f"\n• DON Attestation: {don.get('riskLabel', '?')} risk "
                f"({'✅ Compliant' if don.get('eudrCompliant') else '❌ Non-compliant'})"
            )

        summary = (
            f"📋 DPP for {dpp.get('batchId', batch_id)}:\n"
            f"• Product: {product.get('name', 'Coffee')} "
            f"({product.get('variety', 'Unknown variety')})\n"
            f"• Origin: {origin.get('region', '?')}, {origin.get('country', '?')}\n"
            f"• EUDR: {'✅ Compliant' if dd.get('eudrCompliant') else '❌ Not compliant'}\n"
            f"• Blockchain: {'✅ Anchored' if bc.get('transactionHash') else '⏳ Pending'}"
            f"{don_line}"
        )

        return (
            summary,
            {
                "batch_id": dpp.get("batchId"),
                "passport_id": dpp.get("passportId"),
                "eudr_compliant": dd.get("eudrCompliant"),
                "deforestation_risk": dd.get("riskAssessment", {}).get("deforestationRisk"),
                "blockchain_tx": bc.get("transactionHash"),
                "don_attested": don.get("attestationExists", False),
                "don_risk_label": don.get("riskLabel"),
                "qr_code": dpp.get("qrCode", {}).get("base64") if isinstance(dpp.get("qrCode"), dict) else None,
            },
        )

    def _get_container_dpp(
        self, db: Session, args: Dict[str, Any],
        user_id: int = None, user_did: str = None
    ) -> Tuple[str, Dict[str, Any]]:
        """Get aggregated DPP for a shipping container."""
        container_id = args.get("container_id")
        if not container_id:
            return ("Please specify a container ID.", {"error": "no_container_id"})

        try:
            from dpp.dpp_builder import build_aggregated_dpp
            dpp = build_aggregated_dpp(container_id=container_id)
        except ValueError as e:
            return (f"Container not found: {e}", {"error": str(e)})
        except Exception as e:
            logger.warning(f"Container DPP failed for {container_id}: {e}")
            return (
                f"Could not generate container DPP for '{container_id}'.",
                {"error": str(e)},
            )

        product = dpp.get("productInformation", {})
        contributors = dpp.get("traceability", {}).get("contributors", [])
        num_farmers = product.get("numberOfContributors", len(contributors))
        total_qty_str = product.get("totalQuantity", "0 kg")  # e.g. "1500 kg"

        # Build top-contributor summary (max 5)
        top = contributors[:5]
        contrib_lines = []
        for c in top:
            pct = c.get("contributionPercent", "?")  # Already formatted, e.g. "33.3%"
            name = c.get("farmer", "Unknown")
            contrib_lines.append(f"  • {name}: {pct}")
        if len(contributors) > 5:
            contrib_lines.append(f"  … and {len(contributors) - 5} more")

        summary = (
            f"📦 Container {container_id}:\n"
            f"• {num_farmers} contributing farmers, {total_qty_str} total\n"
            + "\n".join(contrib_lines)
        )

        return (
            summary,
            {
                "container_id": container_id,
                "num_farmers": num_farmers,
                "total_quantity": total_qty_str,
                "contributors_count": len(contributors),
            },
        )

    def _trace_lineage(
        self, db: Session, args: Dict[str, Any],
        user_id: int = None, user_did: str = None
    ) -> Tuple[str, Dict[str, Any]]:
        """Trace the full supply chain lineage of a product."""
        product_id = args.get("product_id")
        if not product_id:
            return ("Please specify a product or batch ID.", {"error": "no_product_id"})

        max_depth = args.get("max_depth", 5)

        try:
            from dpp.dpp_builder import build_recursive_dpp
            lineage = build_recursive_dpp(product_id=product_id, max_depth=max_depth)
        except ValueError as e:
            return (f"Could not trace lineage: {e}", {"error": str(e)})
        except Exception as e:
            logger.warning(f"Lineage trace failed for {product_id}: {e}")
            return (
                f"Lineage trace failed for '{product_id}'.",
                {"error": str(e)},
            )

        # Extract contributor data — recursive DPP has 'contributors' not 'chainOfCustody'
        contributors = lineage.get("traceability", {}).get("contributors", [])
        trace_method = lineage.get("traceability", {}).get("traceMethod", "")
        product_info = lineage.get("productInformation", {})
        num_levels = product_info.get("aggregationLevels", "Unknown")

        farmer_lines = []
        for c in contributors[:10]:  # Cap at 10 for voice readability
            name = c.get("farmer", "?")
            pct = c.get("contributionPercent", "?")
            region = c.get("origin", {}).get("region", "?")
            farmer_lines.append(f"  • {name} ({region}): {pct}")
        if len(contributors) > 10:
            farmer_lines.append(f"  … and {len(contributors) - 10} more")

        total_qty_str = product_info.get("totalQuantity", "? kg")

        summary = (
            f"🔍 Lineage for {product_id}:\n"
            f"• {len(contributors)} contributing farmers, {total_qty_str}\n"
            f"• {trace_method}\n"
            + ("\n".join(farmer_lines) if farmer_lines else "  No farmers found.")
        )

        return (
            summary,
            {
                "product_id": product_id,
                "contributors_count": len(contributors),
                "total_quantity": total_qty_str,
            },
        )

    def _validate_dpp(
        self, db: Session, args: Dict[str, Any],
        user_id: int = None, user_did: str = None
    ) -> Tuple[str, Dict[str, Any]]:
        """Validate a DPP for completeness and EUDR compliance."""
        batch_id = args.get("batch_id")
        if not batch_id:
            return ("Please specify a batch ID.", {"error": "no_batch_id"})

        try:
            from dpp.dpp_builder import build_dpp, validate_dpp
            dpp = build_dpp(batch_id=batch_id)
            is_valid, errors = validate_dpp(dpp)
        except ValueError as e:
            return (f"Could not build DPP to validate: {e}", {"error": str(e)})
        except Exception as e:
            logger.warning(f"DPP validation failed for {batch_id}: {e}")
            return (f"Validation failed for batch '{batch_id}'.", {"error": str(e)})

        if is_valid:
            return (
                f"✅ DPP for {batch_id} is valid and EUDR-compliant.",
                {"batch_id": batch_id, "valid": True, "errors": []},
            )
        else:
            error_list = "\n".join(f"  • {e}" for e in errors)
            return (
                f"❌ DPP for {batch_id} has {len(errors)} issue(s):\n{error_list}",
                {"batch_id": batch_id, "valid": False, "errors": errors},
            )

    # ------------------------------------------------------------------
    # Verification tool implementations (Agent #6)
    # ------------------------------------------------------------------

    def _list_pending_verifications(
        self, db: Session, args: Dict[str, Any],
        user_id: int = None, user_did: str = None
    ) -> Tuple[str, Dict[str, Any]]:
        """List batches pending verification."""
        from database.models import CoffeeBatch

        query = db.query(CoffeeBatch).filter(
            CoffeeBatch.status == "PENDING_VERIFICATION",
        )

        origin = args.get("origin")
        if origin:
            query = query.filter(CoffeeBatch.origin.ilike(f"%{origin}%"))

        limit = args.get("limit", 10)
        batches = query.order_by(CoffeeBatch.created_at.desc()).limit(limit).all()

        if not batches:
            return ("No batches pending verification.", {"batches": [], "count": 0})

        batch_list = []
        for b in batches:
            farmer_name = "Unknown"
            try:
                if b.farmer:
                    farmer_name = b.farmer.name or "Unknown"
            except Exception:
                pass  # Lazy-load may fail outside eager context
            batch_list.append({
                "batch_id": b.batch_id,
                "origin": b.origin,
                "variety": b.variety,
                "quantity_kg": b.quantity_kg,
                "created_at": str(b.created_at) if b.created_at else None,
                "farmer": farmer_name,
            })

        return (
            f"{len(batch_list)} batch(es) pending verification.",
            {"batches": batch_list, "count": len(batch_list)},
        )

    def _verify_batch(
        self, db: Session, args: Dict[str, Any],
        user_id: int = None, user_did: str = None
    ) -> Tuple[str, Dict[str, Any]]:
        """Verify a coffee batch (cooperative managers only)."""
        from database.models import CoffeeBatch, UserIdentity
        from datetime import datetime

        # Validate user role
        user = db.query(UserIdentity).filter_by(id=user_id).first()
        if not user:
            return ("User not found. Please register first.", {"error": "user_not_found"})
        if user.role not in ("COOPERATIVE_MANAGER", "ADMIN"):
            return (
                f"Only cooperative managers can verify batches. Your role is {user.role}.",
                {"error": "role_not_cooperative_manager"},
            )

        batch_id = args.get("batch_id")
        if not batch_id:
            return ("Please specify a batch ID to verify.", {"error": "no_batch_id"})

        # Look up batch
        from database.crud import get_batch_by_id_or_gtin
        batch = get_batch_by_id_or_gtin(db, batch_id)
        if not batch:
            return (f"Batch '{batch_id}' not found.", {"error": "batch_not_found"})

        if batch.status == "VERIFIED":
            return (
                f"Batch {batch.batch_id} is already verified "
                f"(verified at {batch.verified_at}).",
                {"error": "already_verified", "batch_id": batch.batch_id},
            )

        # Perform verification
        verified_quantity = args.get("verified_quantity_kg", batch.quantity_kg)
        quality_notes = args.get("quality_notes")

        batch.status = "VERIFIED"
        batch.verified_quantity = verified_quantity
        batch.verification_notes = quality_notes
        batch.verified_by_did = user_did or user.did
        batch.verifying_organization_id = user.organization_id
        batch.verified_at = datetime.utcnow()
        batch.verification_used = True

        # Try to issue verification credential
        credential_issued = False
        if user.organization_id and batch.created_by_did:
            try:
                from ssi.verification_credentials import issue_verification_credential
                issue_verification_credential(
                    batch_id=batch.batch_id,
                    farmer_did=batch.created_by_did,
                    organization_id=user.organization_id,
                    verified_quantity_kg=verified_quantity,
                    claimed_quantity_kg=batch.quantity_kg,
                    variety=batch.variety,
                    origin=batch.origin,
                    quality_notes=quality_notes,
                    verifier_did=user_did or user.did,
                    verifier_name=user.telegram_first_name,
                    has_photo_evidence=False,
                )
                credential_issued = True
            except Exception as e:
                logger.warning(f"Credential issuance failed (non-fatal): {e}")

        db.flush()  # Stage changes (get_db context auto-commits)

        return (
            f"Batch {batch.batch_id} verified: {verified_quantity} kg. "
            f"{'Credential issued.' if credential_issued else ''}",
            {
                "batch_id": batch.batch_id,
                "verified_quantity_kg": verified_quantity,
                "quality_notes": quality_notes,
                "credential_issued": credential_issued,
                "verified_by": user.telegram_first_name or user.did,
            },
        )


    # ------------------------------------------------------------------
    # Blockchain tool implementations (Agent #7)
    # ------------------------------------------------------------------

    def _check_blockchain_anchor(
        self, db: Session, args: Dict[str, Any],
        user_id: int = None, user_did: str = None
    ) -> Tuple[str, Dict[str, Any]]:
        """Check if a batch is anchored on the blockchain."""
        batch_id = args.get("batch_id")
        if not batch_id:
            return ("Please specify a batch ID.", {"error": "no_batch_id"})

        try:
            anchor = _get_blockchain_anchor()
            info = anchor.get_batch_info(batch_id)
        except Exception as e:
            logger.warning(f"Blockchain query failed for {batch_id}: {e}")
            return (
                f"Could not check blockchain for '{batch_id}'. "
                "The blockchain node may be unavailable.",
                {"error": str(e)},
            )

        if not info:
            return (
                f"Batch {batch_id} is not yet anchored on the blockchain.",
                {"batch_id": batch_id, "anchored": False},
            )

        from datetime import datetime
        ts = info.get("timestamp", 0)
        anchor_time = (
            datetime.utcfromtimestamp(ts).strftime("%Y-%m-%d %H:%M UTC")
            if ts else "Unknown"
        )

        return (
            f"✅ Batch {batch_id} is anchored on Base Sepolia:\n"
            f"• Event type: {info.get('event_type', '?')}\n"
            f"• Location: {info.get('location', '?')}\n"
            f"• IPFS: {info.get('ipfs_cid', 'N/A')}\n"
            f"• Anchored: {anchor_time}",
            {
                "batch_id": batch_id,
                "anchored": True,
                "event_hash": info.get("event_hash"),
                "event_type": info.get("event_type"),
                "ipfs_cid": info.get("ipfs_cid"),
                "submitter": info.get("submitter"),
                "timestamp": ts,
            },
        )

    def _get_token_info(
        self, db: Session, args: Dict[str, Any],
        user_id: int = None, user_did: str = None
    ) -> Tuple[str, Dict[str, Any]]:
        """Look up ERC-1155 batch token metadata."""
        token_id = args.get("token_id")
        if token_id is None:
            return ("Please specify a token ID.", {"error": "no_token_id"})

        try:
            from blockchain.token_manager import get_token_manager
            manager = get_token_manager()
            metadata = manager.get_batch_metadata(int(token_id))
        except Exception as e:
            logger.warning(f"Token lookup failed for {token_id}: {e}")
            return (
                f"Could not look up token {token_id}. "
                "The blockchain node may be unavailable.",
                {"error": str(e)},
            )

        if not metadata:
            return (
                f"Token {token_id} not found on-chain.",
                {"token_id": token_id, "found": False},
            )

        quantity_kg = metadata.get("quantity", 0) / 1000  # grams → kg
        is_agg = metadata.get("is_aggregated", False)
        children = metadata.get("child_token_ids", [])

        agg_info = ""
        if is_agg:
            agg_info = f"\n• Aggregated container with {len(children)} child tokens"

        return (
            f"🔗 Token {token_id}:\n"
            f"• Batch: {metadata.get('batch_id', '?')}\n"
            f"• Quantity: {quantity_kg:.1f} kg\n"
            f"• IPFS: {metadata.get('ipfs_cid', 'N/A')}"
            f"{agg_info}",
            {
                "token_id": token_id,
                "found": True,
                "batch_id": metadata.get("batch_id"),
                "quantity_kg": quantity_kg,
                "ipfs_cid": metadata.get("ipfs_cid"),
                "is_aggregated": is_agg,
                "child_token_ids": children,
            },
        )

    def _verify_batch_hash(
        self, db: Session, args: Dict[str, Any],
        user_id: int = None, user_did: str = None
    ) -> Tuple[str, Dict[str, Any]]:
        """Verify batch data integrity by comparing hash against blockchain."""
        batch_id = args.get("batch_id")
        if not batch_id:
            return ("Please specify a batch ID.", {"error": "no_batch_id"})

        try:
            from blockchain.batch_hasher import hash_batch_from_db_model
            from database.crud import get_batch_by_id_or_gtin

            batch = get_batch_by_id_or_gtin(db, batch_id)
            if not batch:
                return (f"Batch '{batch_id}' not found.", {"error": "batch_not_found"})

            # Compute current hash from DB data
            current_hash = hash_batch_from_db_model(batch)

            # Get on-chain hash
            anchor = _get_blockchain_anchor()
            on_chain = anchor.get_batch_info(batch.batch_id)
        except Exception as e:
            logger.warning(f"Hash verification failed for {batch_id}: {e}")
            return (
                f"Could not verify hash for '{batch_id}'. "
                "The blockchain node may be unavailable.",
                {"error": str(e)},
            )

        if not on_chain:
            return (
                f"Batch {batch.batch_id} is not anchored on-chain yet — "
                "cannot verify hash integrity.",
                {"batch_id": batch.batch_id, "anchored": False, "verified": None},
            )

        on_chain_hash = on_chain.get("event_hash", "")
        current_hex = current_hash.hex() if isinstance(current_hash, bytes) else str(current_hash)

        # Normalize for comparison
        a = current_hex.lower().replace("0x", "")
        b = on_chain_hash.lower().replace("0x", "")
        match = a == b

        if match:
            return (
                f"✅ Batch {batch.batch_id} data integrity verified — "
                "hash matches blockchain record. No tampering detected.",
                {
                    "batch_id": batch.batch_id,
                    "anchored": True,
                    "verified": True,
                    "hash": current_hex,
                },
            )
        else:
            return (
                f"⚠️ Batch {batch.batch_id} hash MISMATCH — data may have "
                "been modified since it was anchored on-chain.",
                {
                    "batch_id": batch.batch_id,
                    "anchored": True,
                    "verified": False,
                    "current_hash": current_hex,
                    "on_chain_hash": on_chain_hash,
                },
            )

    # ------------------------------------------------------------------
    # Chainlink CRE / DON Attestation tools (Agent #8)
    # ------------------------------------------------------------------

    def _request_don_attestation(
        self, db: Session, args: Dict[str, Any],
        user_id: int = None, user_did: str = None
    ) -> Tuple[str, Dict[str, Any]]:
        """Request a DON-attested deforestation check for a farm."""
        farm_id = args.get("farm_id")
        if not farm_id:
            return ("Please specify a farm/farmer ID.", {"error": "no_farm_id"})

        try:
            client = _get_cre_client()
            result = client.request_deforestation_attestation(farm_id)
        except Exception as e:
            logger.warning("DON attestation request failed for %s: %s", farm_id, e)
            return (
                f"Could not request DON attestation for '{farm_id}'. "
                "The CRE service may be unavailable.",
                {"error": str(e)},
            )

        status = result.get("status", "unknown")
        mode = result.get("mode", "unknown")

        if status in ("attested_onchain", "requested"):
            tx_hash = result.get("tx_hash", "")
            tx_info = f" (tx: {tx_hash[:16]}…)" if tx_hash else ""
            return (
                f"✅ DON deforestation attestation {'written on-chain' if 'onchain' in status else 'requested'} "
                f"for farm {farm_id}{tx_info}. "
                f"Use 'check DON attestation for {farm_id}' to read the result.",
                result,
            )
        elif status == "attested_offchain":
            att = result.get("attestation", {})
            compliant = att.get("eudrCompliant", False)
            return (
                f"📋 Deforestation check completed for farm {farm_id} "
                f"({'✅ EUDR compliant' if compliant else '❌ Not compliant'}). "
                f"Note: contract not deployed — result not written on-chain.",
                result,
            )
        else:
            error = result.get("error", "Unknown error")
            return (
                f"❌ DON attestation failed for farm {farm_id}: {error}",
                result,
            )

    def _check_don_attestation(
        self, db: Session, args: Dict[str, Any],
        user_id: int = None, user_did: str = None
    ) -> Tuple[str, Dict[str, Any]]:
        """Read a DON-attested deforestation result from the blockchain."""
        farm_id = args.get("farm_id")
        if not farm_id:
            return ("Please specify a farm/farmer ID.", {"error": "no_farm_id"})

        try:
            client = _get_cre_client()
            attestation = client.get_deforestation_attestation(farm_id)
        except Exception as e:
            logger.warning("DON attestation read failed for %s: %s", farm_id, e)
            return (
                f"Could not read DON attestation for '{farm_id}'. "
                "The blockchain may be unavailable.",
                {"error": str(e)},
            )

        if not attestation.exists:
            return (
                f"No DON attestation found for farm {farm_id}. "
                f"Use 'request DON attestation for {farm_id}' to initiate one.",
                {"farm_id": farm_id, "exists": False},
            )

        risk_emoji = {0: "🟢", 1: "🟡", 2: "🔴", 3: "⚪"}.get(
            attestation.risk_level, "⚪"
        )

        return (
            f"🔗 DON Attestation for farm {farm_id}:\n"
            f"• Risk: {risk_emoji} {attestation.risk_label}\n"
            f"• EUDR: {'✅ Compliant' if attestation.eudr_compliant else '❌ Non-compliant'}\n"
            f"• Tree loss: {attestation.tree_loss_hectares:.4f} ha\n"
            f"• Location: ({attestation.latitude:.6f}, {attestation.longitude:.6f})\n"
            f"• Attested: {attestation.timestamp}",
            attestation.to_dict(),
        )

    def _get_don_provenance_metrics(
        self, db: Session, args: Dict[str, Any],
        user_id: int = None, user_did: str = None
    ) -> Tuple[str, Dict[str, Any]]:
        """Read DON-attested provenance metrics from the blockchain."""
        try:
            client = _get_cre_client()
            metrics = client.get_provenance_metrics()
        except Exception as e:
            logger.warning("DON metrics read failed: %s", e)
            return (
                "Could not read DON provenance metrics. "
                "The blockchain may be unavailable.",
                {"error": str(e)},
            )

        if not metrics.exists:
            return (
                "No DON-attested provenance metrics available yet. "
                "The CRE cron trigger writes these every 5 minutes.",
                metrics.to_dict(),
            )

        return (
            f"📊 DON-Attested Supply Chain Metrics:\n"
            f"• Farmers: {metrics.total_farmers}\n"
            f"• Batches: {metrics.total_batches} "
            f"({metrics.verified_batches} verified)\n"
            f"• Total quantity: {metrics.total_quantity_kg:,} kg\n"
            f"• EUDR compliance: {metrics.eudr_compliant_percent}%\n"
            f"• Anchored on-chain: {metrics.batches_anchored}\n"
            f"• Last updated: {metrics.last_updated}",
            metrics.to_dict(),
        )

    # ------------------------------------------------------------------
    # Post-commission CRE orchestration
    # ------------------------------------------------------------------

    def _auto_request_don_attestation(
        self, db: Session, user_id: int, commission_data: Dict[str, Any]
    ):
        """
        Best-effort auto-trigger DON deforestation attestation after commission.

        If the farmer who created the batch has GPS coordinates, we
        automatically fire a CRE deforestation check. This bridges
        Trigger 2 (LogTrigger on EventAnchored, which already fired
        from the commission anchor) with Trigger 3 (HTTP deforestation).

        Non-blocking: any failure is silently logged.
        """
        from database.models import FarmerIdentity, UserIdentity

        # Find the farmer associated with this user
        user = db.query(UserIdentity).filter_by(id=user_id).first()
        if not user or not user.farmer_id:
            return

        farmer = db.query(FarmerIdentity).filter_by(id=user.farmer_id).first()
        if not farmer or not farmer.latitude or not farmer.longitude:
            logger.debug(
                "Skipping CRE auto-attestation — farmer %s has no GPS",
                farmer.farmer_id if farmer else "?",
            )
            return

        farm_id = farmer.farmer_id
        logger.info(
            "Auto-requesting DON attestation for farm %s (post-commission)",
            farm_id,
        )

        try:
            client = _get_cre_client()
            result = client.request_deforestation_attestation(farm_id)
            logger.info(
                "CRE auto-attestation result for %s: %s",
                farm_id, result.get("status"),
            )
        except Exception as e:
            logger.warning(
                "CRE auto-attestation failed for %s (non-fatal): %s",
                farm_id, e,
            )


# Blockchain singleton (avoids re-creating Web3 connection on every call)
_blockchain_anchor = None


def _get_blockchain_anchor():
    """Get or create the BlockchainAnchor singleton."""
    global _blockchain_anchor
    if _blockchain_anchor is None:
        from blockchain.blockchain_anchor import BlockchainAnchor
        _blockchain_anchor = BlockchainAnchor()
    return _blockchain_anchor


# CRE Client singleton
_cre_client = None


def _get_cre_client():
    """Get or create the CREClient singleton."""
    global _cre_client
    if _cre_client is None:
        from chainlink.cre_client import CREClient
        _cre_client = CREClient()
    return _cre_client


# Module-level singleton
_registry: Optional[ToolRegistry] = None


def get_tool_registry() -> ToolRegistry:
    """Get or create the global tool registry."""
    global _registry
    if _registry is None:
        _registry = ToolRegistry()
    return _registry
