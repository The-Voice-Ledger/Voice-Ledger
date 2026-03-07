/**
 * Logistics & EUDR API helpers.
 *
 * Calls /api/logistics/* and /api/eudr/* endpoints directly.
 */

import { getJSON } from './client'

// ── Shipment tracking ────────────────────────────────────────────

/** Full shipment status + event timeline for a container. */
export function getShipmentStatus(containerSscc) {
  return getJSON(`/api/logistics/shipment/${encodeURIComponent(containerSscc)}`)
}

// ── EUDR Article 9 (flat customs format) ─────────────────────────

/** Flat EUDR Article 9 due diligence fields for a single batch. */
export function getEudrCompliance(batchId) {
  return getJSON(`/api/eudr/compliance/${encodeURIComponent(batchId)}`)
}

/** Container-level EUDR compliance package (all child batches). */
export function getContainerEudr(containerSscc) {
  return getJSON(`/api/eudr/container/${encodeURIComponent(containerSscc)}`)
}
