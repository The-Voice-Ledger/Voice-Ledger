/**
 * DeFi Financing Pool API helpers.
 *
 * Calls /api/financing/* endpoints directly (not via agent).
 */

import { getJSON, postJSON } from './client'

// ── Read-only ────────────────────────────────────────────────────

/** Pool-level metrics: TVL, utilisation, share price, etc. */
export function getPoolStats() {
  return getJSON('/api/financing/pool/stats')
}

/** Investor's vlUSDC share balance + redeemable USDC. */
export function getInvestorBalance(address) {
  return getJSON(`/api/financing/pool/investor/${encodeURIComponent(address)}`)
}

/** Full trade details by ID. */
export function getTrade(tradeId) {
  return getJSON(`/api/financing/trade/${tradeId}`)
}

/** Check if a token is pledged as collateral. */
export function isTokenPledged(tokenId) {
  return getJSON(`/api/financing/trade/token/${tokenId}/pledged`)
}

/** Fee distribution analytics. */
export function getFeeStats() {
  return getJSON('/api/financing/fees/stats')
}

// ── Write (require API key header - routed through backend) ─────

/** Seller requests an advance against a shipped container. */
export function requestAdvance(body) {
  return postJSON('/api/financing/trade/request-advance', body)
}

/** Buyer confirms delivery and repays the pool. */
export function confirmDelivery(tradeId) {
  return postJSON('/api/financing/trade/confirm-delivery', { trade_id: tradeId })
}
