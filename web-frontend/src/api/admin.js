/**
 * Admin dashboard API helpers for Voice Ledger.
 * All write endpoints require a valid JWT (Bearer token) from /api/auth/login.
 */

import { getJSON, postJSON, apiFetch } from './client'

// ── Authentication ────────────────────────────────────────────────

export function loginAdmin(phone_number, pin) {
  return postJSON('/api/auth/login', { phone_number, pin })
}

export function getMe() {
  return getJSON('/api/auth/me')
}

// ── Analytics ─────────────────────────────────────────────────────

export function getAnalyticsSummary() {
  return getJSON('/admin/analytics/summary')
}

export function getRegistrationAnalytics(days = 30) {
  return getJSON(`/admin/analytics/registrations?days=${days}`)
}

// ── Registrations ─────────────────────────────────────────────────

export function getRegistrations(params = {}) {
  const q = new URLSearchParams()
  if (params.status) q.set('status', params.status)
  if (params.role) q.set('role', params.role)
  if (params.limit) q.set('limit', params.limit)
  if (params.offset) q.set('offset', params.offset)
  return getJSON(`/admin/registrations?${q}`)
}

export function approveRegistration(userId, data = {}) {
  return postJSON(`/admin/registrations/${userId}/approve`, data)
}

export function rejectRegistration(userId, data = {}) {
  return postJSON(`/admin/registrations/${userId}/reject`, data)
}

// ── Users ─────────────────────────────────────────────────────────

export function getUsers(params = {}) {
  const q = new URLSearchParams()
  if (params.search) q.set('search', params.search)
  if (params.role) q.set('role', params.role)
  if (params.approved != null) q.set('approved', params.approved)
  if (params.limit) q.set('limit', params.limit)
  if (params.offset) q.set('offset', params.offset)
  return getJSON(`/admin/users?${q}`)
}

export function getUserDetail(userId) {
  return getJSON(`/admin/users/${userId}`)
}

export async function updateUser(userId, data) {
  const res = await apiFetch(`/admin/users/${userId}`, {
    method: 'PATCH',
    body: JSON.stringify(data),
  })
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`)
  return res.json()
}

// ── Marketplace monitoring ─────────────────────────────────────────

export function getAdminRFQs(params = {}) {
  const q = new URLSearchParams()
  if (params.status) q.set('status', params.status)
  if (params.limit) q.set('limit', params.limit)
  if (params.offset) q.set('offset', params.offset)
  return getJSON(`/admin/rfqs?${q}`)
}

export function getAdminOffers(params = {}) {
  const q = new URLSearchParams()
  if (params.rfq_id) q.set('rfq_id', params.rfq_id)
  if (params.limit) q.set('limit', params.limit)
  return getJSON(`/admin/offers?${q}`)
}

export function getAdminSettlements(params = {}) {
  const q = new URLSearchParams()
  if (params.payment_status) q.set('payment_status', params.payment_status)
  if (params.limit) q.set('limit', params.limit)
  return getJSON(`/admin/settlements?${q}`)
}

// ── UAT Issues ────────────────────────────────────────────────────

export function createUATIssue(issue) {
  return postJSON('/api/v1/uat/issues', issue)
}

export function listUATIssues(params = {}) {
  const q = new URLSearchParams()
  if (params.status) q.set('status', params.status)
  if (params.severity) q.set('severity', params.severity)
  if (params.page) q.set('page', params.page)
  if (params.limit) q.set('limit', params.limit)
  if (params.offset) q.set('offset', params.offset)
  return getJSON(`/api/v1/uat/issues?${q}`)
}

export async function updateUATIssue(issueId, data) {
  const res = await apiFetch(`/api/v1/uat/issues/${issueId}`, {
    method: 'PATCH',
    body: JSON.stringify(data),
  })
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`)
  return res.json()
}
