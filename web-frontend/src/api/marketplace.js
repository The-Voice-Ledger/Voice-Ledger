/**
 * REST API helpers for marketplace, DPP, and compliance pages.
 * These call existing FastAPI endpoints directly (not via the agent).
 */

import { getJSON, postJSON } from './client'

// ── RFQs ─────────────────────────────────────────────────────────────

/** List open RFQs. Optional filters: status, variety */
export function listRFQs(params = {}) {
  const q = new URLSearchParams()
  if (params.status) q.set('status', params.status)
  if (params.variety) q.set('variety', params.variety)
  if (params.limit) q.set('limit', params.limit)
  return getJSON(`/api/rfqs?${q}`)
}

/** Get offers on a specific RFQ */
export function listRFQOffers(rfqId) {
  return getJSON(`/api/rfq/${rfqId}/offers`)
}

// ── Containers ───────────────────────────────────────────────────────

/** List available containers */
export function listContainers(params = {}) {
  const q = new URLSearchParams()
  if (params.status) q.set('status', params.status)
  if (params.min_quantity_kg) q.set('min_quantity_kg', params.min_quantity_kg)
  return getJSON(`/api/containers?${q}`)
}

/** Get container details */
export function getContainer(containerId) {
  return getJSON(`/api/container/${containerId}`)
}

// ── DPP ──────────────────────────────────────────────────────────────

/** Fetch DPP via the agent (uses the get_dpp tool under the hood) */
export function fetchDPP(batchId) {
  return postJSON('/api/agent/text', {
    text: `get DPP for batch ${batchId}`,
    language: 'en',
  })
}

// ── Compliance ───────────────────────────────────────────────────────

/** Check EUDR compliance for batch IDs via the agent */
export function checkCompliance(batchIds) {
  return postJSON('/api/agent/text', {
    text: `check EUDR compliance for batches ${batchIds.join(', ')}`,
    language: 'en',
  })
}

/** Query batches via the agent */
export function queryBatches(params = {}) {
  const parts = ['show me batches']
  if (params.status) parts.push(`with status ${params.status}`)
  if (params.origin) parts.push(`from ${params.origin}`)
  return postJSON('/api/agent/text', {
    text: parts.join(' '),
    language: 'en',
  })
}

// ── Container Pools (shared buying) ─────────────────────────────────

/** List active container pools */
export function listPools(params = {}) {
  const q = new URLSearchParams()
  if (params.status) q.set('status', params.status)
  if (params.region) q.set('region', params.region)
  if (params.container_offering_id) q.set('container_offering_id', params.container_offering_id)
  return getJSON(`/api/pools?${q}`)
}

/** Get pool detail */
export function getPool(poolId) {
  return getJSON(`/api/pool/${poolId}`)
}

/** Commit to a pool */
export function commitToPool(data) {
  return postJSON('/api/pool/commit', data)
}

/** List current user's pool commitments */
export function listMyCommitments() {
  return getJSON('/api/my/commitments')
}

/** List current user's RFQs (private) */
export function listMyRFQs() {
  return getJSON('/api/my/rfqs')
}

/** Get region → port mapping */
export function listRegions() {
  return getJSON('/api/regions')
}
