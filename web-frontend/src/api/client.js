/**
 * HTTP client wrapper for Voice Ledger API.
 * Auto-attaches JWT token when available.
 */

const BASE = '' // same-origin in production; Vite proxy in dev

export async function apiFetch(path, opts = {}) {
  const token = localStorage.getItem('vl_token')
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
    localStorage.removeItem('vl_token')
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
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`)
  return res.json()
}

/** GET JSON helper */
export async function getJSON(path) {
  const res = await apiFetch(path)
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`)
  return res.json()
}
