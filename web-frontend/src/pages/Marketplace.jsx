import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'
import {
  IconHandshake, IconPackage, IconRefreshCw, IconMessageCircle,
  IconUsers, IconShip, IconArrowRight, IconTrendingUp, IconBox,
} from '../components/svg/Icons'
import { listContainers, listPools, commitToPool } from '../api/marketplace'
import useAuthStore from '../stores/authStore'
import PageHeroBg from '../components/svg/PageHeroBg'
import ContainerFillSvg from '../components/svg/ContainerFillSvg'
import EmptyState from '../components/svg/EmptyState'
import TechCardBg from '../components/svg/TechCardBg'

/* ── Shared UI atoms ────────────────────────────────────────────── */

function StatusBadge({ status }) {
  const colors = {
    OPEN: 'bg-green-100 text-green-700',
    AVAILABLE: 'bg-green-100 text-green-700',
    FILLING: 'bg-blue-100 text-blue-700',
    CONFIRMED: 'bg-yellow-100 text-yellow-700',
    PARTIALLY_SOLD: 'bg-yellow-100 text-yellow-700',
    SHIPPED: 'bg-purple-100 text-purple-700',
    DELIVERED: 'bg-stone-100 text-stone-500',
    FULLY_RESERVED: 'bg-stone-100 text-stone-500',
  }
  return (
    <span className={`text-[10px] font-semibold uppercase tracking-wider rounded-full px-2.5 py-0.5 ${colors[status] || 'bg-stone-100 text-stone-600'}`}>
      {status?.replace(/_/g, ' ')}
    </span>
  )
}

function FillBar({ pct }) {
  const color =
    pct >= 80 ? 'bg-green-500' :
    pct >= 50 ? 'bg-yellow-500' :
    'bg-blue-500'
  return (
    <div className="w-full bg-stone-100 rounded-full h-2 overflow-hidden" title={`${pct}% filled`}>
      <div className={`h-full rounded-full transition-all duration-700 ease-out ${color}`} style={{ width: `${Math.min(pct, 100)}%` }} />
    </div>
  )
}

/** Shimmer skeleton for loading state */
function SkeletonCard() {
  return (
    <div className="bg-white rounded-xl border border-stone-200 p-5 space-y-3 animate-pulse">
      <div className="flex justify-between">
        <div className="space-y-1.5">
          <div className="h-3 w-28 bg-stone-200 rounded" />
          <div className="h-4 w-36 bg-stone-200 rounded" />
        </div>
        <div className="h-5 w-16 bg-stone-200 rounded-full" />
      </div>
      <div className="h-2 w-full bg-stone-100 rounded-full" />
      <div className="grid grid-cols-2 gap-2">
        <div className="h-3 bg-stone-100 rounded" />
        <div className="h-3 bg-stone-100 rounded" />
      </div>
    </div>
  )
}

/* ── Pool card ──────────────────────────────────────────────────── */

