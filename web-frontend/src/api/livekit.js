/**
 * LiveKit API — token endpoint and helpers.
 */

import { postJSON, getJSON } from './client'

/**
 * Get a LiveKit room token from our backend.
 * @param {object} opts  { userId, userName, userRole, userDid }
 * @returns {Promise<{token: string, url: string, room: string}>}
 */
export async function getLiveKitToken(opts = {}) {
  return postJSON('/api/livekit/token', {
    user_id: opts.userId || 'anonymous',
    user_name: opts.userName || 'Guest',
    user_role: opts.userRole || 'user',
    user_did: opts.userDid || null,
  })
}

/**
 * Check if LiveKit is configured on the backend.
 * @returns {Promise<{configured: boolean, url: string|null}>}
 */
export async function liveKitHealth() {
  return getJSON('/api/livekit/health')
}
