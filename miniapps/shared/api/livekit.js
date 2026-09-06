/**
 * LiveKit API - token endpoint and helpers.
 */

// Simple fetch helpers (same as web-frontend client.js)
async function postJSON(path, body) {
  const response = await fetch(path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!response.ok) throw new Error(`${response.status} ${response.statusText}`)
  return response.json()
}

async function getJSON(path) {
  const response = await fetch(path)
  if (!response.ok) throw new Error(`${response.status} ${response.statusText}`)
  return response.json()
}

/**
 * Get a LiveKit room token from our backend.
 * @param {object} opts  { userId, userName, userRole, userDid }
 * @returns {Promise<{token: string, url: string, room: string}>}
 */
async function getLiveKitToken(opts = {}) {
  return postJSON('/api/livekit/token', {
    user_id:   opts.userId   || 'anonymous',
    user_name: opts.userName || 'Guest',
    user_role: opts.userRole || 'user',
    user_did:  opts.userDid  || null,
    language:  opts.language || 'en',
  })
}

/**
 * Check if LiveKit is configured on the backend.
 * @returns {Promise<{configured: boolean, url: string|null}>}
 */
async function liveKitHealth() {
  return getJSON('/api/livekit/health')
}

// Attach to window for global access
window.getLiveKitToken = getLiveKitToken
window.liveKitHealth = liveKitHealth
