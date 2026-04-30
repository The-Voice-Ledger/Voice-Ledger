/**
 * Admin Dashboard — Voice Ledger
 *
 * Tabs:
 *   Overview   — summary stats cards
 *   Registrations — pending approvals + approved/rejected list
 *   Users      — search, filter, view detail, edit language/org
 *   Marketplace — RFQs, offers, settlements
 *   UAT Issues — review and resolve UAT bug reports
 *
 * Auth: requires ADMIN or SYSTEM_ADMIN role (enforced by backend + frontend guard).
 */

import { useState, useEffect, useCallback } from 'react'
import { useTranslation } from 'react-i18next'
import { Navigate } from 'react-router-dom'
import {
  IconUsers, IconChartBar, IconShieldCheck, IconCircleCheck, IconCircleX,
  IconSearch, IconRefreshCw, IconFileText, IconPackage, IconHandshake,
  IconTrendingUp, IconInfo, IconX, IconCheck, IconLoader,
} from '../components/svg/Icons'
import {
  getAnalyticsSummary,
  getRegistrations, approveRegistration, rejectRegistration,
  getUsers, getUserDetail, updateUser,
  getAdminRFQs, getAdminOffers, getAdminSettlements,
  listUATIssues, updateUATIssue,
} from '../api/admin'
import useAuthStore from '../stores/authStore'
import PageHeroBg from '../components/svg/PageHeroBg'
import TechCardBg from '../components/svg/TechCardBg'

// ── Helpers ───────────────────────────────────────────────────────

const ROLE_COLORS = {
  FARMER:              'bg-green-100 text-green-700',
  COOPERATIVE_MANAGER: 'bg-blue-100  text-blue-700',
  EXPORTER:            'bg-amber-100 text-amber-700',
  BUYER:               'bg-purple-100 text-purple-700',
  ADMIN:               'bg-stone-200  text-stone-700',
  SYSTEM_ADMIN:        'bg-stone-900  text-white',
}

const SEVERITY_COLORS = {
  blocker:  'bg-red-100   text-red-700',
  major:    'bg-orange-100 text-orange-700',
  minor:    'bg-yellow-100 text-yellow-700',
  cosmetic: 'bg-stone-100  text-stone-600',
}

const UAT_STATUS_COLORS = {
  open:        'bg-red-100   text-red-700',
  in_progress: 'bg-blue-100  text-blue-700',
  fixed:       'bg-green-100 text-green-700',
  verified:    'bg-teal-100  text-teal-700',
  wont_fix:    'bg-stone-100 text-stone-500',
}

function RoleBadge({ role }) {
  return (
    <span className={`text-xs font-medium rounded-full px-2.5 py-0.5 ${ROLE_COLORS[role] || 'bg-stone-100 text-stone-600'}`}>
      {role?.replace(/_/g, ' ')}
    </span>
  )
}

function ApprovalBadge({ approved }) {
  return approved
    ? <span className="text-xs font-medium rounded-full px-2.5 py-0.5 bg-green-100 text-green-700">Approved</span>
    : <span className="text-xs font-medium rounded-full px-2.5 py-0.5 bg-amber-100 text-amber-700">Pending</span>
}

function SeverityBadge({ severity }) {
  return (
    <span className={`text-xs font-medium rounded-full px-2.5 py-0.5 ${SEVERITY_COLORS[severity] || 'bg-stone-100 text-stone-600'}`}>
      {severity}
    </span>
  )
}

function UATStatusBadge({ status }) {
  return (
    <span className={`text-xs font-medium rounded-full px-2.5 py-0.5 ${UAT_STATUS_COLORS[status] || 'bg-stone-100 text-stone-600'}`}>
      {status?.replace(/_/g, ' ')}
    </span>
  )
}

// ── Shared skeleton ───────────────────────────────────────────────

function Skeleton({ rows = 4 }) {
  return (
    <div className="space-y-3 animate-pulse">
      {Array.from({ length: rows }).map((_, i) => (
        <div key={i} className="bg-white rounded-xl border border-stone-200 p-4 flex items-center gap-3">
          <div className="w-8 h-8 rounded-full bg-stone-200 shrink-0" />
          <div className="flex-1 space-y-2">
            <div className="h-3 bg-stone-200 rounded w-1/3" />
            <div className="h-2 bg-stone-100 rounded w-1/2" />
          </div>
          <div className="h-5 w-16 bg-stone-100 rounded-full" />
        </div>
      ))}
    </div>
  )
}

// ── Stat card (overview tab) ──────────────────────────────────────