function PoolCard({ pool, onCommit }) {
  return (
    <div className="relative overflow-hidden bg-white rounded-xl border border-stone-200 p-5 flex flex-col gap-3 hover:shadow-lg hover:-translate-y-0.5 transition-all duration-200">
      <TechCardBg variant="dotgrid" />
      {/* Header */}
      <div className="relative z-10 flex items-start justify-between">
        <div>
          {pool.container_sscc ? (
            <Link to={`/tracking?sscc=${pool.container_sscc}`} className="text-xs text-stone-400 font-mono hover:text-stone-700 hover:underline transition">
              {pool.container_sscc}
            </Link>
          ) : (
            <p className="text-xs text-stone-400 font-mono">Pool</p>
          )}
          <p className="text-sm font-semibold text-stone-900">{pool.cooperative_name || pool.cooperative || 'Cooperative'}</p>
        </div>
        <StatusBadge status={pool.status} />
      </div>

      {/* Details */}
      <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-xs text-stone-500">
        {pool.variety && <span>Variety: <strong className="text-stone-700">{pool.variety}</strong></span>}
        {pool.grade && <span>Grade: <strong className="text-stone-700">{pool.grade}</strong></span>}
        <span>Price: <strong className="text-stone-700 font-mono">${pool.price_per_kg}/kg</strong></span>
        <span>Region: <strong className="text-stone-700">{pool.destination_region}</strong></span>
      </div>

      {/* Fill progress */}
      <div>
        <div className="flex justify-between text-xs text-stone-500 mb-1">
          <span>{pool.filled_kg?.toLocaleString()} / {pool.fill_target_kg?.toLocaleString()} kg</span>
          <span className="font-semibold text-stone-700">{pool.fill_pct ?? 0}%</span>
        </div>
        <ContainerFillSvg pct={pool.fill_pct ?? 0} height={32} />
      </div>

      {/* Buyers + deadline */}
      <div className="flex items-center justify-between text-xs text-stone-400">
        <span className="flex items-center gap-1"><IconUsers className="w-3.5 h-3.5" /> {pool.buyer_count ?? 0} buyers</span>
        {pool.deadline && <span>Deadline: {new Date(pool.deadline).toLocaleDateString()}</span>}
      </div>

      {/* CTA */}
      {pool.status === 'FILLING' && onCommit && (
        <button
          onClick={() => onCommit(pool)}
          className="mt-1 w-full text-sm font-medium bg-stone-900 text-white rounded-lg py-2 hover:bg-stone-800 active:scale-[0.98] transition-all flex items-center justify-center gap-1"
        >
          <IconShip className="w-4 h-4" /> Join this pool
        </button>
      )}
    </div>
  )
}

/* ── Commit modal ───────────────────────────────────────────────── */

function CommitModal({ pool, onClose, onSubmit, submitting }) {
  const { t } = useTranslation()
  const [qty, setQty] = useState('')
  const [country, setCountry] = useState('')
  const [city, setCity] = useState('')

  // Support both pool shape and raw container shape
  const isContainer = !pool.destination_region
  const offeringId = pool.container_offering_id || pool.id
  const price = pool?.price_per_kg ?? 0
  const maxKg = pool.remaining_kg ?? pool.available_quantity_kg ?? 0
  const total = qty ? (parseFloat(qty) * price).toFixed(2) : '0.00'

  const subtitle = isContainer
    ? `${pool.cooperative_name || 'Cooperative'} - ${pool.variety || 'Coffee'}`
    : `${pool.cooperative_name || pool.cooperative || ''} - ${pool.variety || ''} | ${pool.destination_region} via ${pool.destination_port}`

  return (
    <div className="fixed inset-0 z-50 bg-black/40 backdrop-blur-sm flex items-center justify-center p-4" onClick={onClose}>
      <div
        className="bg-white rounded-2xl shadow-xl max-w-md w-full p-6 animate-fade-in-up"
        onClick={(e) => e.stopPropagation()}
      >
        <h3 className="text-lg font-bold text-stone-900 mb-1">{isContainer ? t('mkt_buy_container') : t('mkt_join_pool')}</h3>
        <p className="text-xs text-stone-500 mb-4">{subtitle}</p>

        {isContainer && (
          <div className="text-xs text-stone-500 bg-blue-50 border border-blue-100 rounded-lg p-2.5 mb-3">
            {t('mkt_pool_auto_note')}
          </div>
        )}

        <div className="space-y-3">
          <div>
            <label className="block text-xs font-medium text-stone-600 mb-1">
              Quantity (kg) - max {maxKg?.toLocaleString()} kg available
            </label>
            <input
              type="number"
              min="1"
              max={pool.remaining_kg}
              value={qty}
              onChange={(e) => setQty(e.target.value)}
              className="w-full border border-stone-200 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-stone-300 outline-none"
              placeholder="e.g. 1000"
            />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-medium text-stone-600 mb-1">Delivery country code</label>
              <input
                type="text"
                maxLength={2}
                value={country}
                onChange={(e) => setCountry(e.target.value.toUpperCase())}
                className="w-full border border-stone-200 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-stone-300 outline-none uppercase"
                placeholder="US"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-stone-600 mb-1">Delivery city</label>
              <input
                type="text"
                value={city}
                onChange={(e) => setCity(e.target.value)}
                className="w-full border border-stone-200 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-stone-300 outline-none"
                placeholder="New York"
              />
            </div>
          </div>

          <div className="bg-stone-50 rounded-lg p-3 text-sm">
            <div className="flex justify-between">
              <span className="text-stone-500">Unit price</span>
              <span className="font-medium text-stone-900">${price}/kg</span>
            </div>
            <div className="flex justify-between mt-1">
              <span className="text-stone-500">Estimated total</span>
              <span className="font-bold text-stone-900">${Number(total).toLocaleString()}</span>
            </div>
          </div>
        </div>

        <div className="flex gap-3 mt-5">
          <button
            onClick={onClose}
            className="flex-1 py-2 text-sm font-medium text-stone-600 border border-stone-200 rounded-lg hover:bg-stone-50 transition"
          >
            Cancel
          </button>
          <button
            disabled={!qty || parseFloat(qty) <= 0 || parseFloat(qty) > maxKg || (!isContainer && !country) || submitting}
            onClick={() => onSubmit({
              container_offering_id: offeringId,
              quantity_kg: parseFloat(qty),
              delivery_country: country || undefined,
              delivery_city: city || undefined,
            })}
            className="flex-1 py-2 text-sm font-medium bg-stone-900 text-white rounded-lg hover:bg-stone-800 transition disabled:opacity-40"
          >
            {submitting ? 'Committing…' : 'Confirm'}
          </button>
        </div>
      </div>
    </div>
  )
}

