"""
DeFi Financing Pool API Router

REST endpoints for the on-chain receivables factoring pool:
  - Pool stats & investor balances (read-only)
  - Trade lifecycle: request advance, confirm delivery, cancel, default
  - Fee distribution analytics

Prefix: /api/financing
Separate from the marketplace pool_api.py (/api/pools).

Created: March 5, 2026
"""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/financing", tags=["defi-financing-pool"])


# ─────────────────────────────────────────
# Pydantic schemas
# ─────────────────────────────────────────

class PoolStats(BaseModel):
    total_assets_usdc: float
    total_advanced_usdc: float
    available_for_advance_usdc: float
    utilisation_pct: float
    cumulative_fees_usdc: float
    total_shares: float
    share_price_usdc: float


class InvestorBalance(BaseModel):
    address: str
    shares: float
    redeemable_usdc: float


class TradeDetail(BaseModel):
    trade_id: int
    token_id: int
    token_amount: int
    seller: str
    buyer: str
    agreed_price_usdc: float
    advance_amount_usdc: float
    fee_bps: int
    fee_amount_usdc: float
    shipment_hash: str
    farm_id: str
    created_at: int
    settled_at: int
    deadline: int
    status: str


class FeeStats(BaseModel):
    total_distributed_usdc: float
    total_to_investors_usdc: float
    total_to_protocol_usdc: float
    total_to_reserve_usdc: float
    investor_bps: int
    protocol_bps: int
    reserve_bps: int


class RequestAdvanceBody(BaseModel):
    token_id: int = Field(..., description="ERC-1155 container token ID")
    token_amount: int = Field(..., gt=0, description="Token amount (container quantity)")
    buyer: str = Field(..., description="Confirmed buyer wallet address")
    agreed_price_usdc: float = Field(..., gt=0, description="Agreed price in USDC")
    shipment_hash: str = Field(..., description="EPCIS shipment event hash (0x...)")
    farm_id: str = Field(..., description="Farm ID for CRE compliance check")


class ConfirmDeliveryBody(BaseModel):
    trade_id: int = Field(..., description="Trade ID to settle")


class TxResponse(BaseModel):
    success: bool
    tx_hash: Optional[str] = None
    message: str


# ─────────────────────────────────────────
# Lazy manager loader (import only when needed)
# ─────────────────────────────────────────

_mgr = None


def _get_mgr():
    global _mgr
    if _mgr is None:
        try:
            from blockchain.financing_manager import get_financing_manager
            _mgr = get_financing_manager()
        except Exception as e:
            logger.error("Failed to initialise FinancingManager: %s", e)
            raise HTTPException(
                status_code=503,
                detail=f"Financing pool not available: {e}",
            )
    return _mgr


# ─────────────────────────────────────────
# READ endpoints
# ─────────────────────────────────────────

@router.get("/pool/stats", response_model=PoolStats)
async def get_pool_stats():
    """Current financing pool metrics."""
    return _get_mgr().pool_stats()


@router.get("/pool/investor/{address}", response_model=InvestorBalance)
async def get_investor_balance(address: str):
    """Investor's vlUSDC share balance and redeemable USDC."""
    return _get_mgr().investor_balance(address)


@router.get("/trade/{trade_id}", response_model=TradeDetail)
async def get_trade(trade_id: int):
    """Fetch trade details by ID."""
    result = _get_mgr().get_trade(trade_id)
    if not result:
        raise HTTPException(status_code=404, detail=f"Trade {trade_id} not found")
    return result


@router.get("/trade/token/{token_id}/pledged")
async def check_token_pledged(token_id: int):
    """Check if an ERC-1155 token is locked as collateral."""
    return {"token_id": token_id, "pledged": _get_mgr().is_token_pledged(token_id)}


@router.get("/fees/stats", response_model=FeeStats)
async def get_fee_stats():
    """Cumulative fee distribution analytics."""
    return _get_mgr().fee_stats()


# ─────────────────────────────────────────
# WRITE endpoints (require API key or JWT)
# ─────────────────────────────────────────

def _check_auth(api_key: Optional[str], authorization: Optional[str]):
    """Accept either x-api-key header or valid JWT Bearer token."""
    import os
    # 1) Check API key
    expected = os.getenv("VOICE_LEDGER_API_KEY", "")
    if api_key and expected and api_key == expected:
        return
    # 2) Check JWT Bearer token
    if authorization and authorization.startswith("Bearer "):
        try:
            from voice.web.auth import verify_jwt_token
            verify_jwt_token(authorization.replace("Bearer ", ""))
            return
        except Exception:
            pass
    raise HTTPException(status_code=401, detail="Authentication required (API key or JWT)")


@router.post("/trade/request-advance", response_model=TxResponse)
async def request_advance(
    body: RequestAdvanceBody,
    x_api_key: Optional[str] = Header(None),
    authorization: Optional[str] = Header(None),
):
    """Seller requests an advance against a shipped container."""
    _check_auth(x_api_key, authorization)
    tx = _get_mgr().request_advance(
        token_id=body.token_id,
        token_amount=body.token_amount,
        buyer=body.buyer,
        agreed_price_usdc=body.agreed_price_usdc,
        shipment_hash=body.shipment_hash,
        farm_id=body.farm_id,
    )
    if tx:
        return TxResponse(success=True, tx_hash=tx, message="Advance disbursed")
    raise HTTPException(status_code=400, detail="Advance request failed (check logs)")


@router.post("/trade/confirm-delivery", response_model=TxResponse)
async def confirm_delivery(
    body: ConfirmDeliveryBody,
    x_api_key: Optional[str] = Header(None),
    authorization: Optional[str] = Header(None),
):
    """Buyer confirms delivery and repays the pool."""
    _check_auth(x_api_key, authorization)
    tx = _get_mgr().confirm_delivery(body.trade_id)
    if tx:
        return TxResponse(success=True, tx_hash=tx, message="Delivery confirmed, pool repaid")
    raise HTTPException(status_code=400, detail="Delivery confirmation failed")


@router.post("/trade/{trade_id}/cancel", response_model=TxResponse)
async def cancel_trade(
    trade_id: int,
    x_api_key: Optional[str] = Header(None),
    authorization: Optional[str] = Header(None),
):
    """Cancel a trade (seller returns advance, gets token back)."""
    _check_auth(x_api_key, authorization)
    tx = _get_mgr().cancel_trade(trade_id)
    if tx:
        return TxResponse(success=True, tx_hash=tx, message="Trade cancelled")
    raise HTTPException(status_code=400, detail="Cancellation failed")


@router.post("/trade/{trade_id}/mark-default", response_model=TxResponse)
async def mark_default(
    trade_id: int,
    x_api_key: Optional[str] = Header(None),
    authorization: Optional[str] = Header(None),
):
    """Mark an overdue trade as defaulted."""
    _check_auth(x_api_key, authorization)
    tx = _get_mgr().mark_default(trade_id)
    if tx:
        return TxResponse(success=True, tx_hash=tx, message="Trade marked as defaulted")
    raise HTTPException(status_code=400, detail="Default marking failed")
