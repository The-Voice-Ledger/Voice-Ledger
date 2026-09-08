/**
 * SSI (Self-Sovereign Identity) API
 *
 * Wraps the public DID verification endpoints.
 * No authentication required — credentials are public by design.
 */

import { getJSON } from './client'

/**
 * Fetch the DID document and verify all associated credentials.
 * @param {string} did  e.g. "did:key:z6MkhaXgBZ…"
 * @returns {Promise<{did, user_info, credentials, summary}>}
 */
export async function verifyDid(did) {
  return getJSON(`/voice/verify/${did}`)
}

/**
 * Fetch a W3C Verifiable Presentation for all credentials of a DID.
 * @param {string} did
 * @returns {Promise<object>} JSON-LD Verifiable Presentation
 */
export async function getVerifiablePresentation(did) {
  return getJSON(`/voice/verify/${did}/presentation`)
}