/* ── Main page ──────────────────────────────────────────────────── */

export default function Marketplace() {
  const { t } = useTranslation()
  const { isAuthenticated } = useAuthStore()
  const [tab, setTab] = useState('pools')
  const [containers, setContainers] = useState([])
  const [pools, setPools] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [commitPool, setCommitPool] = useState(null)
  const [submitting, setSubmitting] = useState(false)

  const load = async () => {
    setLoading(true)
    setError(null)
    try {
      const [c, p] = await Promise.all([
        listContainers().catch(() => []),
        listPools().catch(() => ({ pools: [] })),
      ])
      setContainers(Array.isArray(c) ? c : [])
      setPools(Array.isArray(p) ? p : [])
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [])

  const handleCommit = async (data) => {
    setSubmitting(true)
    try {
      await commitToPool(data)
      setCommitPool(null)
      load()
    } catch (e) {
      setError(e.message)
    } finally {
      setSubmitting(false)
    }
  }

  // Aggregate stats
  const totalAvailableKg = containers.reduce((s, c) => s + (c.available_quantity_kg || 0), 0)
  const fillingPools = pools.filter((p) => p.status === 'FILLING').length

  return (
    <div className="max-w-6xl mx-auto px-4 py-8">
      {/* Header with stats */}
      <div className="relative flex flex-col sm:flex-row sm:items-end justify-between gap-4 mb-8">
        <PageHeroBg variant="marketplace" />
        <div>
          <h1 className="text-xl sm:text-2xl font-extrabold text-stone-900 flex items-center gap-2 page-header-accent">
            <IconHandshake className="w-6 h-6 shrink-0" /> {t('nav_marketplace')}
          </h1>
          <p className="text-sm text-stone-500 mt-1">{t('mkt_subtitle')}</p>
          {/* Live stat chips */}
          {!loading && (
            <div className="flex flex-wrap gap-2 mt-3">
              <span className="inline-flex items-center gap-1 text-xs bg-green-50 text-green-700 rounded-full px-2.5 py-1 font-medium">
                <IconBox className="w-3 h-3" /> {containers.length} {t('mkt_containers_tab').toLowerCase()}
              </span>
              <span className="inline-flex items-center gap-1 text-xs bg-blue-50 text-blue-700 rounded-full px-2.5 py-1 font-medium">
                <IconUsers className="w-3 h-3" /> {fillingPools} {t('mkt_active_pools')}
              </span>
              {totalAvailableKg > 0 && (
                <span className="inline-flex items-center gap-1 text-xs bg-amber-50 text-amber-700 rounded-full px-2.5 py-1 font-medium">
                  <IconTrendingUp className="w-3 h-3" /> {totalAvailableKg.toLocaleString()} kg {t('mkt_available')}
                </span>
              )}
            </div>
          )}
        </div>
        <div className="flex items-center gap-3 shrink-0">
          <button
            onClick={load}
            disabled={loading}
            className="inline-flex items-center gap-1 text-sm text-stone-500 hover:text-stone-700 transition"
          >
            <IconRefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} /> {t('mkt_refresh')}
          </button>
          <Link
            to="/assistant"
            className="inline-flex items-center gap-1 text-sm bg-stone-900 text-white rounded-full px-4 py-1.5 hover:bg-stone-800 hover:scale-105 active:scale-95 transition-all"
          >
            <IconMessageCircle className="w-4 h-4" /> {t('mkt_chat_buy')}
          </Link>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 border-b border-stone-200 mb-6">
        <button
          onClick={() => setTab('pools')}
          className={`px-4 py-2.5 text-sm font-medium border-b-2 transition-all ${
            tab === 'pools'
              ? 'border-stone-900 text-stone-900'
              : 'border-transparent text-stone-500 hover:text-stone-700'
          }`}
        >
          <IconUsers className="w-4 h-4 inline mr-1 -mt-0.5" />
          {t('mkt_pools_tab')} {!loading && <span className="ml-1 text-[10px] bg-stone-100 text-stone-500 rounded-full px-1.5 py-0.5">{pools.length}</span>}
        </button>
        <button
          onClick={() => setTab('containers')}
          className={`px-4 py-2.5 text-sm font-medium border-b-2 transition-all ${
            tab === 'containers'
              ? 'border-stone-900 text-stone-900'
              : 'border-transparent text-stone-500 hover:text-stone-700'
          }`}
        >
          <IconPackage className="w-4 h-4 inline mr-1 -mt-0.5" />
          {t('mkt_containers_tab')} {!loading && <span className="ml-1 text-[10px] bg-stone-100 text-stone-500 rounded-full px-1.5 py-0.5">{containers.length}</span>}
        </button>
      </div>

      {error && (
        <div className="text-sm text-red-600 bg-red-50 border border-red-100 rounded-lg p-3 mb-4">{error}</div>
      )}

      {/* Loading skeletons */}
      {loading && (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {[1, 2, 3, 4, 5, 6].map((i) => <SkeletonCard key={i} />)}
        </div>
      )}

      {/* Pools Grid */}
      {!loading && tab === 'pools' && (
        pools.length === 0 ? (
          <div className="bg-white rounded-xl border border-stone-200">
            <EmptyState
              variant="pools"
              message={t('mkt_no_pools')}
              sub={t('mkt_no_pools_hint')}
              actionLabel={t('mkt_chat_buy')}
              actionTo="/assistant"
            />
          </div>
        ) : (
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {pools.map((p) => (
              <PoolCard
                key={p.id}
                pool={p}
                onCommit={isAuthenticated ? setCommitPool : null}
              />
            ))}
          </div>
        )
      )}

      {/* Containers Table */}
      {!loading && tab === 'containers' && (
        <div className="bg-white rounded-xl border border-stone-200 overflow-hidden">
          {containers.length === 0 ? (
            <EmptyState
              variant="containers"
              message={t('mkt_no_containers')}
              sub={t('mkt_no_containers_hint')}
              actionLabel={t('mkt_chat_buy')}
              actionTo="/assistant"
            />
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="bg-stone-50/80 text-left text-[11px] text-stone-500 uppercase tracking-wider">
                  <tr>
                    <th className="px-4 py-3 font-semibold">SSCC</th>
                    <th className="px-4 py-3 font-semibold">{t('mkt_col_cooperative')}</th>
                    <th className="px-4 py-3 font-semibold">{t('mkt_col_variety')}</th>
                    <th className="px-4 py-3 font-semibold">{t('mkt_col_available')}</th>
                    <th className="px-4 py-3 font-semibold">{t('mkt_col_price')}</th>
                    <th className="px-4 py-3 font-semibold">{t('mkt_col_status')}</th>
                    <th className="px-4 py-3 text-right"></th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-stone-100">
                  {containers.map((c, idx) => (
                    <tr key={c.id} className={`hover:bg-stone-50/60 transition ${idx % 2 === 1 ? 'bg-stone-50/30' : ''}`}>
                      <td className="px-4 py-3">
                        <Link to={`/tracking?sscc=${c.container_sscc}`} className="font-mono text-xs text-stone-700 hover:text-stone-900 hover:underline transition">
                          {c.container_sscc}
                        </Link>
                      </td>
                      <td className="px-4 py-3 text-stone-600">{c.cooperative_name}</td>
                      <td className="px-4 py-3">{c.variety || '-'}</td>
                      <td className="px-4 py-3">
                        <span className="font-medium text-stone-700">{c.available_quantity_kg?.toLocaleString()}</span>
                        <span className="text-stone-400"> / {c.total_quantity_kg?.toLocaleString()} kg</span>
                      </td>
                      <td className="px-4 py-3 font-medium font-mono text-stone-900">${c.price_per_kg}/kg</td>
                      <td className="px-4 py-3"><StatusBadge status={c.status} /></td>
                      <td className="px-4 py-3 text-right">
                        {c.available_quantity_kg > 0 && (
                          isAuthenticated ? (
                            <button
                              onClick={() => setCommitPool(c)}
                              className="inline-flex items-center gap-1 text-xs font-medium bg-stone-900 text-white rounded-full px-3 py-1.5 hover:bg-stone-800 hover:scale-105 active:scale-95 transition-all"
                            >
                              <IconShip className="w-3.5 h-3.5" /> {t('mkt_buy')}
                            </button>
                          ) : (
                            <Link
                              to="/login"
                              className="text-xs text-stone-500 underline hover:text-stone-700 transition"
                            >
                              {t('mkt_sign_in_to_buy')}
                            </Link>
                          )
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* How it works - stepper with connecting lines */}
      <div className="mt-10 bg-gradient-to-br from-stone-50 to-stone-100/50 rounded-2xl p-6 sm:p-8 border border-stone-200">
        <h3 className="text-sm font-bold text-stone-900 mb-6 flex items-center gap-2">
          <IconShip className="w-4 h-4" /> {t('mkt_how_title')}
        </h3>
        <div className="relative grid sm:grid-cols-4 gap-6 sm:gap-4">
          {/* Connecting line (desktop) */}
          <div className="hidden sm:block absolute top-4 left-[calc(12.5%+16px)] right-[calc(12.5%+16px)] h-0.5 bg-stone-200" />
          {[
            { step: '1', label: t('mkt_step1_label'), desc: t('mkt_step1_desc') },
            { step: '2', label: t('mkt_step2_label'), desc: t('mkt_step2_desc') },
            { step: '3', label: t('mkt_step3_label'), desc: t('mkt_step3_desc') },
            { step: '4', label: t('mkt_step4_label'), desc: t('mkt_step4_desc') },
          ].map((s) => (
            <div key={s.step} className="relative flex flex-col items-center gap-2 text-center">
              <span className="relative z-10 w-8 h-8 rounded-full bg-stone-900 text-white text-sm font-bold flex items-center justify-center shadow-md">
                {s.step}
              </span>
              <p className="text-xs font-semibold text-stone-700">{s.label}</p>
              <p className="text-[11px] text-stone-500 leading-relaxed">{s.desc}</p>
            </div>
          ))}
        </div>
        <div className="text-center mt-6">
          <Link
            to="/assistant"
            className="inline-flex items-center gap-2 bg-stone-900 text-white font-semibold rounded-full px-6 py-2.5 hover:bg-stone-800 hover:scale-105 active:scale-95 transition-all text-sm shadow-md"
          >
            <IconMessageCircle className="w-4 h-4" /> {t('mkt_ask_assistant')} <IconArrowRight className="w-4 h-4" />
          </Link>
        </div>
      </div>

      {/* Commit modal */}
      {commitPool && (
        <CommitModal
          pool={commitPool}
          onClose={() => setCommitPool(null)}
          onSubmit={handleCommit}
          submitting={submitting}
        />
      )}
    </div>
  )
}
