/**
 * HTTP client wrapper for Voice Ledger API.
 * Auto-attaches JWT token when available.
 */

const BASE = '' // same-origin in production; Vite proxy in dev

export async function apiFetch(path, opts = {}) {
  const token = localStorage.getItem('voice-ledger-auth') ? JSON.parse(localStorage.getItem('voice-ledger-auth')).state?.token : null
  const headers = { ...(opts.headers || {}) }

  if (token) {
    headers['Authorization'] = `Bearer ${token}`
  }

  // Don't set Content-Type for FormData - browser sets multipart boundary
  if (!(opts.body instanceof FormData) && !headers['Content-Type']) {
    headers['Content-Type'] = 'application/json'
  }

  const res = await fetch(`${BASE}${path}`, { ...opts, headers })

  if (res.status === 401) {
    // Token expired - clear and let UI redirect
    const authData = localStorage.getItem('voice-ledger-auth')
    if (authData) {
      const parsed = JSON.parse(authData)
      if (parsed.state?.token) {
        localStorage.setItem('voice-ledger-auth', JSON.stringify({ ...parsed, state: { ...parsed.state, token: null, user: null, isAuthenticated: false } }))
      }
    }
    window.dispatchEvent(new Event('vl:auth-expired'))
  }

  return res
}

/** POST JSON helper */
export async function postJSON(path, body) {
  const res = await apiFetch(path, {
    method: 'POST',
    body: JSON.stringify(body),
  })
  if (!res.ok) {
    const error = new Error(`${res.status} ${res.statusText}`)
    error.status = res.status
    error.statusText = res.statusText
    throw error
  }
  return res.json()
}

/** GET JSON helper */
export async function getJSON(path) {
  const res = await apiFetch(path)
  if (!res.ok) {
    const error = new Error(`${res.status} ${res.statusText}`)
    error.status = res.status
    error.statusText = res.statusText
    throw error
  }
  return res.json()
}