function StatCard({ icon: Icon, label, value, sub, accent }) {
  return (
    <div className="relative overflow-hidden bg-white rounded-xl border border-stone-200 p-5 flex flex-col gap-1 hover:-translate-y-0.5 hover:shadow-lg transition-all duration-200">
      <TechCardBg variant="dotgrid" />
      <div className={`relative z-10 flex items-center gap-2 text-xs text-stone-400 uppercase tracking-wider`}>
        <Icon className={`w-4 h-4 ${accent || 'text-stone-400'}`} />
        {label}
      </div>
      <p className="relative z-10 text-2xl font-bold font-mono text-stone-900">{value ?? '—'}</p>
      {sub && <p className="relative z-10 text-xs text-stone-500">{sub}</p>}
    </div>
  )
}

// ── Overview tab ─────────────────────────────────────────────────

function OverviewTab() {
  const [stats, setStats] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const data = await getAnalyticsSummary()
      setStats(data)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { load() }, [load])

  if (loading) {
    return (
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 animate-pulse">
        {Array.from({ length: 8 }).map((_, i) => (
          <div key={i} className="bg-white rounded-xl border border-stone-200 p-5">
            <div className="h-3 w-24 bg-stone-200 rounded mb-3" />
            <div className="h-7 w-16 bg-stone-200 rounded" />
          </div>
        ))}
      </div>
    )
  }

  if (error) {
    return (
      <div className="bg-red-50 border border-red-200 rounded-xl p-5 text-sm text-red-700">
        Failed to load analytics: {error}
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <StatCard icon={IconUsers}     label="Total Users"          value={stats?.total_users}            accent="text-stone-500" />
        <StatCard icon={IconInfo}      label="Pending Approval"     value={stats?.pending_registrations}  accent="text-amber-500" />
        <StatCard icon={IconPackage}   label="Total Batches"        value={stats?.total_batches}          accent="text-forest-600" />
        <StatCard icon={IconShieldCheck} label="Verified Batches"   value={stats?.verified_batches}       accent="text-green-600" />
        <StatCard icon={IconFileText}  label="Total RFQs"           value={stats?.marketplace?.total_rfqs}    accent="text-blue-500" />
        <StatCard icon={IconTrendingUp} label="Active RFQs"         value={stats?.marketplace?.active_rfqs}   accent="text-indigo-500" />
        <StatCard icon={IconHandshake} label="Settlements"          value={stats?.acceptances?.total}         accent="text-purple-500" />
        <StatCard icon={IconChartBar}  label="Pending Payments"     value={stats?.pending_payments}           accent="text-red-500" />
      </div>

      {/* Role breakdown */}
      {stats?.users?.by_role && (
        <div className="relative overflow-hidden bg-white rounded-xl border border-stone-200 p-5">
          <TechCardBg variant="circuit" />
          <h3 className="relative z-10 text-sm font-semibold text-stone-800 mb-4 section-heading">Users by Role</h3>
          <div className="relative z-10 flex flex-wrap gap-3">
            {Object.entries(stats.users.by_role).map(([role, count]) => (
              <div key={role} className="flex items-center gap-2 bg-stone-50 border border-stone-100 rounded-lg px-3 py-2">
                <RoleBadge role={role} />
                <span className="text-sm font-bold font-mono text-stone-900">{count}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

// ── Registrations tab ────────────────────────────────────────────

function RegistrationsTab() {
  const [filterStatus, setFilterStatus] = useState('PENDING')
  const [filterRole, setFilterRole] = useState('')
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(false)
  const [actionLoading, setActionLoading] = useState({})
  const [comment, setComment] = useState('')
  const [commentFor, setCommentFor] = useState(null)
  const [toast, setToast] = useState(null)

  const showToast = (msg, ok = true) => {
    setToast({ msg, ok })
    setTimeout(() => setToast(null), 3000)
  }

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const params = { limit: 100 }
      if (filterStatus) params.status = filterStatus
      if (filterRole) params.role = filterRole
      const res = await getRegistrations(params)
      setData(res)
    } catch (err) {
      showToast(`Load failed: ${err.message}`, false)
    } finally {
      setLoading(false)
    }
  }, [filterStatus, filterRole])

  useEffect(() => { load() }, [load])

  const handleApprove = async (userId, name) => {
    setActionLoading((s) => ({ ...s, [`approve_${userId}`]: true }))
    try {
      await approveRegistration(userId, { comments: comment })
      showToast(`${name} approved`)
      setCommentFor(null)
      setComment('')
      load()
    } catch (err) {
      showToast(`Approve failed: ${err.message}`, false)
    } finally {
      setActionLoading((s) => ({ ...s, [`approve_${userId}`]: false }))
    }
  }

  const handleReject = async (userId, name) => {
    setActionLoading((s) => ({ ...s, [`reject_${userId}`]: true }))
    try {
      await rejectRegistration(userId, { comments: comment })
      showToast(`${name} rejected`)
      setCommentFor(null)
      setComment('')
      load()
    } catch (err) {
      showToast(`Reject failed: ${err.message}`, false)
    } finally {
      setActionLoading((s) => ({ ...s, [`reject_${userId}`]: false }))
    }
  }

  const registrations = data?.registrations || []

  return (
    <div className="space-y-4">
      {/* Toast */}
      {toast && (
        <div className={`fixed top-20 right-4 z-50 px-4 py-2.5 rounded-xl text-sm font-medium shadow-lg animate-fade-in-up ${toast.ok ? 'bg-green-600 text-white' : 'bg-red-600 text-white'}`}>
          {toast.msg}
        </div>
      )}

      {/* Filters */}
      <div className="flex flex-wrap gap-3 items-center">
        <div className="flex rounded-lg border border-stone-200 overflow-hidden text-xs font-medium">
          {['', 'PENDING', 'APPROVED'].map((s) => (
            <button
              key={s || 'ALL'}
              onClick={() => setFilterStatus(s)}
              className={`px-3 py-1.5 transition ${filterStatus === s ? 'bg-stone-900 text-white' : 'bg-white text-stone-600 hover:bg-stone-50'}`}
            >
              {s || 'All'}
            </button>
          ))}
        </div>

        <select
          value={filterRole}
          onChange={(e) => setFilterRole(e.target.value)}
          className="rounded-lg border border-stone-200 px-3 py-1.5 text-xs bg-white outline-none focus:border-stone-400"
        >
          <option value="">All roles</option>
          <option value="FARMER">Farmer</option>
          <option value="COOPERATIVE_MANAGER">Cooperative Manager</option>
          <option value="EXPORTER">Exporter</option>
          <option value="BUYER">Buyer</option>
        </select>

        <button onClick={load} className="flex items-center gap-1.5 text-xs text-stone-500 hover:text-stone-800 transition">
          <IconRefreshCw className="w-3.5 h-3.5" /> Refresh
        </button>

        {data && (
          <span className="text-xs text-stone-400 ml-auto">{data.total} total</span>
        )}
      </div>

      {/* List */}
      {loading ? <Skeleton rows={5} /> : registrations.length === 0 ? (
        <div className="text-center py-12 text-stone-400 text-sm">No registrations found.</div>
      ) : (
        <div className="space-y-3">
          {registrations.map((reg) => (
            <div key={reg.id} className="relative overflow-hidden bg-white rounded-xl border border-stone-200 p-4 hover:shadow-md transition-all">
              <TechCardBg variant="dotgrid" />
              <div className="relative z-10">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div className="space-y-1 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="font-semibold text-stone-900 text-sm">{reg.name || 'Unnamed'}</span>
                      <RoleBadge role={reg.role} />
                      <ApprovalBadge approved={reg.is_approved} />
                    </div>
                    <p className="text-xs text-stone-500">
                      {reg.phone_number}
                      {reg.organization ? ` · ${reg.organization}` : ''}
                    </p>
                    <p className="text-xs text-stone-400">ID: {reg.id}</p>
                  </div>

                  {/* Actions (only show for pending) */}
                  {!reg.is_approved && (
                    <div className="flex items-center gap-2 shrink-0">
                      {commentFor === reg.id ? (
                        <div className="flex flex-col gap-1.5">
                          <input
                            type="text"
                            placeholder="Optional comment..."
                            value={comment}
                            onChange={(e) => setComment(e.target.value)}
                            className="text-xs rounded-lg border border-stone-200 px-2 py-1 outline-none focus:border-stone-400 w-44"
                          />
                          <div className="flex gap-1.5">
                            <button
                              onClick={() => handleApprove(reg.id, reg.name)}
                              disabled={actionLoading[`approve_${reg.id}`]}
                              className="flex items-center gap-1 px-2.5 py-1 rounded-lg bg-green-600 hover:bg-green-700 text-white text-xs font-medium transition disabled:opacity-50"
                            >
                              {actionLoading[`approve_${reg.id}`] ? <IconLoader className="w-3 h-3" /> : <IconCheck className="w-3 h-3" />}
                              Approve
                            </button>
                            <button
                              onClick={() => handleReject(reg.id, reg.name)}
                              disabled={actionLoading[`reject_${reg.id}`]}
                              className="flex items-center gap-1 px-2.5 py-1 rounded-lg bg-red-600 hover:bg-red-700 text-white text-xs font-medium transition disabled:opacity-50"
                            >
                              {actionLoading[`reject_${reg.id}`] ? <IconLoader className="w-3 h-3" /> : <IconX className="w-3 h-3" />}
                              Reject
                            </button>
                            <button
                              onClick={() => setCommentFor(null)}
                              className="px-2.5 py-1 rounded-lg border border-stone-200 text-xs text-stone-500 hover:bg-stone-50 transition"
                            >
                              Cancel
                            </button>
                          </div>
                        </div>
                      ) : (
                        <button
                          onClick={() => { setCommentFor(reg.id); setComment('') }}
                          className="px-3 py-1.5 rounded-lg bg-stone-900 hover:bg-stone-800 text-white text-xs font-medium transition"
                        >
                          Review
                        </button>
                      )}
                    </div>
                  )}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

// ── Users tab ─────────────────────────────────────────────────────

function UsersTab() {
  const [search, setSearch] = useState('')
  const [filterRole, setFilterRole] = useState('')
  const [filterApproved, setFilterApproved] = useState('')
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(false)
  const [selected, setSelected] = useState(null)
  const [detail, setDetail] = useState(null)
  const [detailLoading, setDetailLoading] = useState(false)
  const [editing, setEditing] = useState(false)
  const [editForm, setEditForm] = useState({})
  const [saving, setSaving] = useState(false)
  const [toast, setToast] = useState(null)

  const showToast = (msg, ok = true) => {
    setToast({ msg, ok })
    setTimeout(() => setToast(null), 3000)
  }

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const params = { limit: 100 }
      if (search) params.search = search
      if (filterRole) params.role = filterRole
      if (filterApproved !== '') params.approved = filterApproved
      const res = await getUsers(params)
      setData(res)
    } catch (err) {
      showToast(`Load failed: ${err.message}`, false)
    } finally {
      setLoading(false)
    }
  }, [search, filterRole, filterApproved])

  useEffect(() => { load() }, [load])

  const openDetail = async (userId) => {
    setSelected(userId)
    setDetail(null)
    setEditing(false)
    setDetailLoading(true)
    try {
      const d = await getUserDetail(userId)
      setDetail(d)
      setEditForm({ preferred_language: d.preferred_language, organization_id: d.organization_id })
    } catch (err) {
      showToast(`Load failed: ${err.message}`, false)
    } finally {
      setDetailLoading(false)
    }
  }

  const handleSave = async () => {
    if (!selected) return
    setSaving(true)
    try {
      await updateUser(selected, editForm)
      showToast('User updated')
      setEditing(false)
      openDetail(selected)
      load()
    } catch (err) {
      showToast(`Save failed: ${err.message}`, false)
    } finally {
      setSaving(false)
    }
  }

  const users = data?.users || []

  return (
    <div className="space-y-4">
      {toast && (
        <div className={`fixed top-20 right-4 z-50 px-4 py-2.5 rounded-xl text-sm font-medium shadow-lg animate-fade-in-up ${toast.ok ? 'bg-green-600 text-white' : 'bg-red-600 text-white'}`}>
          {toast.msg}
        </div>
      )}

      {/* Search + filters */}
      <div className="flex flex-wrap gap-3 items-center">
        <div className="relative flex-1 min-w-48">
          <IconSearch className="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-stone-400" />
          <input
            type="text"
            placeholder="Search name or phone..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full rounded-lg border border-stone-200 pl-8 pr-3 py-1.5 text-xs outline-none focus:border-stone-400 focus:ring-1 focus:ring-stone-200"
          />
        </div>

        <select
          value={filterRole}
          onChange={(e) => setFilterRole(e.target.value)}
          className="rounded-lg border border-stone-200 px-3 py-1.5 text-xs bg-white outline-none focus:border-stone-400"
        >
          <option value="">All roles</option>
          <option value="FARMER">Farmer</option>
          <option value="COOPERATIVE_MANAGER">Cooperative Manager</option>
          <option value="EXPORTER">Exporter</option>
          <option value="BUYER">Buyer</option>
          <option value="ADMIN">Admin</option>
        </select>

        <select
          value={filterApproved}
          onChange={(e) => setFilterApproved(e.target.value)}
          className="rounded-lg border border-stone-200 px-3 py-1.5 text-xs bg-white outline-none focus:border-stone-400"
        >
          <option value="">Any status</option>
          <option value="true">Approved</option>
          <option value="false">Pending</option>
        </select>

        {data && <span className="text-xs text-stone-400 ml-auto">{data.total} users</span>}
      </div>

      <div className="flex gap-4">
        {/* User list */}
        <div className="flex-1 space-y-2 min-w-0">
          {loading ? <Skeleton rows={5} /> : users.length === 0 ? (
            <div className="text-center py-12 text-stone-400 text-sm">No users found.</div>
          ) : users.map((u) => (
            <button
              key={u.id}
              onClick={() => openDetail(u.id)}
              className={`w-full text-left relative overflow-hidden bg-white rounded-xl border transition-all hover:shadow-md p-3 ${selected === u.id ? 'border-stone-400 ring-1 ring-stone-300' : 'border-stone-200'}`}
            >
              <TechCardBg variant="dotgrid" />
              <div className="relative z-10 flex items-center gap-3">
                <div className="w-8 h-8 rounded-full bg-stone-100 flex items-center justify-center text-xs font-bold text-stone-600 shrink-0">
                  {(u.name || '?')[0].toUpperCase()}
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="text-sm font-medium text-stone-900 truncate">{u.name || 'Unnamed'}</span>
                    <RoleBadge role={u.role} />
                  </div>
                  <p className="text-xs text-stone-500 truncate">{u.phone_number}</p>
                </div>
                <ApprovalBadge approved={u.is_approved} />
              </div>
            </button>
          ))}
        </div>

        {/* Detail panel */}
        {selected && (
          <div className="w-72 shrink-0 relative overflow-hidden bg-white rounded-xl border border-stone-200 p-4 self-start">
            <TechCardBg variant="hex" />
            <div className="relative z-10">
              {detailLoading ? (
                <div className="space-y-3 animate-pulse">
                  <div className="h-4 bg-stone-200 rounded w-2/3" />
                  <div className="h-3 bg-stone-100 rounded w-1/2" />
                  <div className="h-3 bg-stone-100 rounded w-3/4" />
                </div>
              ) : detail ? (
                <>
                  <div className="flex items-start justify-between mb-3">
                    <div>
                      <p className="text-sm font-semibold text-stone-900">{detail.name || 'Unnamed'}</p>
                      <p className="text-xs text-stone-500">{detail.phone_number}</p>
                    </div>
                    <button onClick={() => setSelected(null)} className="text-stone-400 hover:text-stone-700 transition">
                      <IconX className="w-4 h-4" />
                    </button>
                  </div>

                  <dl className="space-y-1.5 text-xs mb-4">
                    {[
                      ['ID', detail.id],
                      ['Role', <RoleBadge key="r" role={detail.role} />],
                      ['Approved', <ApprovalBadge key="a" approved={detail.is_approved} />],
                      ['Organization', detail.organization || '—'],
                      ['Language', detail.preferred_language],
                      ['Batches', detail.batches_count],
                      ['DID', detail.did ? detail.did.slice(0, 24) + '...' : '—'],
                    ].map(([label, val]) => (
                      <div key={label} className="flex justify-between gap-2">
                        <dt className="text-stone-400 shrink-0">{label}</dt>
                        <dd className="text-stone-700 text-right break-all">{val}</dd>
                      </div>
                    ))}
                  </dl>

                  {editing ? (
                    <div className="space-y-2">
                      <div>
                        <label className="block text-xs font-medium text-stone-600 mb-1">Language</label>
                        <select
                          value={editForm.preferred_language || 'en'}
                          onChange={(e) => setEditForm((f) => ({ ...f, preferred_language: e.target.value }))}
                          className="w-full rounded-lg border border-stone-200 px-2 py-1 text-xs bg-stone-50 outline-none"
                        >
                          <option value="en">English</option>
                          <option value="am">Amharic</option>
                        </select>
                      </div>
                      <div className="flex gap-1.5">
                        <button
                          onClick={handleSave}
                          disabled={saving}
                          className="flex-1 py-1.5 rounded-lg bg-stone-900 text-white text-xs font-medium transition disabled:opacity-50"
                        >
                          {saving ? 'Saving...' : 'Save'}
                        </button>
                        <button
                          onClick={() => setEditing(false)}
                          className="flex-1 py-1.5 rounded-lg border border-stone-200 text-xs text-stone-600 hover:bg-stone-50 transition"
                        >
                          Cancel
                        </button>
                      </div>
                    </div>
                  ) : (
                    <button
                      onClick={() => setEditing(true)}
                      className="w-full py-1.5 rounded-lg border border-stone-200 text-xs font-medium text-stone-700 hover:bg-stone-50 transition"
                    >
                      Edit Profile
                    </button>
                  )}
                </>
              ) : null}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

// ── Marketplace tab ───────────────────────────────────────────────

function MarketplaceTab() {
  const [subTab, setSubTab] = useState('rfqs')
  const [rfqs, setRfqs] = useState(null)
  const [offers, setOffers] = useState(null)
  const [settlements, setSettlements] = useState(null)
  const [loading, setLoading] = useState(false)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const [r, o, s] = await Promise.all([
        getAdminRFQs({ limit: 100 }),
        getAdminOffers({ limit: 100 }),
        getAdminSettlements({ limit: 100 }),
      ])
      setRfqs(r)
      setOffers(o)
      setSettlements(s)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { load() }, [load])

  const SUB_TABS = [
    { key: 'rfqs',        label: `RFQs (${rfqs?.total ?? '...'})` },
    { key: 'offers',      label: `Offers (${offers?.total ?? '...'})` },
    { key: 'settlements', label: `Settlements (${settlements?.total ?? '...'})` },
  ]

  const STATUS_COLORS_RFQ = {
    ACTIVE:   'bg-blue-100 text-blue-700',
    ACCEPTED: 'bg-green-100 text-green-700',
    EXPIRED:  'bg-stone-100 text-stone-500',
    CLOSED:   'bg-red-100 text-red-600',
  }

  return (
    <div className="space-y-4">
      {/* Sub-tab pills */}
      <div className="flex gap-2 flex-wrap">
        {SUB_TABS.map(({ key, label }) => (
          <button
            key={key}
            onClick={() => setSubTab(key)}
            className={`px-3 py-1.5 rounded-lg text-xs font-medium transition ${subTab === key ? 'bg-stone-900 text-white' : 'bg-white border border-stone-200 text-stone-600 hover:bg-stone-50'}`}
          >
            {label}
          </button>
        ))}
        <button onClick={load} className="flex items-center gap-1.5 text-xs text-stone-500 hover:text-stone-800 transition ml-auto">
          <IconRefreshCw className="w-3.5 h-3.5" /> Refresh
        </button>
      </div>

      {loading ? <Skeleton rows={5} /> : (
        <>
          {/* RFQs */}
          {subTab === 'rfqs' && (
            <div className="overflow-x-auto rounded-xl border border-stone-200">
              <table className="w-full text-xs">
                <thead className="bg-stone-50 border-b border-stone-200">
                  <tr>
                    {['ID', 'Buyer', 'Qty (kg)', 'Grade', 'Status', 'Offers'].map((h) => (
                      <th key={h} className="text-left px-4 py-2.5 text-stone-500 font-medium tracking-wide">{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-stone-100">
                  {(rfqs?.rfqs || []).map((r) => (
                    <tr key={r.id} className="bg-white hover:bg-stone-50 transition">
                      <td className="px-4 py-2.5 font-mono text-stone-600">{r.id}</td>
                      <td className="px-4 py-2.5 text-stone-700">{r.buyer_name || r.buyer_id}</td>
                      <td className="px-4 py-2.5 font-mono">{r.quantity_kg?.toLocaleString()}</td>
                      <td className="px-4 py-2.5 text-stone-600">{r.grade || '—'}</td>
                      <td className="px-4 py-2.5">
                        <span className={`rounded-full px-2 py-0.5 font-medium ${STATUS_COLORS_RFQ[r.status] || 'bg-stone-100 text-stone-600'}`}>{r.status}</span>
                      </td>
                      <td className="px-4 py-2.5 font-mono">{r.offers_count}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {!rfqs?.rfqs?.length && <p className="text-center py-8 text-stone-400 text-sm">No RFQs.</p>}
            </div>
          )}

          {/* Offers */}
          {subTab === 'offers' && (
            <div className="overflow-x-auto rounded-xl border border-stone-200">
              <table className="w-full text-xs">
                <thead className="bg-stone-50 border-b border-stone-200">
                  <tr>
                    {['ID', 'RFQ', 'Cooperative', 'Price/kg', 'Status'].map((h) => (
                      <th key={h} className="text-left px-4 py-2.5 text-stone-500 font-medium tracking-wide">{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-stone-100">
                  {(offers?.offers || []).map((o) => (
                    <tr key={o.id} className="bg-white hover:bg-stone-50 transition">
                      <td className="px-4 py-2.5 font-mono text-stone-600">{o.id}</td>
                      <td className="px-4 py-2.5 font-mono">{o.rfq_id}</td>
                      <td className="px-4 py-2.5 text-stone-700">{o.cooperative_id}</td>
                      <td className="px-4 py-2.5 font-mono">${o.price_per_kg?.toFixed(2)}</td>
                      <td className="px-4 py-2.5">
                        <span className="rounded-full px-2 py-0.5 font-medium bg-stone-100 text-stone-600">{o.status}</span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {!offers?.offers?.length && <p className="text-center py-8 text-stone-400 text-sm">No offers.</p>}
            </div>
          )}

          {/* Settlements */}
          {subTab === 'settlements' && (
            <div className="overflow-x-auto rounded-xl border border-stone-200">
              <table className="w-full text-xs">
                <thead className="bg-stone-50 border-b border-stone-200">
                  <tr>
                    {['ID', 'Acceptance #', 'Qty (kg)', 'Payment', 'Delivery', 'TX Hash'].map((h) => (
                      <th key={h} className="text-left px-4 py-2.5 text-stone-500 font-medium tracking-wide">{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-stone-100">
                  {(settlements?.settlements || []).map((s) => (
                    <tr key={s.id} className="bg-white hover:bg-stone-50 transition">
                      <td className="px-4 py-2.5 font-mono text-stone-600">{s.id}</td>
                      <td className="px-4 py-2.5 font-mono text-stone-600">{s.acceptance_number}</td>
                      <td className="px-4 py-2.5 font-mono">{s.quantity_accepted_kg?.toLocaleString()}</td>
                      <td className="px-4 py-2.5">
                        <span className={`rounded-full px-2 py-0.5 font-medium ${s.payment_status === 'SETTLED' ? 'bg-green-100 text-green-700' : 'bg-amber-100 text-amber-700'}`}>{s.payment_status}</span>
                      </td>
                      <td className="px-4 py-2.5">
                        <span className={`rounded-full px-2 py-0.5 font-medium ${s.delivery_status === 'DELIVERED' ? 'bg-green-100 text-green-700' : 'bg-blue-100 text-blue-700'}`}>{s.delivery_status}</span>
                      </td>
                      <td className="px-4 py-2.5 font-mono text-stone-400 truncate max-w-20">
                        {s.settlement_tx_hash ? s.settlement_tx_hash.slice(0, 12) + '...' : '—'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {!settlements?.settlements?.length && <p className="text-center py-8 text-stone-400 text-sm">No settlements.</p>}
            </div>
          )}
        </>
      )}
    </div>
  )
}

// ── UAT Issues tab ────────────────────────────────────────────────

function UATTab() {
  const [filterStatus, setFilterStatus] = useState('')
  const [filterSeverity, setFilterSeverity] = useState('')
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(false)
  const [updating, setUpdating] = useState({})
  const [expanded, setExpanded] = useState(null)
  const [toast, setToast] = useState(null)

  const showToast = (msg, ok = true) => {
    setToast({ msg, ok })
    setTimeout(() => setToast(null), 3000)
  }

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const params = { limit: 100 }
      if (filterStatus) params.status = filterStatus
      if (filterSeverity) params.severity = filterSeverity
      const res = await listUATIssues(params)
      setData(res)
    } catch (err) {
      showToast(`Load failed: ${err.message}`, false)
    } finally {
      setLoading(false)
    }
  }, [filterStatus, filterSeverity])

  useEffect(() => { load() }, [load])

  const handleStatusChange = async (issueId, newStatus) => {
    setUpdating((s) => ({ ...s, [issueId]: true }))
    try {
      await updateUATIssue(issueId, { status: newStatus })
      showToast(`Issue #${issueId} marked as ${newStatus}`)
      load()
    } catch (err) {
      showToast(`Update failed: ${err.message}`, false)
    } finally {
      setUpdating((s) => ({ ...s, [issueId]: false }))
    }
  }

  const issues = data?.issues || []

  return (
    <div className="space-y-4">
      {toast && (
        <div className={`fixed top-20 right-4 z-50 px-4 py-2.5 rounded-xl text-sm font-medium shadow-lg animate-fade-in-up ${toast.ok ? 'bg-green-600 text-white' : 'bg-red-600 text-white'}`}>
          {toast.msg}
        </div>
      )}

      {/* Filters */}
      <div className="flex flex-wrap gap-3 items-center">
        <select
          value={filterStatus}
          onChange={(e) => setFilterStatus(e.target.value)}
          className="rounded-lg border border-stone-200 px-3 py-1.5 text-xs bg-white outline-none focus:border-stone-400"
        >
          <option value="">All statuses</option>
          <option value="open">Open</option>
          <option value="in_progress">In Progress</option>
          <option value="fixed">Fixed</option>
          <option value="verified">Verified</option>
          <option value="wont_fix">Won't Fix</option>
        </select>

        <select
          value={filterSeverity}
          onChange={(e) => setFilterSeverity(e.target.value)}
          className="rounded-lg border border-stone-200 px-3 py-1.5 text-xs bg-white outline-none focus:border-stone-400"
        >
          <option value="">All severities</option>
          <option value="blocker">Blocker</option>
          <option value="major">Major</option>
          <option value="minor">Minor</option>
          <option value="cosmetic">Cosmetic</option>
        </select>

        <button onClick={load} className="flex items-center gap-1.5 text-xs text-stone-500 hover:text-stone-800 transition">
          <IconRefreshCw className="w-3.5 h-3.5" /> Refresh
        </button>

        {data && <span className="text-xs text-stone-400 ml-auto">{data.total} issues</span>}
      </div>

      {/* Issue list */}
      {loading ? <Skeleton rows={5} /> : issues.length === 0 ? (
        <div className="text-center py-12 text-stone-400 text-sm">No UAT issues found.</div>
      ) : (
        <div className="space-y-3">
          {issues.map((issue) => (
            <div key={issue.id} className="relative overflow-hidden bg-white rounded-xl border border-stone-200 hover:shadow-md transition-all">
              <TechCardBg variant="dotgrid" />
              <div className="relative z-10">
                {/* Summary row */}
                <button
                  onClick={() => setExpanded(expanded === issue.id ? null : issue.id)}
                  className="w-full text-left px-4 py-3 flex flex-wrap items-center gap-3"
                >
                  <div className="flex-1 min-w-0 space-y-0.5">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="text-sm font-medium text-stone-900 truncate">{issue.title}</span>
                      <SeverityBadge severity={issue.severity} />
                      <UATStatusBadge status={issue.status} />
                    </div>
                    <p className="text-xs text-stone-500">{issue.page} · {issue.category} · {issue.user_name || 'Anonymous'}</p>
                    <p className="text-xs text-stone-400">{issue.created_at ? new Date(issue.created_at).toLocaleString() : ''}</p>
                  </div>
                  <IconInfo className="w-4 h-4 text-stone-400 shrink-0" />
                </button>

                {/* Expanded detail */}
                {expanded === issue.id && (
                  <div className="px-4 pb-4 border-t border-stone-100 pt-3 space-y-3">
                    <p className="text-sm text-stone-700 whitespace-pre-wrap">{issue.description}</p>

                    {issue.browser_info && (
                      <p className="text-xs text-stone-400 font-mono break-all">{issue.browser_info}</p>
                    )}

                    {issue.console_errors?.length > 0 && (
                      <details className="text-xs">
                        <summary className="cursor-pointer text-stone-500 hover:text-stone-800">
                          {issue.console_errors.length} console error(s)
                        </summary>
                        <div className="mt-2 space-y-1 bg-stone-50 rounded-lg p-2 font-mono text-[10px] text-red-600 max-h-32 overflow-y-auto">
                          {issue.console_errors.map((e, i) => (
                            <p key={i}>{e.ts} — {e.message}</p>
                          ))}
                        </div>
                      </details>
                    )}

                    {issue.resolution_notes && (
                      <div className="bg-teal-50 border border-teal-100 rounded-lg p-3 text-xs text-teal-700">
                        <span className="font-semibold">Resolution: </span>{issue.resolution_notes}
                      </div>
                    )}

                    {/* Status actions */}
                    <div className="flex flex-wrap gap-1.5">
                      {['in_progress', 'fixed', 'verified', 'wont_fix'].map((s) => (
                        <button
                          key={s}
                          disabled={issue.status === s || updating[issue.id]}
                          onClick={() => handleStatusChange(issue.id, s)}
                          className={`px-2.5 py-1 rounded-lg text-xs font-medium transition disabled:opacity-40 ${issue.status === s ? 'bg-stone-900 text-white' : 'border border-stone-200 text-stone-600 hover:bg-stone-50'}`}
                        >
                          {updating[issue.id] ? '...' : s.replace(/_/g, ' ')}
                        </button>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

// ── Main page ─────────────────────────────────────────────────────

const TABS = [
  { key: 'overview',      label: 'Overview',      icon: IconChartBar },
  { key: 'registrations', label: 'Registrations', icon: IconUsers },
  { key: 'users',         label: 'Users',         icon: IconShieldCheck },
  { key: 'marketplace',   label: 'Marketplace',   icon: IconHandshake },
  { key: 'uat',           label: 'UAT Issues',    icon: IconFileText },
]

export default function Admin() {
  const { t } = useTranslation()
  const { isAuthenticated, user } = useAuthStore()
  const [activeTab, setActiveTab] = useState('overview')

  // Guard: must be logged in as ADMIN or SYSTEM_ADMIN
  if (!isAuthenticated) {
    return <Navigate to="/login" replace />
  }
  if (user?.role !== 'ADMIN' && user?.role !== 'SYSTEM_ADMIN') {
    return (
      <div className="min-h-[calc(100dvh-4rem)] flex items-center justify-center px-4">
        <div className="text-center space-y-3">
          <IconCircleX className="w-12 h-12 text-red-400 mx-auto" />
          <h1 className="text-xl font-bold text-stone-900">Access Denied</h1>
          <p className="text-sm text-stone-500">Admin access is required to view this page.</p>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-[calc(100dvh-4rem)]">
      {/* Page hero header */}
      <div className="relative overflow-hidden bg-white border-b border-stone-100 py-8 px-4 md:px-8">
        <PageHeroBg variant="compliance" className="absolute inset-0 text-stone-500 opacity-60" />
        <div className="relative z-10 max-w-6xl mx-auto">
          <div className="flex items-center gap-3 mb-1">
            <IconShieldCheck className="w-5 h-5 text-stone-600" />
            <p className="text-xs font-semibold text-stone-500 uppercase tracking-widest">Administration</p>
          </div>
          <h1 className="text-3xl font-bold text-stone-900 page-header-accent">Admin Dashboard</h1>
          <p className="text-sm text-stone-500 mt-1">
            Manage registrations, users, marketplace activity, and UAT reports.
          </p>
        </div>
      </div>

      {/* Content */}
      <div className="max-w-6xl mx-auto px-4 md:px-8 py-6 space-y-6">
        {/* Tab bar */}
        <div className="flex gap-1 overflow-x-auto border-b border-stone-200 pb-0">
          {TABS.map(({ key, label, icon: Icon }) => (
            <button
              key={key}
              onClick={() => setActiveTab(key)}
              className={`flex items-center gap-1.5 px-4 py-2.5 text-sm font-medium whitespace-nowrap border-b-2 transition-colors ${
                activeTab === key
                  ? 'border-stone-900 text-stone-900'
                  : 'border-transparent text-stone-500 hover:text-stone-800'
              }`}
            >
              <Icon className="w-4 h-4" />
              {label}
            </button>
          ))}
        </div>

        {/* Tab content */}
        {activeTab === 'overview'      && <OverviewTab />}
        {activeTab === 'registrations' && <RegistrationsTab />}
        {activeTab === 'users'         && <UsersTab />}
        {activeTab === 'marketplace'   && <MarketplaceTab />}
        {activeTab === 'uat'           && <UATTab />}
      </div>
    </div>
  )
}
