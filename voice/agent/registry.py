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
        # Write tools - delegate to command_integration.py handlers
        self._tools["record_commission"] = self._wrap_commission
        self._tools["record_shipment"] = self._wrap_shipment
        self._tools["record_receipt"] = self._wrap_receipt
        self._tools["record_transformation"] = self._wrap_transformation
        self._tools["pack_batches"] = self._wrap_pack
        self._tools["unpack_batches"] = self._wrap_unpack
        self._tools["split_batch"] = self._wrap_split
        
        # Read tools - new capabilities the old pipeline didn't have
        self._tools["query_batches"] = self._query_batches
        self._tools["search_knowledge"] = self._search_knowledge
        
        # Marketplace tools (Agent #3)
        self._tools["create_rfq"] = self._create_rfq
        self._tools["browse_rfqs"] = self._browse_rfqs
        self._tools["submit_offer"] = self._submit_offer
        self._tools["accept_offer"] = self._accept_offer
        self._tools["list_rfq_offers"] = self._list_rfq_offers
        self._tools["list_my_offers"] = self._list_my_offers

        # Container marketplace tools (Agent #3b)
        self._tools["browse_containers"] = self._browse_containers
        self._tools["create_container_offering"] = self._create_container_offering
        self._tools["purchase_container"] = self._purchase_container

        # Container pool tools - shared buying (Agent #3c)
        self._tools["browse_pools"] = self._browse_pools
        self._tools["commit_to_pool"] = self._commit_to_pool
        self._tools["list_my_commitments"] = self._list_my_commitments
        
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

        # Settlement / Payment tools (Agent #9)
        self._tools["confirm_payment"] = self._confirm_payment
        self._tools["check_payment_status"] = self._check_payment_status
        self._tools["record_cooperative_payout"] = self._record_cooperative_payout
        self._tools["confirm_payment_received"] = self._confirm_payment_received
        self._tools["dispute_payment"] = self._dispute_payment
        self._tools["confirm_shipment"] = self._confirm_shipment
        self._tools["confirm_delivery"] = self._confirm_delivery

        # DeFi Financing Pool tools (Agent #10)
        self._tools["check_financing_pool"] = self._check_financing_pool
        self._tools["request_financing_advance"] = self._request_financing_advance
        self._tools["check_trade_financing"] = self._check_trade_financing

    # ------------------------------------------------------------------
    # Helper: Cooperative lookup
    # ------------------------------------------------------------------

    def _get_batch_cooperative(self, batch_id: str, db: Session) -> str:
        """Look up cooperative name from the batch's verifying org or creator's org."""
        try:
            from database.models import CoffeeBatch, UserIdentity, Organization
            batch = db.query(CoffeeBatch).filter_by(batch_id=batch_id).first()
            if not batch:
                return "Unknown Cooperative"
            # 1. Try verifying organization (set by autopilot)
            if batch.verifying_organization_id:
                org = db.query(Organization).filter_by(id=batch.verifying_organization_id).first()
                if org:
                    return org.name
            # 2. Try creator's organization
            if batch.created_by_user_id:
                creator = db.query(UserIdentity).filter_by(id=batch.created_by_user_id).first()
                if creator and creator.organization_id:
                    org = db.query(Organization).filter_by(id=creator.organization_id).first()
                    if org:
                        return org.name
            return "Unknown Cooperative"
        except Exception as e:
            logger.debug("Could not resolve cooperative for %s: %s", batch_id, e)
            return "Unknown Cooperative"

    # ------------------------------------------------------------------
    # Container marketplace tool implementations (Agent #3b)
    # ------------------------------------------------------------------

    def _browse_containers(
        self, db: Session, args: Dict[str, Any],
        user_id: int = None, user_did: str = None
    ) -> Tuple[str, Dict[str, Any]]:
        """Browse available container offerings."""
        from database.models import ContainerOffering, Organization

        query = db.query(ContainerOffering).filter(
            ContainerOffering.status.in_(['AVAILABLE', 'PARTIALLY_SOLD'])
        )

        variety = args.get("variety")
        if variety:
            query = query.filter(ContainerOffering.variety.ilike(f"%{variety}%"))

        min_qty = args.get("min_quantity_kg")
        if min_qty:
            query = query.filter(ContainerOffering.available_quantity_kg >= float(min_qty))

        limit = args.get("limit", 10)
        offerings = query.order_by(ContainerOffering.created_at.desc()).limit(limit).all()

        if not offerings:
            return ("No available containers found.", {"containers": [], "count": 0})

        container_list = []
        for o in offerings:
            coop = db.query(Organization).filter_by(id=o.cooperative_id).first()
            container_list.append({
                "id": o.id,
                "container_sscc": o.container_sscc,
                "cooperative": coop.name if coop else "Unknown",
                "total_quantity_kg": o.total_quantity_kg,
                "available_quantity_kg": o.available_quantity_kg,
                "price_per_kg": o.price_per_kg,
                "currency": o.currency,
                "variety": o.variety,
                "processing_method": o.processing_method,
                "grade": o.grade,
                "status": o.status,
                "delivery_location": o.delivery_location,
                "dpp_url": o.dpp_url,
            })

        msg = f"Found {len(container_list)} available container(s)."
        return (msg, {"containers": container_list, "count": len(container_list)})

    def _create_container_offering(
        self, db: Session, args: Dict[str, Any],
        user_id: int = None, user_did: str = None
    ) -> Tuple[str, Dict[str, Any]]:
        """Create a container offering for fractional sale."""
        from database.models import (
            ContainerOffering, UserIdentity, Organization
        )
        from datetime import datetime, timedelta

        user = db.query(UserIdentity).filter_by(id=user_id).first()
        if not user:
            return ("User not found. Please register first.", {"error": "user_not_found"})
        if user.role not in ("COOPERATIVE_MANAGER", "ADMIN"):
            return (
                f"Only cooperative managers can list containers. Your role is {user.role}.",
                {"error": "role_not_authorized"},
            )

        if not user.organization_id:
            return ("User not associated with an organization.", {"error": "no_organization"})

        # Required fields
        container_sscc = args.get("container_sscc")
        total_quantity_kg = args.get("total_quantity_kg")
        price_per_kg = args.get("price_per_kg")

        if not container_sscc or not total_quantity_kg or not price_per_kg:
            return (
                "Please provide container_sscc (18 digits), total_quantity_kg, and price_per_kg.",
                {"error": "missing_fields"},
            )

        # Validate SSCC length
        if len(str(container_sscc)) != 18:
            return (
                "Container SSCC must be exactly 18 digits.",
                {"error": "invalid_sscc"},
            )

        # Check if container already listed
        existing = db.query(ContainerOffering).filter_by(
            container_sscc=str(container_sscc),
            status='AVAILABLE'
        ).first()

        if existing:
            return (
                f"Container {container_sscc} is already listed.",
                {"error": "already_listed"},
            )

        # Set expiration date (default 90 days)
        expires_days = args.get("expires_days", 90)
        expires_at = datetime.utcnow() + timedelta(days=expires_days)

        # Fetch batch details from aggregation if variety/processing/grade not provided
        variety = args.get("variety")
        processing_method = args.get("processing_method")
        grade = args.get("grade")

        if not variety or not processing_method or not grade:
            from database.models import AggregationRelationship, CoffeeBatch
            agg_rels = db.query(AggregationRelationship).filter_by(
                parent_sscc=str(container_sscc)
            ).all()

            if agg_rels:
                batch = db.query(CoffeeBatch).filter_by(
                    batch_id=agg_rels[0].child_identifier
                ).first()
                if batch:
                    if not variety:
                        variety = batch.variety
                    if not processing_method:
                        processing_method = batch.processing_method
                    if not grade:
                        grade = batch.quality_grade

        # Validate required fields - ask user if missing
        missing_fields = []
        if not variety:
            missing_fields.append("coffee variety")
        if not processing_method:
            missing_fields.append("processing method")
        if not grade:
            missing_fields.append("quality grade")
        if not args.get("delivery_location"):
            missing_fields.append("delivery location")
        if not args.get("description"):
            missing_fields.append("description")

        if missing_fields:
            return (
                f"To create the container offering, please provide: {', '.join(missing_fields)}.",
                None
            )

        # Build offering params
        offering_params = {
            "container_sscc": str(container_sscc),
            "aggregation_id": args.get("aggregation_id"),
            "cooperative_id": user.organization_id,
            "total_quantity_kg": float(total_quantity_kg),
            "available_quantity_kg": float(total_quantity_kg),
            "reserved_quantity_kg": 0,
            "price_per_kg": float(price_per_kg),
            "currency": 'USD',
            "status": 'AVAILABLE',
            "variety": variety,
            "processing_method": processing_method,
            "grade": grade,
            "delivery_location": args.get("delivery_location"),
            "earliest_delivery_date": args.get("earliest_delivery_date"),
            "latest_delivery_date": args.get("latest_delivery_date"),
            "description": args.get("description"),
            "dpp_url": args.get("dpp_url"),
            "expires_at": expires_at
        }

        # Only add certifications/sample_photos if they have actual values
        if args.get("certifications") not in [None, "null", ""]:
            offering_params["certifications"] = args.get("certifications")
        if args.get("sample_photos") not in [None, "null", ""]:
            offering_params["sample_photos"] = args.get("sample_photos")

        # Create offering
        container_offering = ContainerOffering(**offering_params)

        db.add(container_offering)
        db.commit()
        db.refresh(container_offering)

        # Get cooperative name for response
        cooperative = db.query(Organization).filter_by(id=user.organization_id).first()

        return (
            f"Container offering created successfully! SSCC: {container_offering.container_sscc}, "
            f"Quantity: {container_offering.total_quantity_kg}kg, "
            f"Price: ${container_offering.price_per_kg}/kg, "
            f"Total Value: ${container_offering.total_value_usd:,.2f}. "
            f"Expires in {expires_days} days.",
            {
                "id": container_offering.id,
                "container_sscc": container_offering.container_sscc,
                "cooperative_id": container_offering.cooperative_id,
                "cooperative_name": cooperative.name if cooperative else "Unknown",
                "total_quantity_kg": container_offering.total_quantity_kg,
                "available_quantity_kg": container_offering.available_quantity_kg,
                "price_per_kg": container_offering.price_per_kg,
                "currency": container_offering.currency,
                "status": container_offering.status,
                "variety": container_offering.variety,
                "processing_method": container_offering.processing_method,
                "grade": container_offering.grade,
                "delivery_location": container_offering.delivery_location,
                "expires_at": container_offering.expires_at.isoformat() if container_offering.expires_at else None,
                "total_value_usd": container_offering.total_value_usd,
            }
        )

    def _purchase_container(
        self, db: Session, args: Dict[str, Any],
        user_id: int = None, user_did: str = None
    ) -> Tuple[str, Dict[str, Any]]:
        """Purchase a partial quantity from a container offering."""
        from database.models import (
            ContainerOffering, ContainerPool, BuyerCommitment, RFQAcceptance,
            UserIdentity, Organization, Buyer, REGION_PORT_MAP, POOL_AUTO_CONFIRM_PCT,
        )
        from datetime import datetime, timedelta

        print(f"[DEBUG] _purchase_container called: user_id={user_id}, args={args}")

        user = db.query(UserIdentity).filter_by(id=user_id).first()
        if not user:
            return ("User not found. Please register first.", {"error": "user_not_found"})
        if user.role not in ("BUYER", "ADMIN"):
            return (
                f"Only buyers can purchase containers. Your role is {user.role}.",
                {"error": "role_not_buyer"},
            )

        container_id = args.get("container_id")
        quantity_kg = args.get("quantity_kg", 0)
        print(f"[DEBUG] container_id={container_id}, quantity_kg={quantity_kg}")

        if not container_id or quantity_kg <= 0:
            return ("Please specify a container_id and quantity_kg.", {"error": "missing_fields"})

        offering = db.query(ContainerOffering).filter_by(id=int(container_id)).first()
        if not offering:
            return ("Container offering not found.", {"error": "not_found"})
        if offering.status not in ('AVAILABLE', 'PARTIALLY_SOLD'):
            return (f"Container is not available (status: {offering.status}).", {"error": "unavailable"})
        if quantity_kg > offering.available_quantity_kg:
            return (
                f"Insufficient quantity. Available: {offering.available_quantity_kg}kg, requested: {quantity_kg}kg.",
                {"error": "insufficient_qty"},
            )

        total_amount = quantity_kg * offering.price_per_kg
        print(f"[DEBUG] Offering found: SSCC={offering.container_sscc}, available={offering.available_quantity_kg}kg, total_amount=${total_amount}")

        # Resolve destination region
        country = args.get("delivery_country")
        print(f"[DEBUG] delivery_country from args: {country}")
        if not country:
            buyer_profile = db.query(Buyer).filter_by(organization_id=user.organization_id).first()
            print(f"[DEBUG] Buyer profile found: {buyer_profile is not None}")
            if buyer_profile and buyer_profile.country:
                country = buyer_profile.country[:2].upper()
                print(f"[DEBUG] Country from buyer profile: {country}")

        if country and country.upper() in REGION_PORT_MAP:
            port, region = REGION_PORT_MAP[country.upper()]
        else:
            port, region = "Djibouti", "International"
        print(f"[DEBUG] Resolved region: {region}, port: {port}")

        # Get or create pool
        pool = (
            db.query(ContainerPool)
            .filter(
                ContainerPool.container_offering_id == offering.id,
                ContainerPool.destination_region == region,
                ContainerPool.status == "FILLING",
            )
            .first()
        )
        if not pool:
            print(f"[DEBUG] Creating new pool for offering {offering.id}, region {region}")
            pool = ContainerPool(
                container_offering_id=offering.id,
                destination_region=region,
                destination_port=port,
                fill_target_kg=offering.available_quantity_kg,
                filled_kg=0,
                status="FILLING",
                deadline=datetime.utcnow() + timedelta(days=30),
            )
            db.add(pool)
            db.flush()
        else:
            print(f"[DEBUG] Found existing pool: id={pool.id}, filled_kg={pool.filled_kg}, fill_target={pool.fill_target_kg}")

        # Generate acceptance number
        last = db.query(RFQAcceptance).order_by(RFQAcceptance.id.desc()).first()
        next_num = (last.id + 1) if last else 1
        acceptance_number = f"ACC-{next_num:06d}"
        print(f"[DEBUG] Generated acceptance number: {acceptance_number}")

        # Create RFQAcceptance
        acceptance = RFQAcceptance(
            rfq_id=None,
            offer_id=None,
            container_offering_id=int(container_id),
            acceptance_number=acceptance_number,
            quantity_accepted_kg=quantity_kg,
            payment_terms=args.get("payment_terms", "Net 7 days"),
            payment_status="PENDING",
            delivery_status="PENDING",
        )
        db.add(acceptance)
        print(f"[DEBUG] Created RFQAcceptance: id={acceptance.id}, number={acceptance_number}")

        # Create BuyerCommitment linked to the pool
        commitment = BuyerCommitment(
            pool_id=pool.id,
            buyer_id=user.id,
            organization_id=user.organization_id,
            quantity_kg=quantity_kg,
            unit_price=offering.price_per_kg,
            total_amount=total_amount,
            currency=offering.currency or "USD",
            delivery_country=country,
            delivery_city=args.get("delivery_city"),
            status="COMMITTED",
        )
        db.add(commitment)
        print(f"[DEBUG] Created BuyerCommitment: pool_id={pool.id}, quantity_kg={quantity_kg}")

        # Update pool fill
        pool.filled_kg += quantity_kg
        pool.updated_at = datetime.utcnow()
        print(f"[DEBUG] Pool updated: filled_kg={pool.filled_kg}, fill_pct={pool.fill_pct}%")

        # Update offering quantities
        offering.available_quantity_kg -= quantity_kg
        offering.reserved_quantity_kg += quantity_kg
        if offering.available_quantity_kg == 0:
            offering.status = 'FULLY_RESERVED'
        else:
            offering.status = 'PARTIALLY_SOLD'
        offering.updated_at = datetime.utcnow()
        print(f"[DEBUG] Offering updated: available={offering.available_quantity_kg}kg, reserved={offering.reserved_quantity_kg}kg, status={offering.status}")

        # Auto-confirm check (same as _commit_to_pool)
        if pool.fill_pct >= POOL_AUTO_CONFIRM_PCT:
            print(f"[DEBUG] Pool auto-confirm triggered: {pool.fill_pct}% >= {POOL_AUTO_CONFIRM_PCT}%")
            pool.status = "CONFIRMED"
            pool.confirmed_at = datetime.utcnow()
            for c in pool.commitments:
                if c.status == "COMMITTED":
                    c.status = "PAYMENT_PENDING"
                    c.updated_at = datetime.utcnow()
        else:
            print(f"[DEBUG] Pool not confirmed yet: {pool.fill_pct}% < {POOL_AUTO_CONFIRM_PCT}%")

        db.commit()
        db.refresh(acceptance)
        db.refresh(commitment)
        db.refresh(pool)
        print(f"[DEBUG] Committed to database")

        coop = db.query(Organization).filter_by(id=offering.cooperative_id).first()

        status_msg = (
            f"Purchase confirmed! {quantity_kg}kg from container {offering.container_sscc} "
            f"at ${offering.price_per_kg}/kg (total ${total_amount:,.2f}). "
            f"Acceptance #{acceptance_number}. "
            f"Added to {region} pool (shipping via {port}). "
            f"Pool is now {pool.fill_pct}% full."
        )
        if pool.status == "CONFIRMED":
            status_msg += " Pool confirmed for shipment! Payment instructions will follow."

        return (
            status_msg,
            {
                "acceptance_id": acceptance.id,
                "acceptance_number": acceptance_number,
                "commitment_id": commitment.id,
                "pool_id": pool.id,
                "container_sscc": offering.container_sscc,
                "cooperative": coop.name if coop else "Unknown",
                "quantity_kg": quantity_kg,
                "price_per_kg": offering.price_per_kg,
                "total_amount_usd": total_amount,
                "payment_status": "PENDING",
                "destination_region": region,
                "destination_port": port,
                "pool_fill_pct": pool.fill_pct,
                "pool_status": pool.status,
            },
        )

    # ------------------------------------------------------------------
    # Container Pool tool implementations (Agent #3c - shared buying)
    # ------------------------------------------------------------------

    def _browse_pools(
        self, db: Session, args: Dict[str, Any],
        user_id: int = None, user_did: str = None
    ) -> Tuple[str, Dict[str, Any]]:
        """Browse active container pools with fill-progress."""
        from database.models import ContainerPool, ContainerOffering, Organization

        query = db.query(ContainerPool).filter(
            ContainerPool.status.in_(["FILLING", "CONFIRMED"])
        )

        region = args.get("region")
        if region:
            query = query.filter(ContainerPool.destination_region.ilike(f"%{region}%"))

        offering_id = args.get("container_offering_id")
        if offering_id:
            query = query.filter(ContainerPool.container_offering_id == int(offering_id))

        pools = query.order_by(ContainerPool.created_at.desc()).limit(20).all()

        if not pools:
            return ("No active container pools found.", {"pools": [], "count": 0})

        pool_list = []
        for p in pools:
            offering = db.query(ContainerOffering).filter_by(id=p.container_offering_id).first()
            coop = None
            if offering:
                coop = db.query(Organization).filter_by(id=offering.cooperative_id).first()
            pool_list.append({
                "id": p.id,
                "container_sscc": offering.container_sscc if offering else None,
                "cooperative": coop.name if coop else "Unknown",
                "variety": offering.variety if offering else None,
                "grade": offering.grade if offering else None,
                "price_per_kg": offering.price_per_kg if offering else 0,
                "destination_region": p.destination_region,
                "destination_port": p.destination_port,
                "fill_target_kg": p.fill_target_kg,
                "filled_kg": p.filled_kg,
                "fill_pct": p.fill_pct,
                "remaining_kg": p.remaining_kg,
                "buyer_count": p.buyer_count,
                "status": p.status,
                "deadline": p.deadline.isoformat() if p.deadline else None,
            })

        msg = f"Found {len(pool_list)} active pool(s)."
        return (msg, {"pools": pool_list, "count": len(pool_list)})

    def _commit_to_pool(
        self, db: Session, args: Dict[str, Any],
        user_id: int = None, user_did: str = None
    ) -> Tuple[str, Dict[str, Any]]:
        """Commit a fractional quantity to a shared container pool."""
        from database.models import (
            ContainerPool, BuyerCommitment, ContainerOffering,
            UserIdentity, Organization, Buyer, REGION_PORT_MAP,
            POOL_AUTO_CONFIRM_PCT,
        )
        from datetime import datetime, timedelta

        user = db.query(UserIdentity).filter_by(id=user_id).first()
        if not user:
            return ("User not found. Please register first.", {"error": "user_not_found"})
        if user.role not in ("BUYER", "SYSTEM_ADMIN"):
            return (
                f"Only buyers can commit to pools. Your role is {user.role}.",
                {"error": "role_not_buyer"},
            )

        offering_id = args.get("container_offering_id")
        quantity_kg = args.get("quantity_kg", 0)
        if not offering_id or quantity_kg <= 0:
            return ("Please specify container_offering_id and quantity_kg.", {"error": "missing_fields"})

        offering = db.query(ContainerOffering).filter_by(id=int(offering_id)).first()
        if not offering:
            return ("Container offering not found.", {"error": "not_found"})
        if offering.status not in ("AVAILABLE", "PARTIALLY_SOLD"):
            return (f"Container is not available (status: {offering.status}).", {"error": "unavailable"})
        if quantity_kg > offering.available_quantity_kg:
            return (
                f"Insufficient quantity. Available: {offering.available_quantity_kg} kg, "
                f"requested: {quantity_kg} kg.",
                {"error": "insufficient_qty"},
            )

        # Resolve destination
        country = args.get("delivery_country")
        if not country:
            buyer_profile = db.query(Buyer).filter_by(organization_id=user.organization_id).first()
            if buyer_profile and buyer_profile.country:
                country = buyer_profile.country[:2].upper()

        if country and country.upper() in REGION_PORT_MAP:
            port, region = REGION_PORT_MAP[country.upper()]
        else:
            port, region = "Djibouti", "International"

        # Get or create pool
        pool = (
            db.query(ContainerPool)
            .filter(
                ContainerPool.container_offering_id == offering.id,
                ContainerPool.destination_region == region,
                ContainerPool.status == "FILLING",
            )
            .first()
        )
        if not pool:
            pool = ContainerPool(
                container_offering_id=offering.id,
                destination_region=region,
                destination_port=port,
                fill_target_kg=offering.available_quantity_kg,
                filled_kg=0,
                status="FILLING",
                deadline=datetime.utcnow() + timedelta(days=30),
            )
            db.add(pool)
            db.flush()

        # Clamp quantity to pool remaining capacity
        if pool.remaining_kg > 0:
            quantity_kg = min(quantity_kg, pool.remaining_kg)

        total_amount = round(quantity_kg * offering.price_per_kg, 2)

        commitment = BuyerCommitment(
            pool_id=pool.id,
            buyer_id=user.id,
            organization_id=user.organization_id,
            quantity_kg=quantity_kg,
            unit_price=offering.price_per_kg,
            total_amount=total_amount,
            currency=offering.currency or "USD",
            delivery_country=country,
            delivery_city=args.get("delivery_city"),
            delivery_address=args.get("delivery_address"),
            status="COMMITTED",
        )
        db.add(commitment)

        offering.available_quantity_kg -= quantity_kg
        offering.reserved_quantity_kg += quantity_kg
        if offering.available_quantity_kg <= 0:
            offering.status = "FULLY_RESERVED"
        else:
            offering.status = "PARTIALLY_SOLD"
        offering.updated_at = datetime.utcnow()

        # Auto-confirm check
        if pool.fill_pct >= POOL_AUTO_CONFIRM_PCT:
            pool.status = "CONFIRMED"
            pool.confirmed_at = datetime.utcnow()
            for c in pool.commitments:
                if c.status == "COMMITTED":
                    c.status = "PAYMENT_PENDING"
                    c.updated_at = datetime.utcnow()

        db.commit()
        db.refresh(commitment)
        db.refresh(pool)

        coop = db.query(Organization).filter_by(id=offering.cooperative_id).first()

        status_msg = (
            f"Committed {quantity_kg} kg from container {offering.container_sscc} "
            f"to the {region} pool (shipping via {port}) "
            f"at ${offering.price_per_kg}/kg (total ${total_amount:,.2f}). "
            f"Pool is now {pool.fill_pct}% full."
        )
        if pool.status == "CONFIRMED":
            status_msg += " Pool confirmed for shipment! Payment instructions will follow."

        return (
            status_msg,
            {
                "commitment_id": commitment.id,
                "pool_id": pool.id,
                "destination_region": region,
                "destination_port": port,
                "container_sscc": offering.container_sscc,
                "cooperative": coop.name if coop else "Unknown",
                "quantity_kg": quantity_kg,
                "price_per_kg": offering.price_per_kg,
                "total_amount": total_amount,
                "pool_fill_pct": pool.fill_pct,
                "pool_status": pool.status,
            },
        )

    def _list_my_commitments(
        self, db: Session, args: Dict[str, Any],
        user_id: int = None, user_did: str = None
    ) -> Tuple[str, Dict[str, Any]]:
        """List the buyer's own pool commitments."""
        from database.models import ContainerPool, BuyerCommitment, ContainerOffering, Organization

        commitments = (
            db.query(BuyerCommitment)
            .filter(BuyerCommitment.buyer_id == user_id)
            .order_by(BuyerCommitment.created_at.desc())
            .limit(20)
            .all()
        )

        if not commitments:
            return ("You have no pool commitments yet.", {"commitments": [], "count": 0})

        items = []
        for c in commitments:
            pool = db.query(ContainerPool).filter_by(id=c.pool_id).first()
            offering = db.query(ContainerOffering).filter_by(id=pool.container_offering_id).first() if pool else None
            coop = db.query(Organization).filter_by(id=offering.cooperative_id).first() if offering else None
            items.append({
                "commitment_id": c.id,
                "pool_id": c.pool_id,
                "container_sscc": offering.container_sscc if offering else None,
                "cooperative": coop.name if coop else "Unknown",
                "variety": offering.variety if offering else None,
                "quantity_kg": c.quantity_kg,
                "unit_price": c.unit_price,
                "total_amount": c.total_amount,
                "destination_region": pool.destination_region if pool else None,
                "destination_port": pool.destination_port if pool else None,
                "pool_fill_pct": pool.fill_pct if pool else 0,
                "pool_status": pool.status if pool else "UNKNOWN",
                "commitment_status": c.status,
                "delivery_country": c.delivery_country,
                "delivery_city": c.delivery_city,
            })

        msg = f"You have {len(items)} pool commitment(s)."
        return (msg, {"commitments": items, "count": len(items)})
    
    # ------------------------------------------------------------------
    # Settlement / Payment tool implementations (Agent #9)
    # ------------------------------------------------------------------

    def _confirm_payment(
        self, db: Session, args: Dict[str, Any],
        user_id: int = None, user_did: str = None
    ) -> Tuple[str, Dict[str, Any]]:
        """
        Buyer confirms they made a bank transfer for a commitment or
        acceptance.  Records settlement on-chain.
        """
        from database.models import (
            BuyerCommitment, ContainerPool, ContainerOffering,
            RFQAcceptance, RFQOffer, UserIdentity, Organization,
        )
        from datetime import datetime

        commitment_id = args.get("commitment_id")
        acceptance_number = args.get("acceptance_number")
        payment_reference = args.get("payment_reference")

        if commitment_id:
            c = db.query(BuyerCommitment).filter_by(id=int(commitment_id)).first()
            if not c:
                return ("Commitment not found.", {"error": "not_found"})
            if c.buyer_id != user_id:
                return ("This is not your commitment.", {"error": "forbidden"})
            if c.status == "PAID":
                return ("Already paid.", {"error": "already_paid"})

            pool = db.query(ContainerPool).filter_by(id=c.pool_id).first()
            offering = (
                db.query(ContainerOffering)
                .filter_by(id=pool.container_offering_id)
                .first()
                if pool else None
            )
            coop = (
                db.query(Organization).filter_by(id=offering.cooperative_id).first()
                if offering else None
            )

            # On-chain settlement
            settlement_result = None
            if coop and getattr(coop, "wallet_address", None):
                try:
                    from blockchain.settlement_manager import SettlementManager
                    sm = SettlementManager()
                    settlement_result = sm.record_commitment_settlement(
                        commitment_id=c.id,
                        recipient_address=getattr(coop, "wallet_address", None),
                        amount_usd=c.total_amount,
                    )
                    c.settlement_tx_hash = settlement_result["tx_hash"]
                    c.settlement_recorded_at = datetime.utcnow()
                    c.settlement_blockchain_confirmed = settlement_result["confirmed"]
                except Exception as e:
                    logger.error("Blockchain settlement failed: %s", e)

            c.status = "PAID"
            c.payment_method = "BANK_TRANSFER"
            c.payment_confirmed_by_buyer_at = datetime.utcnow()
            c.paid_at = datetime.utcnow()
            if payment_reference:
                c.payment_reference = payment_reference
            c.updated_at = datetime.utcnow()
            db.commit()
            db.refresh(c)

            msg = (
                f"Payment confirmed for commitment #{c.id} "
                f"(${c.total_amount:,.2f})."
            )
            if settlement_result:
                msg += f" Blockchain TX: {settlement_result['tx_hash'][:16]}..."

            # Notify cooperative managers
            try:
                from voice.marketplace.payment_messaging import send_telegram_message
                coop_managers = db.query(UserIdentity).filter_by(
                    organization_id=coop.id, role="COOPERATIVE_MANAGER"
                ).all() if coop else []
                notify_msg = (
                    f"💳 <b>Buyer Confirmed Payment</b>\n\n"
                    f"Commitment: <code>#{c.id}</code>\n"
                    f"Amount: ${c.total_amount:,.2f} USD\n"
                    f"Reference: {payment_reference or 'Via voice agent'}\n"
                    f"Please check your bank account and confirm receipt."
                )
                for mgr in coop_managers:
                    if mgr.telegram_user_id:
                        send_telegram_message(mgr.telegram_user_id, notify_msg, parse_mode="HTML")
            except Exception as e:
                logger.warning("Failed to notify cooperative of commitment payment: %s", e)

            return (msg, {
                "commitment_id": c.id,
                "amount": c.total_amount,
                "status": c.status,
                "settlement_tx": c.settlement_tx_hash,
            })

        elif acceptance_number:
            a = db.query(RFQAcceptance).filter_by(
                acceptance_number=acceptance_number.upper()
            ).first()
            if not a:
                return (f"Acceptance {acceptance_number} not found.", {"error": "not_found"})

            from database.models import RFQ
            rfq = db.query(RFQ).filter_by(id=a.rfq_id).first()
            if rfq and rfq.buyer_id != user_id:
                return ("This is not your acceptance.", {"error": "forbidden"})

            if a.payment_status in ("CONFIRMED_BY_BUYER", "RECEIVED"):
                return ("Payment already confirmed.", {"error": "already_paid"})

            offer = db.query(RFQOffer).filter_by(id=a.offer_id).first()
            coop = (
                db.query(Organization).filter_by(id=offer.cooperative_id).first()
                if offer else None
            )
            total_amount = a.quantity_accepted_kg * offer.price_per_kg if offer else 0

            settlement_result = None
            if coop and getattr(coop, "wallet_address", None):
                try:
                    from blockchain.settlement_manager import SettlementManager
                    sm = SettlementManager()
                    settlement_result = sm.record_settlement(
                        acceptance_id=a.id,
                        recipient_address=getattr(coop, "wallet_address", None),
                        amount_usd=total_amount,
                    )
                    a.settlement_tx_hash = settlement_result["tx_hash"]
                    a.settlement_recorded_at = datetime.utcnow()
                    a.settlement_blockchain_confirmed = settlement_result["confirmed"]
                except Exception as e:
                    logger.error("Blockchain settlement failed: %s", e)

            a.payment_status = "CONFIRMED_BY_BUYER"
            a.payment_method = "BANK_TRANSFER"
            a.payment_confirmed_by_buyer_at = datetime.utcnow()
            if payment_reference:
                a.payment_receipt_url = payment_reference  # text ref
            a.updated_at = datetime.utcnow()
            db.commit()
            db.refresh(a)

            msg = (
                f"Payment confirmed for acceptance {a.acceptance_number} "
                f"(${total_amount:,.2f})."
            )
            if settlement_result:
                msg += f" Blockchain TX: {settlement_result['tx_hash'][:16]}..."

            # Notify cooperative managers
            try:
                from voice.marketplace.payment_messaging import send_telegram_message
                coop_managers = db.query(UserIdentity).filter_by(
                    organization_id=coop.id, role="COOPERATIVE_MANAGER"
                ).all() if coop else []
                notify_msg = (
                    f"💳 <b>Buyer Confirmed Payment</b>\n\n"
                    f"Acceptance: <code>{a.acceptance_number}</code>\n"
                    f"Amount: ${total_amount:,.2f} USD\n"
                    f"Reference: {payment_reference or 'Via voice agent'}\n"
                    f"Please check your bank account and confirm receipt:\n"
                    f"<code>/confirm_receipt {a.acceptance_number}</code>"
                )
                for mgr in coop_managers:
                    if mgr.telegram_user_id:
                        send_telegram_message(mgr.telegram_user_id, notify_msg, parse_mode="HTML")
            except Exception as e:
                logger.warning("Failed to notify cooperative of payment: %s", e)

            return (msg, {
                "acceptance_number": a.acceptance_number,
                "amount": total_amount,
                "payment_status": a.payment_status,
                "settlement_tx": a.settlement_tx_hash,
            })

        return (
            "Please provide a commitment_id or acceptance_number.",
            {"error": "missing_id"},
        )

    def _check_payment_status(
        self, db: Session, args: Dict[str, Any],
        user_id: int = None, user_did: str = None
    ) -> Tuple[str, Dict[str, Any]]:
        """Check payment & blockchain settlement status."""
        from database.models import (
            BuyerCommitment, ContainerPool, ContainerOffering,
            RFQAcceptance, RFQOffer, Organization,
        )

        commitment_id = args.get("commitment_id")
        acceptance_number = args.get("acceptance_number")

        if commitment_id:
            c = db.query(BuyerCommitment).filter_by(id=int(commitment_id)).first()
            if not c:
                return ("Commitment not found.", {"error": "not_found"})
            pool = db.query(ContainerPool).filter_by(id=c.pool_id).first()
            offering = (
                db.query(ContainerOffering)
                .filter_by(id=pool.container_offering_id)
                .first()
                if pool else None
            )
            coop = (
                db.query(Organization).filter_by(id=offering.cooperative_id).first()
                if offering else None
            )
            msg = (
                f"Commitment #{c.id}: {c.quantity_kg} kg, "
                f"${c.total_amount:,.2f}\n"
                f"Payment status: {c.status}\n"
                f"Buyer confirmed: {'Yes' if c.payment_confirmed_by_buyer_at else 'No'}\n"
                f"Coop confirmed: {'Yes' if c.payment_received_by_coop_at else 'No'}\n"
                f"Blockchain TX: {c.settlement_tx_hash or 'Not yet'}\n"
                f"Coop payout TX: {c.coop_payout_tx_hash or 'Not yet'}"
            )
            return (msg, {
                "commitment_id": c.id,
                "quantity_kg": c.quantity_kg,
                "total_amount": c.total_amount,
                "status": c.status,
                "buyer_confirmed": c.payment_confirmed_by_buyer_at is not None,
                "coop_confirmed": c.payment_received_by_coop_at is not None,
                "settlement_tx": c.settlement_tx_hash,
                "coop_payout_tx": c.coop_payout_tx_hash,
                "cooperative": coop.name if coop else None,
            })

        elif acceptance_number:
            a = db.query(RFQAcceptance).filter_by(
                acceptance_number=acceptance_number.upper()
            ).first()
            if not a:
                return (f"Acceptance {acceptance_number} not found.", {"error": "not_found"})
            offer = db.query(RFQOffer).filter_by(id=a.offer_id).first()
            coop = (
                db.query(Organization).filter_by(id=offer.cooperative_id).first()
                if offer else None
            )
            total = a.quantity_accepted_kg * offer.price_per_kg if offer else 0
            msg = (
                f"Acceptance {a.acceptance_number}: {a.quantity_accepted_kg} kg, "
                f"${total:,.2f}\n"
                f"Payment status: {a.payment_status}\n"
                f"Buyer confirmed: {'Yes' if a.payment_confirmed_by_buyer_at else 'No'}\n"
                f"Coop confirmed: {'Yes' if a.payment_received_by_coop_at else 'No'}\n"
                f"Blockchain TX: {a.settlement_tx_hash or 'Not yet'}\n"
                f"Coop payout TX: {a.coop_payout_tx_hash or 'Not yet'}"
            )
            return (msg, {
                "acceptance_number": a.acceptance_number,
                "quantity_kg": a.quantity_accepted_kg,
                "total_amount": total,
                "payment_status": a.payment_status,
                "buyer_confirmed": a.payment_confirmed_by_buyer_at is not None,
                "coop_confirmed": a.payment_received_by_coop_at is not None,
                "settlement_tx": a.settlement_tx_hash,
                "coop_payout_tx": a.coop_payout_tx_hash,
                "cooperative": coop.name if coop else None,
            })

        return (
            "Please provide a commitment_id or acceptance_number.",
            {"error": "missing_id"},
        )

    def _record_cooperative_payout(
        self, db: Session, args: Dict[str, Any],
        user_id: int = None, user_did: str = None
    ) -> Tuple[str, Dict[str, Any]]:
        """
        Admin records that WAGA forwarded funds to the cooperative’s
        Ethiopian bank account. Records the payout on-chain.
        """
        from database.models import (
            BuyerCommitment, ContainerPool, ContainerOffering,
            RFQAcceptance, RFQOffer, UserIdentity, Organization,
        )
        from datetime import datetime

        # Verify admin
        user = db.query(UserIdentity).filter_by(id=user_id).first()
        if not user or user.role not in ("SYSTEM_ADMIN", "ADMIN"):
            return ("Only admins can record cooperative payouts.", {"error": "forbidden"})

        commitment_id = args.get("commitment_id")
        acceptance_number = args.get("acceptance_number")

        if commitment_id:
            record_type = "commitment"
            record = db.query(BuyerCommitment).filter_by(id=int(commitment_id)).first()
            if not record:
                return ("Commitment not found.", {"error": "not_found"})
            pool = db.query(ContainerPool).filter_by(id=record.pool_id).first()
            offering = (
                db.query(ContainerOffering)
                .filter_by(id=pool.container_offering_id)
                .first()
                if pool else None
            )
            coop = (
                db.query(Organization).filter_by(id=offering.cooperative_id).first()
                if offering else None
            )
            amount = record.total_amount
            record_id = record.id

        elif acceptance_number:
            record_type = "acceptance"
            record = db.query(RFQAcceptance).filter_by(
                acceptance_number=acceptance_number.upper()
            ).first()
            if not record:
                return (f"Acceptance {acceptance_number} not found.", {"error": "not_found"})
            offer = db.query(RFQOffer).filter_by(id=record.offer_id).first()
            coop = (
                db.query(Organization).filter_by(id=offer.cooperative_id).first()
                if offer else None
            )
            amount = record.quantity_accepted_kg * offer.price_per_kg if offer else 0
            record_id = record.id
        else:
            return (
                "Please provide a commitment_id or acceptance_number.",
                {"error": "missing_id"},
            )

        if not coop or not getattr(coop, "wallet_address", None):
            return (
                f"Cooperative has no wallet address on file.",
                {"error": "no_wallet"},
            )

        if record.coop_payout_tx_hash:
            return (
                f"Payout already recorded (TX: {record.coop_payout_tx_hash[:16]}...).",
                {"error": "already_recorded"},
            )

        try:
            from blockchain.settlement_manager import SettlementManager
            sm = SettlementManager()
            if record_type == "acceptance":
                result = sm.record_cooperative_payout_for_acceptance(
                    acceptance_id=record_id,
                    recipient_address=getattr(coop, "wallet_address", None),
                    amount_usd=amount,
                )
            else:
                result = sm.record_cooperative_payout_for_commitment(
                    commitment_id=record_id,
                    recipient_address=getattr(coop, "wallet_address", None),
                    amount_usd=amount,
                )
        except Exception as e:
            logger.error("Cooperative payout TX failed: %s", e)
            return (f"Blockchain transaction failed: {e}", {"error": "tx_failed"})

        record.coop_payout_tx_hash = result["tx_hash"]
        record.coop_payout_at = datetime.utcnow()
        record.coop_payout_confirmed = result["confirmed"]
        record.updated_at = datetime.utcnow()
        db.commit()

        msg = (
            f"Cooperative payout recorded for {coop.name}: "
            f"${amount:,.2f}. TX: {result['tx_hash'][:16]}... "
            f"(block {result['block_number']})"
        )
        return (msg, {
            "cooperative": coop.name,
            "amount": amount,
            "tx_hash": result["tx_hash"],
            "block_number": result["block_number"],
            "confirmed": result["confirmed"],
        })

    def _confirm_payment_received(
        self, db: Session, args: Dict[str, Any],
        user_id: int = None, user_did: str = None
    ) -> Tuple[str, Dict[str, Any]]:
        """
        Cooperative confirms they received the buyer's bank transfer.
        Updates acceptance to RECEIVED or commitment receipt timestamp.
        """
        from database.models import (
            BuyerCommitment, ContainerPool, ContainerOffering,
            RFQAcceptance, RFQOffer, UserIdentity, Organization,
        )
        from datetime import datetime

        user = db.query(UserIdentity).filter_by(id=user_id).first()
        if not user:
            return ("User not found.", {"error": "user_not_found"})

        commitment_id = args.get("commitment_id")
        acceptance_number = args.get("acceptance_number")

        if commitment_id:
            c = db.query(BuyerCommitment).filter_by(id=int(commitment_id)).first()
            if not c:
                return ("Commitment not found.", {"error": "not_found"})
            pool = db.query(ContainerPool).filter_by(id=c.pool_id).first()
            offering = (
                db.query(ContainerOffering)
                .filter_by(id=pool.container_offering_id)
                .first()
                if pool else None
            )
            if not offering or user.organization_id != offering.cooperative_id:
                return ("You are not the cooperative for this commitment.", {"error": "forbidden"})
            if c.payment_received_by_coop_at:
                return ("Receipt already confirmed.", {"error": "already_confirmed"})

            c.payment_received_by_coop_at = datetime.utcnow()
            c.updated_at = datetime.utcnow()
            db.commit()

            return (
                f"Receipt confirmed for commitment #{c.id} "
                f"(${c.total_amount:,.2f}). Shipment can proceed.",
                {
                    "commitment_id": c.id,
                    "amount": c.total_amount,
                    "status": c.status,
                    "receipt_confirmed": True,
                },
            )

        elif acceptance_number:
            a = db.query(RFQAcceptance).filter_by(
                acceptance_number=acceptance_number.upper()
            ).first()
            if not a:
                return (f"Acceptance {acceptance_number} not found.", {"error": "not_found"})
            offer = db.query(RFQOffer).filter_by(id=a.offer_id).first()
            if not offer or user.organization_id != offer.cooperative_id:
                return ("You are not the cooperative for this acceptance.", {"error": "forbidden"})
            if a.payment_status == "RECEIVED":
                return ("Receipt already confirmed.", {"error": "already_confirmed"})

            # Guard: buyer must confirm payment first (mirrors payment_handler.py)
            if a.payment_status != "CONFIRMED_BY_BUYER":
                return (
                    f"Cannot confirm receipt yet — buyer has not confirmed payment. "
                    f"Current status: {a.payment_status}. "
                    f"Ask the buyer to confirm with: /confirm_payment {a.acceptance_number}",
                    {"error": "buyer_not_confirmed", "payment_status": a.payment_status},
                )

            a.payment_status = "RECEIVED"
            a.payment_received_by_coop_at = datetime.utcnow()
            a.payment_released_at = datetime.utcnow()
            a.delivery_status = "PREPARING_SHIPMENT"
            a.updated_at = datetime.utcnow()
            db.commit()

            total = a.quantity_accepted_kg * offer.price_per_kg

            # Dispatch webhook to LSPs / customs brokers
            try:
                from voice.service.webhook_dispatcher import dispatch_webhook_sync
                container = getattr(a, 'container_offering', None)
                dispatch_webhook_sync("PREPARING_SHIPMENT", {
                    "acceptance_number": a.acceptance_number,
                    "container_sscc": getattr(container, 'container_sscc', None) if container else None,
                    "total_amount_usd": total,
                    "dpp_url": f"/api/dpp/batch/{a.acceptance_number}",
                })
            except Exception:
                pass  # webhook delivery is best-effort

            # Notify buyer that receipt was confirmed and shipment is being prepared
            try:
                from database.models import RFQ
                from voice.marketplace.payment_messaging import send_telegram_message
                rfq = db.query(RFQ).filter_by(id=a.rfq_id).first()
                buyer = db.query(UserIdentity).filter_by(id=rfq.buyer_id).first() if rfq else None
                if buyer and buyer.telegram_user_id:
                    notify_msg = (
                        f"✅ <b>Payment Received — Shipment Starting!</b>\n\n"
                        f"Acceptance: <code>{a.acceptance_number}</code>\n"
                        f"Amount: ${total:,.2f} USD\n\n"
                        f"The cooperative has confirmed receipt of your payment.\n"
                        f"Your coffee shipment is now being prepared.\n\n"
                        f"Track status: <code>/payment_status {a.acceptance_number}</code>"
                    )
                    send_telegram_message(buyer.telegram_user_id, notify_msg, parse_mode="HTML")
            except Exception as e:
                logger.warning("Failed to notify buyer of receipt confirmation: %s", e)

            return (
                f"Receipt confirmed for acceptance {a.acceptance_number} "
                f"(${total:,.2f}). Delivery status → PREPARING_SHIPMENT.",
                {
                    "acceptance_number": a.acceptance_number,
                    "amount": total,
                    "payment_status": a.payment_status,
                    "delivery_status": a.delivery_status,
                    "receipt_confirmed": True,
                },
            )

        return (
            "Please provide a commitment_id or acceptance_number.",
            {"error": "missing_id"},
        )

    def _dispute_payment(
        self, db: Session, args: Dict[str, Any],
        user_id: int = None, user_did: str = None
    ) -> Tuple[str, Dict[str, Any]]:
        """
        Raise a payment dispute for an RFQ acceptance.
        Mirrors handle_dispute_payment in telegram/payment_handler.py.
        """
        from database.models import RFQAcceptance, UserIdentity
        from datetime import datetime

        acceptance_number = args.get("acceptance_number", "").upper()
        reason = args.get("reason", "").strip()

        if not acceptance_number:
            return ("Please provide an acceptance_number.", {"error": "missing_acceptance"})
        if not reason:
            return ("Please provide a reason for the dispute.", {"error": "missing_reason"})

        a = db.query(RFQAcceptance).filter_by(
            acceptance_number=acceptance_number
        ).first()
        if not a:
            return (f"Acceptance {acceptance_number} not found.", {"error": "not_found"})

        if a.payment_status == "DISPUTED":
            return (
                f"Acceptance {acceptance_number} is already disputed: {a.payment_dispute_reason}",
                {"error": "already_disputed"},
            )

        a.payment_status = "DISPUTED"
        a.payment_dispute_reason = reason
        a.payment_disputed_at = datetime.utcnow()
        db.commit()

        # Notify admins / both parties via Telegram
        try:
            from voice.marketplace.payment_messaging import send_telegram_message
            from database.models import RFQOffer, Organization

            offer = db.query(RFQOffer).filter_by(id=a.offer_id).first()
            coop_managers = db.query(UserIdentity).filter_by(
                organization_id=offer.cooperative_id, role="COOPERATIVE_MANAGER"
            ).all() if offer else []

            from database.models import RFQ
            rfq = db.query(RFQ).filter_by(id=a.rfq_id).first()
            buyer = db.query(UserIdentity).filter_by(id=rfq.buyer_id).first() if rfq else None

            notify_msg = (
                f"⚠️ <b>Payment Dispute Raised</b>\n\n"
                f"Acceptance: <code>{acceptance_number}</code>\n"
                f"Reason: {reason}\n\n"
                f"An administrator will review and contact both parties.\n"
                f"Evidence: receipt={'Yes' if a.payment_receipt_url else 'No'}, "
                f"blockchain={'Yes' if a.settlement_tx_hash else 'No'}"
            )
            for mgr in coop_managers:
                if mgr.telegram_user_id:
                    send_telegram_message(mgr.telegram_user_id, notify_msg, parse_mode="HTML")
            if buyer and buyer.telegram_user_id:
                send_telegram_message(buyer.telegram_user_id, notify_msg, parse_mode="HTML")
        except Exception as e:
            logger.warning("Failed to notify parties of dispute: %s", e)

        return (
            f"⚠️ Dispute raised for acceptance {acceptance_number}: {reason}. "
            f"An administrator will review and contact both parties.",
            {
                "acceptance_number": acceptance_number,
                "payment_status": "DISPUTED",
                "dispute_reason": reason,
            },
        )

    def _confirm_shipment(
        self, db: Session, args: Dict[str, Any],
        user_id: int = None, user_did: str = None
    ) -> Tuple[str, Dict[str, Any]]:
        """
        Cooperative confirms coffee has been shipped.
        PREPARING_SHIPMENT → SHIPPED
        """
        from database.models import RFQAcceptance, RFQOffer, RFQ, UserIdentity
        from datetime import datetime

        acceptance_number = args.get("acceptance_number", "").upper()
        if not acceptance_number:
            return ("Please provide an acceptance_number.", {"error": "missing_acceptance"})

        user = db.query(UserIdentity).filter_by(id=user_id).first()
        if not user:
            return ("User not found.", {"error": "user_not_found"})

        a = db.query(RFQAcceptance).filter_by(acceptance_number=acceptance_number).first()
        if not a:
            return (f"Acceptance {acceptance_number} not found.", {"error": "not_found"})

        offer = db.query(RFQOffer).filter_by(id=a.offer_id).first()
        if not offer or user.organization_id != offer.cooperative_id:
            return ("You are not the cooperative for this acceptance.", {"error": "forbidden"})

        if a.delivery_status == "SHIPPED":
            return (f"Shipment already confirmed for {acceptance_number}.", {"error": "already_shipped"})

        if a.delivery_status != "PREPARING_SHIPMENT":
            return (
                f"Cannot confirm shipment — current status is {a.delivery_status}. "
                f"Payment must be received before shipping.",
                {"error": "invalid_status"},
            )

        a.delivery_status = "SHIPPED"
        a.updated_at = datetime.utcnow()
        db.commit()

        rfq = db.query(RFQ).filter_by(id=a.rfq_id).first()
        total_amount = a.quantity_accepted_kg * offer.price_per_kg

        # Dispatch SHIPPED webhook
        try:
            from voice.service.webhook_dispatcher import dispatch_webhook_sync
            container = getattr(a, "container_offering", None)
            dispatch_webhook_sync("SHIPPED", {
                "acceptance_number": acceptance_number,
                "container_sscc": getattr(container, "container_sscc", None) if container else None,
                "quantity_kg": a.quantity_accepted_kg,
                "delivery_location": rfq.delivery_location if rfq else None,
                "total_amount_usd": total_amount,
                "dpp_url": f"/api/dpp/batch/{acceptance_number}",
            })
        except Exception:
            pass

        # Notify buyer
        try:
            from voice.marketplace.payment_messaging import send_telegram_message
            buyer = db.query(UserIdentity).filter_by(id=rfq.buyer_id).first() if rfq else None
            if buyer and buyer.telegram_user_id:
                send_telegram_message(
                    buyer.telegram_user_id,
                    (
                        f"🚚 <b>Your Coffee Has Been Shipped!</b>\n\n"
                        f"Acceptance: <code>{acceptance_number}</code>\n"
                        f"Quantity: {a.quantity_accepted_kg:,.0f} kg\n"
                        f"Destination: {rfq.delivery_location if rfq else 'N/A'}\n\n"
                        f"Track status: <code>/payment_status {acceptance_number}</code>"
                    ),
                    parse_mode="HTML",
                )
        except Exception as e:
            logger.warning("Failed to notify buyer of shipment: %s", e)

        return (
            f"✅ Shipment confirmed for {acceptance_number} "
            f"({a.quantity_accepted_kg:,.0f} kg to {rfq.delivery_location if rfq else 'N/A'}). "
            f"Buyer notified. Delivery status → SHIPPED.",
            {
                "acceptance_number": acceptance_number,
                "delivery_status": "SHIPPED",
                "quantity_kg": a.quantity_accepted_kg,
                "delivery_location": rfq.delivery_location if rfq else None,
            },
        )

    def _confirm_delivery(
        self, db: Session, args: Dict[str, Any],
        user_id: int = None, user_did: str = None
    ) -> Tuple[str, Dict[str, Any]]:
        """
        Buyer confirms coffee has been delivered.
        SHIPPED → DELIVERED
        """
        from database.models import RFQAcceptance, RFQOffer, RFQ, UserIdentity
        from datetime import datetime

        acceptance_number = args.get("acceptance_number", "").upper()
        if not acceptance_number:
            return ("Please provide an acceptance_number.", {"error": "missing_acceptance"})

        user = db.query(UserIdentity).filter_by(id=user_id).first()
        if not user:
            return ("User not found.", {"error": "user_not_found"})

        a = db.query(RFQAcceptance).filter_by(acceptance_number=acceptance_number).first()
        if not a:
            return (f"Acceptance {acceptance_number} not found.", {"error": "not_found"})

        rfq = db.query(RFQ).filter_by(id=a.rfq_id).first()
        if not rfq or rfq.buyer_id != user_id:
            return ("You are not the buyer for this acceptance.", {"error": "forbidden"})

        if a.delivery_status == "DELIVERED":
            return (f"Delivery already confirmed for {acceptance_number}.", {"error": "already_delivered"})

        if a.delivery_status != "SHIPPED":
            return (
                f"Cannot confirm delivery — current status is {a.delivery_status}. "
                f"Cooperative must confirm shipment first.",
                {"error": "invalid_status"},
            )

        a.delivery_status = "DELIVERED"
        a.delivered_at = datetime.utcnow()
        a.updated_at = datetime.utcnow()
        db.commit()

        offer = db.query(RFQOffer).filter_by(id=a.offer_id).first()
        total_amount = a.quantity_accepted_kg * offer.price_per_kg if offer else 0

        # Dispatch DELIVERED webhook
        try:
            from voice.service.webhook_dispatcher import dispatch_webhook_sync
            container = getattr(a, "container_offering", None)
            dispatch_webhook_sync("DELIVERED", {
                "acceptance_number": acceptance_number,
                "container_sscc": getattr(container, "container_sscc", None) if container else None,
                "quantity_kg": a.quantity_accepted_kg,
                "delivery_location": rfq.delivery_location,
                "total_amount_usd": total_amount,
                "delivered_at": a.delivered_at.isoformat(),
                "dpp_url": f"/api/dpp/batch/{acceptance_number}",
            })
        except Exception:
            pass

        # Notify cooperative managers
        try:
            from voice.marketplace.payment_messaging import send_telegram_message
            if offer:
                coop_managers = db.query(UserIdentity).filter_by(
                    organization_id=offer.cooperative_id, role="COOPERATIVE_MANAGER"
                ).all()
                notify_msg = (
                    f"✅ <b>Coffee Delivery Confirmed by Buyer!</b>\n\n"
                    f"Acceptance: <code>{acceptance_number}</code>\n"
                    f"Quantity: {a.quantity_accepted_kg:,.0f} kg\n"
                    f"Amount: ${total_amount:,.2f} USD\n\n"
                    f"Transaction complete. 🎉"
                )
                for mgr in coop_managers:
                    if mgr.telegram_user_id:
                        send_telegram_message(mgr.telegram_user_id, notify_msg, parse_mode="HTML")
        except Exception as e:
            logger.warning("Failed to notify cooperative of delivery: %s", e)

        return (
            f"✅ Delivery confirmed for {acceptance_number}. "
            f"Cooperative notified. Transaction complete! 🎉",
            {
                "acceptance_number": acceptance_number,
                "delivery_status": "DELIVERED",
                "delivered_at": a.delivered_at.isoformat(),
            },
        )

    # ------------------------------------------------------------------
    # DeFi Financing Pool tool implementations (Agent #10)
    # ------------------------------------------------------------------

    def _check_financing_pool(
        self, db: Session, args: Dict[str, Any],
        user_id: int = None, user_did: str = None
    ) -> Tuple[str, Dict[str, Any]]:
        """Return current financing pool stats."""
        try:
            from blockchain.financing_manager import get_financing_manager
            mgr = get_financing_manager()
            stats = mgr.pool_stats()
            msg = (
                f"Financing pool status:\n"
                f"  Total liquidity: ${stats['total_assets_usdc']:,.2f} USDC\n"
                f"  Currently advanced: ${stats['total_advanced_usdc']:,.2f} USDC\n"
                f"  Available for advances: ${stats['available_for_advance_usdc']:,.2f} USDC\n"
                f"  Utilisation: {stats['utilisation_pct']:.1f}%\n"
                f"  Share price: ${stats['share_price_usdc']:.4f}"
            )
            return (msg, stats)
        except Exception as e:
            logger.error("check_financing_pool failed: %s", e)
            return (
                f"Could not fetch pool stats: {e}",
                {"error": str(e)},
            )

    def _request_financing_advance(
        self, db: Session, args: Dict[str, Any],
        user_id: int = None, user_did: str = None
    ) -> Tuple[str, Dict[str, Any]]:
        """Request a USDC advance against a confirmed trade."""
        from database.models import UserIdentity, RFQAcceptance, RFQOffer

        user = db.query(UserIdentity).filter_by(id=user_id).first()
        if not user or user.role not in ("cooperative", "admin"):
            return ("Only cooperatives can request financing advances.", {"error": "forbidden"})

        acceptance_number = args.get("acceptance_number")
        token_id = args.get("token_id")
        buyer_address = args.get("buyer_address")

        # Look up trade details from acceptance if provided
        if acceptance_number:
            acc = db.query(RFQAcceptance).filter_by(
                acceptance_number=acceptance_number
            ).first()
            if not acc:
                return (
                    f"Acceptance {acceptance_number} not found.",
                    {"error": "not_found"},
                )
            offer = db.query(RFQOffer).filter_by(id=acc.offer_id).first()
            if not offer or user.organization_id != offer.cooperative_id:
                return (
                    "You are not the cooperative for this acceptance.",
                    {"error": "forbidden"},
                )
            if acc.delivery_status not in ("PREPARING_SHIPMENT", "SHIPPED"):
                return (
                    f"Cannot finance acceptance in '{acc.delivery_status}' status. "
                    "Shipment must be confirmed first.",
                    {"error": "invalid_status"},
                )

            agreed_price = acc.quantity_accepted_kg * offer.price_per_kg
            token_id = token_id or getattr(acc, "container_token_id", None)
            if not token_id:
                return (
                    "No container token ID found for this acceptance. "
                    "The container must be tokenised before requesting an advance.",
                    {"error": "no_token"},
                )
        elif not token_id:
            return (
                "Please provide an acceptance_number or token_id.",
                {"error": "missing_id"},
            )
        else:
            agreed_price = None

        try:
            from blockchain.financing_manager import get_financing_manager
            mgr = get_financing_manager()

            # Check available liquidity first
            stats = mgr.pool_stats()
            advance_estimate = (agreed_price * 0.80) if agreed_price else None
            if advance_estimate and advance_estimate > stats["available_for_advance_usdc"]:
                return (
                    f"Insufficient pool liquidity. Available: "
                    f"${stats['available_for_advance_usdc']:,.2f}, "
                    f"estimated advance (80%): ${advance_estimate:,.2f}.",
                    {"error": "insufficient_liquidity", **stats},
                )

            tx_hash = mgr.request_advance(
                token_id=token_id,
                token_amount=1,
                buyer=buyer_address or "0x0000000000000000000000000000000000000000",
                agreed_price_usdc=agreed_price or 0,
                shipment_hash="0x" + "00" * 32,
                farm_id=user_did or "",
            )
            if tx_hash:
                return (
                    f"Advance approved! USDC disbursed to your wallet.\n"
                    f"  Trade amount: ${agreed_price:,.2f}\n"
                    f"  Estimated advance (80%): ${advance_estimate:,.2f}\n"
                    f"  TX: {tx_hash}"
                    if agreed_price else
                    f"Advance approved! TX: {tx_hash}",
                    {
                        "tx_hash": tx_hash,
                        "token_id": token_id,
                        "agreed_price_usdc": agreed_price,
                        "advance_estimate_usdc": advance_estimate,
                        "acceptance_number": acceptance_number,
                    },
                )
            return (
                "Advance request failed. Check that the container token is "
                "approved to the escrow contract.",
                {"error": "tx_failed"},
            )
        except Exception as e:
            logger.error("request_financing_advance failed: %s", e)
            return (
                f"Financing advance failed: {e}",
                {"error": str(e)},
            )

    def _check_trade_financing(
        self, db: Session, args: Dict[str, Any],
        user_id: int = None, user_did: str = None
    ) -> Tuple[str, Dict[str, Any]]:
        """Check status of a financed trade."""
        trade_id = args.get("trade_id")
        acceptance_number = args.get("acceptance_number")

        if not trade_id and not acceptance_number:
            return (
                "Please provide a trade_id or acceptance_number.",
                {"error": "missing_id"},
            )

        try:
            from blockchain.financing_manager import get_financing_manager
            mgr = get_financing_manager()

            if trade_id:
                trade = mgr.get_trade(trade_id)
                if not trade:
                    return (f"Trade {trade_id} not found.", {"error": "not_found"})
            else:
                # Try sequential trade IDs to find matching acceptance
                # (In production, we'd store the mapping in the DB)
                trade = None
                for tid in range(1, 100):
                    t = mgr.get_trade(tid)
                    if not t:
                        break
                    if t.get("farm_id") and acceptance_number in str(t.get("farm_id", "")):
                        trade = t
                        break
                if not trade:
                    return (
                        f"No financed trade found for acceptance {acceptance_number}.",
                        {"error": "not_found"},
                    )

            status_emoji = {
                "Active": "🟡",
                "Settled": "✅",
                "Defaulted": "❌",
            }

            status = trade.get("status", "Unknown")
            emoji = status_emoji.get(status, "❓")
            
            msg = (
                f"{emoji} Trade #{trade_id} Status: {status}\n"
                f"  Advance amount: ${trade.get('advance_amount', 0):,.2f}\n"
                f"  Remaining balance: ${trade.get('remaining_amount', 0):,.2f}\n"
                f"  Deadline: {trade.get('deadline', 'N/A')}"
            )
            return (msg, trade)

        except Exception as e:
            logger.error("check_trade_financing failed: %s", e)
            return (
                f"Could not fetch trade status: {e}",
                {"error": str(e)},
            )

    def _confirm_trade_delivery(
        self, db: Session, args: Dict[str, Any],
        user_id: int = None, user_did: str = None
    ) -> Tuple[str, Dict[str, Any]]:
        """Buyer confirms coffee delivery and releases payment."""
        from database.models import UserIdentity, RFQAcceptance, RFQOffer

        user = db.query(UserIdentity).filter_by(id=user_id).first()
        if not user or user.role not in ("buyer", "admin"):
            return ("Only buyers can confirm delivery.", {"error": "forbidden"})

        trade_id = args.get("trade_id")
        acceptance_number = args.get("acceptance_number")

        # Look up trade details from acceptance if provided
        if acceptance_number:
            acc = db.query(RFQAcceptance).filter_by(
                acceptance_number=acceptance_number
            ).first()
            if not acc:
                return (
                    f"Acceptance {acceptance_number} not found.",
                    {"error": "not_found"},
                )
            offer = db.query(RFQOffer).filter_by(id=acc.offer_id).first()
            if not offer or user.organization_id != offer.buyer_id:
                return (
                    "You are not the buyer for this acceptance.",
                    {"error": "forbidden"},
                )
        elif not trade_id:
            return (
                "Please provide a trade_id or acceptance_number.",
                {"error": "missing_id"},
            )
        else:
            acc = None

        try:
            from blockchain.financing_manager import get_financing_manager
            mgr = get_financing_manager()

            # Find the trade ID if we have acceptance
            if acceptance_number and acc:
                # Try sequential trade IDs to find matching acceptance
                trade = None
                for tid in range(1, 100):
                    t = mgr.get_trade(tid)
                    if not t:
                        break
                    if t.get("farm_id") and acceptance_number in str(t.get("farm_id", "")):
                        trade = t
                        trade_id = tid
                        break
                if not trade:
                    return (
                        f"No financed trade found for acceptance {acceptance_number}.",
                        {"error": "not_found"},
                    )
            else:
                trade = mgr.get_trade(trade_id)
                if not trade:
                    return (f"Trade {trade_id} not found.", {"error": "not_found"})

            # Confirm delivery on blockchain
            tx_hash = mgr.confirm_delivery(trade_id)
            if tx_hash:
                # Update acceptance status in database
                if acc:
                    acc.delivery_status = "DELIVERED"
                    db.commit()

                return (
                    f"✅ Delivery confirmed! Payment released to cooperative.\n"
                    f"  Trade ID: {trade_id}\n"
                    f"  TX: {tx_hash}\n"
                    f"  Remaining 20% + fees have been distributed.",
                    {
                        "tx_hash": tx_hash,
                        "trade_id": trade_id,
                        "acceptance_number": acceptance_number,
                    },
                )
            else:
                return (
                    "Delivery confirmation failed. Check trade status and try again.",
                    {"error": "tx_failed"},
                )
        except Exception as e:
            logger.error("confirm_trade_delivery failed: %s", e)
            return (
                f"Delivery confirmation failed: {e}",
                {"error": str(e)},
            )

    def _cancel_trade(
        self, db: Session, args: Dict[str, Any],
        user_id: int = None, user_did: str = None
    ) -> Tuple[str, Dict[str, Any]]:
        """Cancel a pending or active financed trade."""
        from database.models import UserIdentity, RFQAcceptance, RFQOffer

        user = db.query(UserIdentity).filter_by(id=user_id).first()
        if not user or user.role not in ("cooperative", "admin"):
            return ("Only cooperatives can cancel trades.", {"error": "forbidden"})

        trade_id = args.get("trade_id")
        acceptance_number = args.get("acceptance_number")

        # Look up trade details from acceptance if provided
        if acceptance_number:
            acc = db.query(RFQAcceptance).filter_by(
                acceptance_number=acceptance_number
            ).first()
            if not acc:
                return (
                    f"Acceptance {acceptance_number} not found.",
                    {"error": "not_found"},
                )
            offer = db.query(RFQOffer).filter_by(id=acc.offer_id).first()
            if not offer or user.organization_id != offer.cooperative_id:
                return (
                    "You are not the cooperative for this acceptance.",
                    {"error": "forbidden"},
                )
        elif not trade_id:
            return (
                "Please provide a trade_id or acceptance_number.",
                {"error": "missing_id"},
            )
        else:
            acc = None

        try:
            from blockchain.financing_manager import get_financing_manager
            mgr = get_financing_manager()

            # Find the trade ID if we have acceptance
            if acceptance_number and acc:
                # Try sequential trade IDs to find matching acceptance
                trade = None
                for tid in range(1, 100):
                    t = mgr.get_trade(tid)
                    if not t:
                        break
                    if t.get("farm_id") and acceptance_number in str(t.get("farm_id", "")):
                        trade = t
                        trade_id = tid
                        break
                if not trade:
                    return (
                        f"No financed trade found for acceptance {acceptance_number}.",
                        {"error": "not_found"},
                    )
            else:
                trade = mgr.get_trade(trade_id)
                if not trade:
                    return (f"Trade {trade_id} not found.", {"error": "not_found"})

            # Cancel trade on blockchain
            tx_hash = mgr.cancel_trade(trade_id)
            if tx_hash:
                # Update acceptance status in database
                if acc:
                    acc.delivery_status = "CANCELLED"
                    db.commit()

                return (
                    f"Trade #{trade_id} cancelled successfully.\n"
                    f"  TX: {tx_hash}\n"
                    f"  Collateral has been returned to your wallet.\n"
                    f"  Pool liquidity has been restored.",
                    {
                        "tx_hash": tx_hash,
                        "trade_id": trade_id,
                        "acceptance_number": acceptance_number,
                    },
                )
            else:
                return (
                    "Trade cancellation failed. Check trade status and try again.",
                    {"error": "tx_failed"},
                )
        except Exception as e:
            logger.error("cancel_trade failed: %s", e)
            return (
                f"Trade cancellation failed: {e}",
                {"error": str(e)},
            )

    def _mark_default(
        self, db: Session, args: Dict[str, Any],
        user_id: int = None, user_did: str = None
    ) -> Tuple[str, Dict[str, Any]]:
        """Mark a financed trade as defaulted."""
        from database.models import UserIdentity, RFQAcceptance, RFQOffer

        user = db.query(UserIdentity).filter_by(id=user_id).first()
        if not user or user.role not in ("cooperative", "admin"):
            return ("Only cooperatives or admins can mark trades as defaulted.", {"error": "forbidden"})

        trade_id = args.get("trade_id")
        acceptance_number = args.get("acceptance_number")

        # Look up trade details from acceptance if provided
        if acceptance_number:
            acc = db.query(RFQAcceptance).filter_by(
                acceptance_number=acceptance_number
            ).first()
            if not acc:
                return (
                    f"Acceptance {acceptance_number} not found.",
                    {"error": "not_found"},
                )
            offer = db.query(RFQOffer).filter_by(id=acc.offer_id).first()
            if not offer or user.organization_id != offer.cooperative_id:
                return (
                    "You are not the cooperative for this acceptance.",
                    {"error": "forbidden"},
                )
        elif not trade_id:
            return (
                "Please provide a trade_id or acceptance_number.",
                {"error": "missing_id"},
            )
        else:
            acc = None

        try:
            from blockchain.financing_manager import get_financing_manager
            mgr = get_financing_manager()

            # Find the trade ID if we have acceptance
            if acceptance_number and acc:
                # Try sequential trade IDs to find matching acceptance
                trade = None
                for tid in range(1, 100):
                    t = mgr.get_trade(tid)
                    if not t:
                        break
                    if t.get("farm_id") and acceptance_number in str(t.get("farm_id", "")):
                        trade = t
                        trade_id = tid
                        break
                if not trade:
                    return (
                        f"No financed trade found for acceptance {acceptance_number}.",
                        {"error": "not_found"},
                    )
            else:
                trade = mgr.get_trade(trade_id)
                if not trade:
                    return (f"Trade {trade_id} not found.", {"error": "not_found"})

            # Mark trade as defaulted on blockchain
            tx_hash = mgr.mark_default(trade_id)
            if tx_hash:
                # Update acceptance status in database
                if acc:
                    acc.delivery_status = "DEFAULTED"
                    db.commit()

                return (
                    f"Trade #{trade_id} marked as defaulted.\n"
                    f"  TX: {tx_hash}\n"
                    f"  Collateral is being liquidated.\n"
                    f"  Proceeds will be distributed to pool investors.",
                    {
                        "tx_hash": tx_hash,
                        "trade_id": trade_id,
                        "acceptance_number": acceptance_number,
                    },
                )
            else:
                return (
                    "Failed to mark trade as defaulted. Check trade status and try again.",
                    {"error": "tx_failed"},
                )
        except Exception as e:
            logger.error("mark_default failed: %s", e)
            return (
                f"Failed to mark trade as defaulted: {e}",
                {"error": str(e)},
            )

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
        # deforestation attestation. Best-effort - never blocks commission.
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
    # Read tool implementations (new - not in old pipeline)
    # ------------------------------------------------------------------
    
    def _query_batches(
        self, db: Session, args: Dict[str, Any],
        user_id: int = None, user_did: str = None
    ) -> Tuple[str, Dict[str, Any]]:
        """
        Query coffee batches from the database.
        Delegates to services.batch_service for shared business logic.
        """
        from services.batch_service import query_batches as svc_query_batches

        # For general batch queries (no specific batch_id), show all batches
        # For specific batch lookups, apply user filter
        show_all = not args.get("batch_id")
        result = svc_query_batches(
            db,
            batch_id=args.get("batch_id"),
            status=args.get("status"),
            origin=args.get("origin"),
            user_id=user_id,
            limit=args.get("limit", 10),
            show_all=show_all,
        )

        if result["single"] and result["found"]:
            return (f"Found batch {result['batch']['batch_id']}", result["batch"])
        if result["single"] and not result["found"]:
            return (f"Batch '{result.get('query_batch_id', args.get('batch_id'))}' not found", {"found": False})
        if result["count"] > 0:
            return (f"Found {result['count']} batch(es)", {"batches": result["batches"], "count": result["count"]})
        return ("No batches found matching your criteria", {"batches": [], "count": 0})
    
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
            # Load environment variables
            from dotenv import load_dotenv
            load_dotenv()
            
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
            # Return a helpful response instead of error
            return (
                f"I couldn't search the knowledge base for '{query_text}'. "
                f"However, I can help you based on my training. "
                f"For specific documentation, please check the Voice Ledger guides "
                f"or contact support if the knowledge base should be available.",
                {"error": str(e), "fallback": True},
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
        from sqlalchemy import func
        max_result = db.query(func.max(RFQ.rfq_number)).filter(RFQ.rfq_number.like('RFQ-%')).scalar()
        
        if max_result:
            # Extract numeric part and increment
            try:
                current_num = int(max_result.split('-')[1])
                next_num = current_num + 1
            except (ValueError, IndexError):
                next_num = 1
        else:
            next_num = 1
        
        rfq_number = f"RFQ-{next_num:06d}"

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

        # Support filtering by RFQ ID or RFQ number
        rfq_id = args.get("rfq_id")
        rfq_number = args.get("rfq_number")
        if rfq_id:
            query = query.filter(RFQ.id == int(rfq_id))
        elif rfq_number:
            query = query.filter(RFQ.rfq_number == rfq_number.upper())

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
        if rfq.status not in ("OPEN", "PARTIALLY_FILLED"):
            return (f"RFQ {rfq.rfq_number} is {rfq.status}, not open for offers.", {"error": "rfq_not_open"})

        quantity = args.get("quantity_offered_kg", 0)
        price = args.get("price_per_kg", 0)
        if quantity <= 0 or price <= 0:
            return ("Quantity and price must be greater than zero.", {"error": "invalid_values"})

        # Check offered quantity does not exceed remaining unfulfilled quantity
        from sqlalchemy import func as sqlfunc
        from database.models import RFQAcceptance
        accepted_kg = db.query(
            sqlfunc.coalesce(sqlfunc.sum(RFQAcceptance.quantity_accepted_kg), 0)
        ).filter_by(rfq_id=rfq.id).scalar() or 0
        remaining_kg = rfq.quantity_kg - accepted_kg
        if quantity > remaining_kg:
            return (
                f"Offered quantity ({quantity} kg) exceeds the remaining unfulfilled "
                f"quantity for {rfq.rfq_number} ({remaining_kg:.0f} kg).",
                {"error": "exceeds_remaining", "remaining_kg": remaining_kg},
            )

        # Generate unique offer number — use MAX(id)+1 to avoid string-sort issues
        from sqlalchemy import func
        from sqlalchemy.exc import IntegrityError

        offer_number = None
        for attempt in range(10):
            try:
                with db.no_autoflush:
                    max_id = db.query(func.max(RFQOffer.id)).scalar() or 0

                next_num = max_id + 1 + attempt
                offer_number = f"OFF-{next_num:06d}"

                # Check it's not already taken before attempting insert
                exists = db.query(RFQOffer.id).filter_by(
                    offer_number=offer_number
                ).first()
                if exists:
                    continue

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
                db.flush()  # Raises IntegrityError if duplicate
                break  # Success!

            except IntegrityError:
                db.rollback()
                continue  # Try next number
        else:
            return (
                "Failed to generate a unique offer number. Please try again.",
                {"error": "offer_number_conflict"},
            )

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

    def _list_rfq_offers(
        self, db: Session, args: Dict[str, Any],
        user_id: int = None, user_did: str = None
    ) -> Tuple[str, Dict[str, Any]]:
        """List offers for a buyer's RFQ (buyers only)."""
        from database.models import RFQ, RFQOffer, UserIdentity, Organization

        user = db.query(UserIdentity).filter_by(id=user_id).first()
        if not user:
            return ("User not found. Please register first.", {"error": "user_not_found"})
        
        # 2. CHECK ROLE - only buyers can view offers on their RFQs
        if user.role not in ("BUYER", "ADMIN"):
            return (
                f"Only buyers can view RFQ offers. Your role is {user.role}.",
                {"error": "role_not_buyer"},
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
            return ("RFQ not found.", {"error": "rfq_not_found"})
          
        # Verify user owns this RFQ
        if rfq.buyer_id != user.id and user.role != "ADMIN":
            return ("You can only view offers on your own RFQs.", {"error": "not_owner"})

        # Get offers
        offers = db.query(RFQOffer).filter_by(rfq_id=rfq.id).order_by(
            RFQOffer.created_at.desc()
        ).all()

        if not offers:
            return (
                f"No offers yet for RFQ {rfq.rfq_number}. "
                f"Cooperatives have not submitted any offers.",
                {"rfq_id": rfq.id, "rfq_number": rfq.rfq_number, "offers": [], "count": 0}
            )

        offer_list = []
        for offer in offers:
            coop_org = db.query(Organization).filter_by(id=offer.cooperative_id).first()
            offer_list.append({
                "id": offer.id,
                "offer_number": offer.offer_number,
                "rfq_id": offer.rfq_id,
                "rfq_number": rfq.rfq_number,
                "cooperative_id": offer.cooperative_id,
                "cooperative_name": coop_org.name if coop_org else "Unknown",
                "quantity_offered_kg": offer.quantity_offered_kg,
                "price_per_kg": offer.price_per_kg,
                "total_value_usd": offer.quantity_offered_kg * offer.price_per_kg if offer.price_per_kg else 0,
                "delivery_timeline": offer.delivery_timeline,
                "status": offer.status,
                "created_at": offer.created_at.isoformat() if offer.created_at else None,
            })

        msg = (
            f"📋 **Offers for RFQ {rfq.rfq_number}** ({len(offer_list)} total)\n\n"
            f"Quantity requested: {rfq.quantity_kg} kg\n"
            f"Variety: {rfq.variety or 'Any'}\n\n"
        )

        for i, offer in enumerate(offer_list, 1):
            msg += (
                f"**Offer {i}: {offer['offer_number']}**\n"
                f"  Cooperative: {offer['cooperative_name']}\n"
                f"  Quantity: {offer['quantity_offered_kg']} kg\n"
                f"  Price: ${offer['price_per_kg']}/kg\n"
                f"  Total Value: ${offer['total_value_usd']:,.2f}\n"
                f"  Delivery: {offer['delivery_timeline'] or 'TBD'}\n"
                f"  Status: {offer['status']}\n\n"
            )

        return (
            msg,
            {
                "rfq_id": rfq.id,
                "rfq_number": rfq.rfq_number,
                "quantity_requested_kg": rfq.quantity_kg,
                "variety": rfq.variety,
                "offers": offer_list,
                "count": len(offer_list),
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

        offer_number = args.get("offer_number")

        offer = db.query(RFQOffer).filter_by(offer_number=offer_number).first()
        if not offer:
            return ("Offer not found.", {"error": "offer_not_found"})

        # Get RFQ from the offer
        rfq = db.query(RFQ).filter_by(id=offer.rfq_id).first()
        if not rfq:
            return ("RFQ not found.", {"error": "rfq_not_found"})
        if rfq.buyer_id != user.id and user.role != "ADMIN":
            return ("You can only accept offers on your own RFQs.", {"error": "not_owner"})
        if offer.status != "PENDING":
            return (f"Offer is {offer.status}, cannot accept.", {"error": "offer_not_pending"})

        quantity_accepted = args.get("quantity_accepted_kg") or offer.quantity_offered_kg
        if quantity_accepted > offer.quantity_offered_kg:
            return (
                f"Cannot accept more than offered ({offer.quantity_offered_kg} kg).",
                {"error": "exceeds_offered"},
            )

        # Generate unique acceptance number with retry loop to handle race conditions
        from sqlalchemy import func
        from sqlalchemy.exc import IntegrityError

        acceptance_number = None
        for attempt in range(5):
            try:
                # Disable autoflush during query to avoid race conditions
                with db.no_autoflush:
                    max_result = db.query(func.max(RFQAcceptance.acceptance_number)).filter(
                        RFQAcceptance.acceptance_number.like('ACC-%')
                    ).scalar()

                if max_result:
                    try:
                        current_num = int(max_result.split('-')[1])
                        next_num = current_num + 1 + attempt
                    except (ValueError, IndexError):
                        next_num = 1 + attempt
                else:
                    next_num = 1 + attempt

                acceptance_number = f"ACC-{next_num:06d}"

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
                db.flush()  # This will raise IntegrityError if duplicate
                break  # Success!

            except IntegrityError:
                db.rollback()
                if attempt < 4:
                    continue  # Retry with next number
                else:
                    return (
                        "Failed to generate unique acceptance number after multiple attempts.",
                        {"error": "acceptance_number_conflict"},
                    )

        offer.status = "ACCEPTED"

        # Update RFQ status
        if quantity_accepted >= rfq.quantity_kg:
            rfq.status = "FULFILLED"
        else:
            rfq.status = "PARTIALLY_FILLED"

        db.flush()  # Ensure acceptance gets an ID (get_db context auto-commits)

        coop_org = db.query(Organization).filter_by(id=offer.cooperative_id).first()

        # Send payment instructions to buyer and cooperative.
        # Calls the synchronous Telegram helper directly — no async needed
        # since send_telegram_message uses requests (blocking HTTP).
        try:
            from voice.marketplace.payment_messaging import send_telegram_message
            total_amount = quantity_accepted * offer.price_per_kg

            # Build buyer org for message context
            buyer_org = db.query(Organization).filter_by(
                id=user.organization_id
            ).first() if user.organization_id else None

            bank_name = getattr(coop_org, 'bank_name', None) if coop_org else None
            if bank_name:
                bank_details = (
                    f"<b>Bank Details:</b>\n"
                    f"Bank: {bank_name}\n"
                    f"Account #: <code>{getattr(coop_org, 'bank_account_number', 'N/A')}</code>\n"
                    f"Account Name: {getattr(coop_org, 'bank_account_name', coop_org.name if coop_org else 'N/A')}\n"
                    f"Reference: <b>{acceptance_number}</b>\n"
                )
            else:
                bank_details = (
                    f"⚠️ <b>Bank details not on file</b>\n"
                    f"Contact cooperative directly:\n"
                    f"Phone: {getattr(coop_org, 'phone_number', 'N/A') if coop_org else 'N/A'}\n"
                )

            buyer_msg = (
                f"✅ <b>Offer Accepted Successfully!</b>\n\n"
                f"📋 <b>Transaction Details</b>\n"
                f"Acceptance #: <code>{acceptance_number}</code>\n"
                f"Cooperative: <b>{coop_org.name if coop_org else 'N/A'}</b>\n\n"
                f"📦 <b>Order Details</b>\n"
                f"Quantity: {quantity_accepted:,.0f} kg\n"
                f"Price per kg: ${offer.price_per_kg:.2f}\n"
                f"<b>Total Amount: ${total_amount:,.2f} USD</b>\n"
                f"Payment Terms: {acceptance.payment_terms or 'Standard'}\n\n"
                f"💰 <b>PAYMENT INSTRUCTIONS</b>\n\n"
                f"{bank_details}\n"
                f"⚠️ <b>IMPORTANT:</b>\n"
                f"• Include reference number: <code>{acceptance_number}</code>\n"
                f"• Payment expected within 5 business days\n\n"
                f"1️⃣ Transfer ${total_amount:,.2f} to cooperative's bank account\n"
                f"2️⃣ After payment, send: <code>/confirm_payment {acceptance_number}</code> with receipt photo\n"
                f"3️⃣ Cooperative will verify and confirm receipt\n"
                f"4️⃣ Coffee shipment begins to {rfq.delivery_location}\n\n"
                f"💡 Track: <code>/payment_status {acceptance_number}</code>"
            )
            if user.telegram_user_id:
                send_telegram_message(user.telegram_user_id, buyer_msg, parse_mode='HTML')

            # Notify cooperative managers
            coop_managers = db.query(UserIdentity).filter_by(
                organization_id=offer.cooperative_id, role='COOPERATIVE_MANAGER'
            ).all() if offer.cooperative_id else []
            buyer_name = buyer_org.name if buyer_org else (
                f"{user.telegram_first_name or ''} {user.telegram_last_name or ''}".strip()
            )
            coop_msg = (
                f"🎉 <b>Your Offer Has Been Accepted!</b>\n\n"
                f"📋 <b>Transaction Details</b>\n"
                f"Acceptance #: <code>{acceptance_number}</code>\n"
                f"Buyer: <b>{buyer_name}</b>\n\n"
                f"📦 <b>Order Details</b>\n"
                f"Quantity: {quantity_accepted:,.0f} kg\n"
                f"Price per kg: ${offer.price_per_kg:.2f}\n"
                f"<b>Total Amount: ${total_amount:,.2f} USD</b>\n"
                f"Delivery to: {rfq.delivery_location}\n\n"
                f"⏳ Awaiting buyer bank transfer.\n"
                f"5️⃣ Confirm receipt: <code>/confirm_receipt {acceptance_number}</code>\n\n"
                f"💡 Track: <code>/payment_status {acceptance_number}</code>"
            )
            for mgr in coop_managers:
                if mgr.telegram_user_id:
                    send_telegram_message(mgr.telegram_user_id, coop_msg, parse_mode='HTML')

        except Exception as e:
            print(f"Warning: Failed to send payment instructions: {e}")

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
        from database.models import CoffeeBatch

        batch_ids = args.get("batch_ids", [])
        if not batch_ids:
            return ("No batch IDs provided. Please specify which batches to check.", {"error": "no_batch_ids"})

        is_valid, error_msg = validate_eudr_compliance(batch_ids, db)

        # Build per-batch details for the frontend
        batch_results = []
        all_gps = True
        all_deforestation = True
        all_photo_verified = True
        batches = db.query(CoffeeBatch).filter(
            CoffeeBatch.batch_id.in_(batch_ids)
        ).all()
        for b in batches:
            farmer = b.farmer
            has_gps = bool(farmer and farmer.latitude is not None and farmer.longitude is not None)
            photo_verified = bool(farmer and farmer.photo_latitude is not None and farmer.gps_verified_at is not None)
            deforestation_ok = bool(farmer and farmer.deforestation_compliant is True)
            risk = farmer.deforestation_risk if farmer else None

            if not has_gps:
                all_gps = False
            if not photo_verified:
                all_photo_verified = False
            if not deforestation_ok:
                all_deforestation = False

            batch_results.append({
                "batch_id": b.batch_id,
                "has_gps": has_gps,
                "photo_verified": photo_verified,
                "deforestation_risk": risk,
                "compliant": has_gps and deforestation_ok,
            })

        # Individual check flags (for the checks checklist)
        checks = {
            "gps_coordinates": all_gps,
            "photo_verification": all_photo_verified,
            "deforestation_clear": all_deforestation,
        }

        data = {
            "compliant": is_valid,
            "checks": checks,
            "batch_count": len(batch_ids),
            "batch_ids": batch_ids,
            "batch_results": batch_results,
        }

        if is_valid:
            return (
                f"All {len(batch_ids)} batch(es) are EUDR compliant. "
                "GPS photo-verified and deforestation checks passed for all farmers.",
                data,
            )
        else:
            data["error"] = error_msg
            return (
                f"EUDR compliance issue: {error_msg}",
                data,
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
        """Generate or retrieve the Digital Product Passport for a batch.
        Delegates to services.dpp_service for shared business logic.
        """
        from services.dpp_service import get_dpp as svc_get_dpp

        batch_id = args.get("batch_id")
        if not batch_id:
            return ("Please specify a batch ID.", {"error": "no_batch_id"})

        result = svc_get_dpp(db, batch_id=batch_id)

        if not result["success"]:
            return (f"Could not generate DPP: {result['error']}", {"error": result["error"]})

        # Build voice-friendly summary (preserving original formatting)
        p = result["product"]
        o = result["origin"]
        c = result["compliance"]
        bc = result["blockchain"]
        don = result["don_attestation"]

        don_line = ""
        if don["attested"]:
            don_line = (
                f"\n• DON Attestation: {don['risk_label'] or '?'} risk "
                f"({'✅ Compliant' if don['eudr_compliant'] else '❌ Non-compliant'})"
            )

        summary = (
            f"📋 DPP for {result['batch_id']}:\n"
            f"• Product: {p['name']} ({p['variety']})\n"
            f"• Origin: {o['region']}, {o['country']}\n"
            f"• EUDR: {'✅ Compliant' if c['eudr_compliant'] else '❌ Not compliant'}\n"
            f"• Blockchain: {'✅ Anchored' if bc['anchored'] else '⏳ Pending'}"
            f"{don_line}"
        )

        # Build backward-compatible data dict for existing consumers
        return (
            summary,
            {
                "batch_id": result["batch_id"],
                "passport_id": result["passport_id"],
                "gtin": p["gtin"],
                "origin": f"{o['region']}, {o['country']}",
                "variety": p["variety"],
                "processing": p["processing"],
                "grade": p["grade"],
                "quantity_kg": p["quantity_kg"],
                "farmer_name": o["farmer_name"],
                "cooperative": o["cooperative"],
                "certifications": result["certifications"],
                "latitude": c["latitude"],
                "longitude": c["longitude"],
                "gps_coordinates": f"{c['latitude'] or '?'}, {c['longitude'] or '?'}",
                "eudr_compliant": c["eudr_compliant"],
                "deforestation_risk": c["deforestation_risk"],
                "blockchain_anchored": bc["anchored"],
                "tx_hash": bc["tx_hash"],
                "don_attested": don["attested"],
                "don_risk_label": don["risk_label"],
                "qr_url": result["qr"]["url"],
                "qr_image": result["qr"]["image_url"],
                "lineage": result["lineage"],
            },
        )

    def _get_container_dpp(
        self, db: Session, args: Dict[str, Any],
        user_id: int = None, user_did: str = None
    ) -> Tuple[str, Dict[str, Any]]:
        """
        Get the aggregated Digital Product Passport for a shipping container.
        """
        from datetime import datetime, timezone
        from database.models import ContainerOffering, AggregationRelationship
        from dpp.dpp_builder import build_dpp, load_batch_data

        container_sscc = args.get("container_id") or args.get("container_sscc")
        if not container_sscc:
            return ("Please specify a container ID or SSCC.", {"error": "no_container_id"})

        # 1. Look up the container offering
        offering = (
            db.query(ContainerOffering)
            .filter(ContainerOffering.container_sscc == container_sscc)
            .first()
        )
        if not offering:
            return (
                f"Container '{container_sscc}' not found.",
                {"error": "container_not_found"},
            )

        # 2. Gather child batch IDs from active aggregation relationships
        agg_rows = (
            db.query(AggregationRelationship)
            .filter(
                AggregationRelationship.parent_sscc == container_sscc,
                AggregationRelationship.is_active == True,
            )
            .all()
        )
        child_batch_ids = [row.child_identifier for row in agg_rows]

        # 3. Build a DPP per child batch (derive real compliance values)
        child_dpps = []
        skipped = 0
        for bid in child_batch_ids:
            try:
                child_batch = load_batch_data(bid)
                d_risk = "none"
                d_compliant = True
                if child_batch and child_batch.farmer:
                    f = child_batch.farmer
                    risk = (f.deforestation_risk or "UNKNOWN").lower()
                    d_risk = risk if risk in ("low", "medium", "high", "unknown") else "none"
                    d_compliant = (
                        f.deforestation_compliant is True
                        and f.latitude is not None
                        and f.longitude is not None
                    )
                dpp = build_dpp(
                    batch_id=bid,
                    deforestation_risk=d_risk,
                    eudr_compliant=d_compliant,
                )
                child_dpps.append(dpp)
            except Exception:
                logger.warning("Could not build DPP for child batch %s", bid)
                skipped += 1

        # 4. Build a voice-friendly summary
        child_count = len(child_dpps)
        compliance_flags = [
            d.get("eudrCompliance", {}).get("complianceStatus", "UNKNOWN")
            for d in child_dpps
        ]
        non_compliant = sum(1 for s in compliance_flags if "NON" in s or "RISK" in s)

        summary_lines = [
            f"📦 Container {container_sscc}:",
            f"• Variety: {offering.variety or 'N/A'}, "
            f"{offering.processing_method or 'N/A'}, Grade {offering.grade or 'N/A'}",
            f"• Total quantity: {offering.total_quantity_kg or 0:,.0f} kg",
            f"• Status: {offering.status or 'N/A'}",
            f"• Child batches: {child_count} DPPs built"
            + (f" ({skipped} skipped)" if skipped else ""),
        ]
        if offering.certifications:
            summary_lines.append(f"• Certifications: {offering.certifications}")
        if offering.delivery_location:
            summary_lines.append(f"• Delivery: {offering.delivery_location}")
        if child_count:
            if non_compliant == 0:
                summary_lines.append("• EUDR: ✅ All child batches compliant")
            else:
                summary_lines.append(
                    f"• EUDR: ⚠️ {non_compliant}/{child_count} batch(es) have compliance issues"
                )

        return (
            "\n".join(summary_lines),
            {
                "containerSSCC": container_sscc,
                "totalQuantityKg": offering.total_quantity_kg,
                "variety": offering.variety,
                "processingMethod": offering.processing_method,
                "grade": offering.grade,
                "certifications": offering.certifications,
                "status": offering.status,
                "dppUrl": offering.dpp_url,
                "deliveryLocation": offering.delivery_location,
                "childBatchCount": child_count,
                "childBatches": child_dpps,
                "generatedAt": datetime.now(timezone.utc).isoformat(),
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

        # Extract contributor data - recursive DPP has 'contributors' not 'chainOfCustody'
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
        verified_quantity = args.get("verified_quantity_kg") or batch.quantity_kg
        quality_notes = args.get("quality_notes")

        batch.status = "VERIFIED"
        batch.verified_quantity = verified_quantity
        batch.verification_notes = quality_notes
        batch.verified_by_did = user_did or user.did
        batch.verifying_organization_id = user.organization_id
        batch.verified_at = datetime.utcnow()
        batch.verification_used = True

        # Persist quality assessment data if provided
        if args.get("cupping_score") is not None:
            batch.cupping_score = float(args["cupping_score"])
        if args.get("moisture_pct") is not None:
            batch.moisture_pct = float(args["moisture_pct"])
        if args.get("screen_size"):
            batch.screen_size = str(args["screen_size"])
        if args.get("defect_count") is not None:
            batch.defect_count = int(args["defect_count"])
        if args.get("defect_category"):
            batch.defect_category = str(args["defect_category"])
        if args.get("sensory_notes"):
            batch.sensory_notes = args["sensory_notes"]

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
        batch_id = args.get("batch_id")
        if not batch_id:
            return ("Please specify a batch ID.", {"error": "no_batch_id"})
        
        # Look up token_id from database
        from database.models import CoffeeBatch
        batch = db.query(CoffeeBatch).filter(CoffeeBatch.batch_id == batch_id).first()
        if not batch:
            return (
                f"Batch {batch_id} not found in database.",
                {"error": "batch_not_found", "batch_id": batch_id},
            )
        
        token_id = batch.token_id
        if not token_id:
            return (
                f"Batch {batch_id} exists but has not been tokenised yet.",
                {"error": "not_tokenised", "batch_id": batch_id},
            )

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
        
        # Handle token not found case
        if metadata.get('status') == 'TOKEN_NOT_FOUND':
            return (
                f"Token ID {token_id} does not exist on the blockchain contract.",
                {"token_id": token_id, "found": False, "status": "TOKEN_NOT_FOUND"},
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
        """Verify batch data integrity by comparing EPCIS event hash against blockchain."""
        batch_id = args.get("batch_id")
        if not batch_id:
            return ("Please specify a batch ID.", {"error": "no_batch_id"})

        try:
            import hashlib
            import json
            from database.crud import get_batch_by_id_or_gtin
            from database.models import EPCISEvent

            batch = get_batch_by_id_or_gtin(db, batch_id)
            if not batch:
                return (f"Batch '{batch_id}' not found.", {"error": "batch_not_found"})

            # Get the EPCIS event for this batch
            event = db.query(EPCISEvent).filter(
                EPCISEvent.batch_id == batch.id
            ).order_by(EPCISEvent.created_at.desc()).first()
            
            if not event:
                return (
                    f"Batch {batch.batch_id} has no EPCIS events - cannot verify hash.",
                    {"batch_id": batch.batch_id, "has_events": False, "verified": None},
                )
            
            # Re-compute hash from the stored event JSON using same method as creation
            # Canonicalize: sort keys, no spaces
            if event.event_json:
                canonical = json.dumps(event.event_json, sort_keys=True, separators=(',', ':'))
                current_hash = hashlib.sha256(canonical.encode('utf-8')).hexdigest()
            else:
                # Fallback to canonical_nquads if event_json is missing
                current_hash = hashlib.sha256(event.canonical_nquads.encode('utf-8')).hexdigest()

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
                f"Batch {batch.batch_id} is not anchored on-chain yet - "
                "cannot verify hash integrity.",
                {"batch_id": batch.batch_id, "anchored": False, "verified": None},
            )

        on_chain_hash = on_chain.get("event_hash", "")

        # Normalize for comparison
        a = current_hash.lower().replace("0x", "")
        b = on_chain_hash.lower().replace("0x", "")
        match = a == b

        if match:
            return (
                f"✅ Batch {batch.batch_id} data integrity verified - "
                "hash matches blockchain record. No tampering detected.",
                {
                    "batch_id": batch.batch_id,
                    "anchored": True,
                    "verified": True,
                    "hash": current_hash,
                },
            )
        else:
            return (
                f"⚠️ Batch {batch.batch_id} hash MISMATCH - data may have "
                "been modified since it was anchored on-chain.",
                {
                    "batch_id": batch.batch_id,
                    "anchored": True,
                    "verified": False,
                    "current_hash": current_hash,
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
                f"Note: contract not deployed - result not written on-chain.",
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

        # Find the farmer associated with this user via shared DID
        user = db.query(UserIdentity).filter_by(id=user_id).first()
        if not user or not user.did:
            return

        farmer = db.query(FarmerIdentity).filter_by(did=user.did).first()
        if not farmer or not farmer.latitude or not farmer.longitude:
            logger.debug(
                "Skipping CRE auto-attestation - farmer %s has no GPS",
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
