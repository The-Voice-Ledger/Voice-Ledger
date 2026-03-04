/**
 * Agent API - text and voice chat endpoints.
 */

import { apiFetch, postJSON } from './client'

/**
 * Send a text message to the agent.
 * @param {string} text
 * @param {object} opts  { language, conversationId, context, voice }
 * @returns {Promise<object>} AgentTextResponse
 */
export async function sendText(text, opts = {}) {
  return postJSON('/api/agent/text', {
    text,
    language: opts.language || 'en',
    conversation_id: opts.conversationId || null,
    context: opts.context || null,
    voice: opts.voice || false,
  })
}

/**
 * Send an audio blob to the agent.
 * @param {Blob} audioBlob
 * @param {object} opts  { language, conversationId, context }
 * @returns {Promise<object>} AgentTextResponse
 */
export async function sendVoice(audioBlob, opts = {}) {
  const fd = new FormData()
  fd.append('audio', audioBlob, 'recording.webm')
  fd.append('language', opts.language || 'en')
  if (opts.conversationId) fd.append('conversation_id', opts.conversationId)
  if (opts.context) fd.append('context', JSON.stringify(opts.context))

  const res = await apiFetch('/api/agent/voice', {
    method: 'POST',
    body: fd,
  })
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`)
  return res.json()
}

/**
 * Login with phone + PIN, receive JWT.
 * @param {string} phone
 * @param {string} pin
 * @returns {Promise<{token: string, user: object}>}
 */
export async function login(phone, pin) {
  return postJSON('/api/auth/login', { phone_number: phone, pin })
}

/** Agent health check */
export async function agentHealth() {
  const res = await apiFetch('/api/agent/health')
  return res.json()
}
