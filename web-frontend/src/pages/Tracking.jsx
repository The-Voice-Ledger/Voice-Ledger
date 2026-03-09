import { useState, useEffect } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useSearchParams } from 'react-router-dom'
import {
  LuShip, LuSearch, LuMessageCircle, LuPackageCheck, LuMapPin,
  LuAnchor, LuCircleCheck, LuCircleDot, LuCircle, LuInfo,
} from 'react-icons/lu'
import { getShipmentStatus } from '../api/logistics'

/* ── Shimmer skeleton ───────────────────────────────────────────── */

function TrackingSkeleton() {
  return (
    <div className="space-y-6 animate-pulse">
      <div className="bg-white rounded-xl border border-stone-200 p-5">
        <div className="h-3 w-48 bg-stone-200 rounded mb-3" />
        <div className="h-5 w-28 bg-stone-200 rounded mb-2" />
        <div className="h-3 w-32 bg-stone-100 rounded" />
      </div>
      <div className="bg-white rounded-xl border border-stone-200 p-6">
        <div className="h-4 w-40 bg-stone-200 rounded mb-5" />
        {[...Array(3)].map((_, i) => (
          <div key={i} className="flex gap-3 mb-5">
            <div className="w-7 h-7 rounded-full bg-stone-200 shrink-0" />
            <div className="flex-1">
              <div className="h-4 w-32 bg-stone-200 rounded mb-2" />
              <div className="h-3 w-48 bg-stone-100 rounded" />
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

/* ── Milestone icon / colour mapping ────────────────────────────── */

const MILESTONE_META = {
  PICKUP:                   { icon: LuPackageCheck, color: 'text-green-600',  bg: 'bg-green-100', label: 'Pickup' },
  PORT_ARRIVAL_ORIGIN:      { icon: LuAnchor,       color: 'text-blue-600',   bg: 'bg-blue-100',  label: 'Port of Origin' },
  VESSEL_DEPARTURE:         { icon: LuShip,         color: 'text-indigo-600', bg: 'bg-indigo-100', label: 'Vessel Departed' },
  TRANSSHIPMENT:            { icon: LuShip,         color: 'text-purple-600', bg: 'bg-purple-100', label: 'Transshipment' },
  PORT_ARRIVAL_DESTINATION: { icon: LuAnchor,       color: 'text-teal-600',   bg: 'bg-teal-100',  label: 'Port of Destination' },
  CUSTOMS_CLEARED:          { icon: LuCircleCheck, color: 'text-amber-600',  bg: 'bg-amber-100', label: 'Customs Cleared' },
  DELIVERED:                { icon: LuPackageCheck, color: 'text-green-700',  bg: 'bg-green-200', label: 'Delivered' },
}

const DELIVERY_COLORS = {
  PENDING:             'bg-stone-100 text-stone-600',
  PREPARING_SHIPMENT:  'bg-yellow-100 text-yellow-700',
  SHIPPED:             'bg-blue-100 text-blue-700',
  IN_TRANSIT:          'bg-indigo-100 text-indigo-700',
  CUSTOMS_HOLD:        'bg-amber-100 text-amber-700',
  CUSTOMS_CLEARED:     'bg-teal-100 text-teal-700',
  DELIVERED:           'bg-green-100 text-green-700',
}

function DeliveryBadge({ status }) {
  return (
    <span className={`text-xs font-medium rounded-full px-2.5 py-0.5 ${DELIVERY_COLORS[status] || 'bg-stone-100 text-stone-600'}`}>
      {status?.replace(/_/g, ' ') || 'UNKNOWN'}
    </span>
  )
}

/* ── Timeline component ────────────────────────────────────────── */

function Timeline({ milestones, events }) {
  const { t } = useTranslation()
  // Combine milestones and events, sort by time
  const allEvents = [
    ...(milestones || []).map((m) => ({
      ...m,
      source: 'milestone',
      sort_time: m.event_time || '',
      label: MILESTONE_META[m.milestone_type]?.label || m.milestone_type,
    })),
    ...(events || []).map((e) => ({
      ...e,
      source: 'event',
      sort_time: e.event_time || '',
      label: e.biz_step ? e.biz_step.replace(/_/g, ' ') : e.event_type,
    })),
  ].sort((a, b) => (a.sort_time || '').localeCompare(b.sort_time || ''))

  if (allEvents.length === 0) {
    return (
      <div className="text-center text-stone-400 py-8 text-sm">
        {t('track_no_events')}
      </div>
    )
  }

  return (
    <div className="relative pl-8">
      {/* Vertical line */}
      <div className="absolute left-3.5 top-2 bottom-2 w-0.5 bg-stone-200" />

      <div className="space-y-6">
        {allEvents.map((evt, i) => {
          const meta = evt.source === 'milestone'
            ? (MILESTONE_META[evt.milestone_type] || {})
            : {}
          const Icon = meta.icon || (i === allEvents.length - 1 ? LuCircleDot : LuCircle)
          const iconColor = meta.color || 'text-stone-400'
          const isLast = i === allEvents.length - 1

          return (
            <div key={i} className="relative flex gap-3">
              {/* Icon dot */}
              <div className={`absolute -left-8 top-0.5 w-7 h-7 rounded-full flex items-center justify-center ${meta.bg || 'bg-stone-100'}`}>
                <Icon className={`w-3.5 h-3.5 ${iconColor}`} />
              </div>

              {/* Content */}
              <div className={`flex-1 ${isLast ? '' : 'pb-0'}`}>
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="text-sm font-semibold text-stone-800 capitalize">{evt.label}</span>
                  {evt.source === 'milestone' && (
                    <span className="text-[10px] font-medium bg-blue-50 text-blue-600 rounded px-1.5 py-0.5">LSP</span>
                  )}
                </div>

                <p className="text-xs text-stone-500 mt-0.5">
                  {evt.event_time ? new Date(evt.event_time).toLocaleString() : 'Time unknown'}
                </p>

                {/* Extra details for milestones */}
                {evt.carrier && (
                  <p className="text-xs text-stone-400 mt-0.5">{t('track_carrier')}: {evt.carrier}</p>
                )}
                {evt.vessel_imo && (
                  <p className="text-xs text-stone-400">{t('track_vessel_imo')}: {evt.vessel_imo}</p>
                )}
                {evt.tracking_reference && (
                  <p className="text-xs text-stone-400">{t('track_tracking_ref')}: {evt.tracking_reference}</p>
                )}

                {/* Blockchain proof */}
                {evt.blockchain_tx_hash && (
                  <p className="text-xs text-stone-400 mt-1 flex items-center gap-1">
                    <LuCircleCheck className="w-3 h-3 text-green-500" />
                    <span className="font-mono truncate max-w-[200px]">{evt.blockchain_tx_hash}</span>
                  </p>
                )}
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}

/* ── Main page ──────────────────────────────────────────────────── */

export default function Tracking() {
  const { t } = useTranslation()
  const [searchParams] = useSearchParams()
  const [sscc, setSscc] = useState(searchParams.get('sscc') || '')
  const [loading, setLoading] = useState(false)
  const [shipment, setShipment] = useState(null)
  const [error, setError] = useState(null)

  const handleSearch = async (e) => {
    e?.preventDefault()
    if (!sscc.trim()) return
    setLoading(true)
    setError(null)
    setShipment(null)
    try {
      const result = await getShipmentStatus(sscc.trim())
      setShipment(result)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  const totalEvents = (shipment?.events?.length || 0) + (shipment?.milestones?.length || 0)

  // Auto-search if sscc query param is provided (e.g. linked from Marketplace or Compliance)
  useEffect(() => {
    if (searchParams.get('sscc')) {
      handleSearch()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  return (
    <div className="max-w-4xl mx-auto px-4 py-8">
      {/* Header */}
      <h1 className="text-2xl font-bold text-stone-900 flex items-center gap-2 mb-2">
        <LuShip className="w-6 h-6" /> {t('nav_tracking')}
      </h1>
      <p className="text-sm text-stone-500 mb-6">
        {t('track_subtitle')}
      </p>

      {/* Search */}
      <form onSubmit={handleSearch} className="flex flex-col sm:flex-row gap-2 mb-8">
        <div className="relative flex-1">
          <LuSearch className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-stone-400" />
          <input
            type="text"
            value={sscc}
            onChange={(e) => setSscc(e.target.value)}
            placeholder={t('track_placeholder')}
            className="w-full pl-9 pr-4 py-2.5 rounded-lg border border-stone-300 text-sm outline-none focus:border-stone-400 focus:ring-2 focus:ring-stone-200 transition"
          />
        </div>
        <button
          type="submit"
          disabled={!sscc.trim() || loading}
          className="bg-stone-900 text-white font-medium rounded-lg px-6 py-2.5 text-sm hover:bg-stone-800 hover:scale-105 active:scale-95 transition-all disabled:opacity-50 shrink-0"
        >
          {loading ? t('track_searching') : t('track_search')}
        </button>
      </form>

      {error && (
        <div className="text-sm text-red-600 bg-red-50 border border-red-100 rounded-lg p-3 mb-4">{error}</div>
      )}

      {/* Loading skeleton */}
      {loading && !shipment && <TrackingSkeleton />}

      {/* Shipment result */}
      {shipment && (
        <div className="space-y-6">
          {/* Status header */}
          <div className="bg-white rounded-xl border border-stone-200 p-5 hover:shadow-md transition-shadow">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
              <div>
                <p className="text-xs text-stone-400 font-mono mb-1">{shipment.container_sscc}</p>
                <div className="flex items-center gap-3">
                  <DeliveryBadge status={shipment.delivery_status} />
                  {shipment.variety && (
                    <span className="text-sm text-stone-600">{shipment.variety}</span>
                  )}
                </div>
              </div>
              <div className="text-right text-sm text-stone-600">
                {shipment.total_quantity_kg && (
                  <p><strong>{shipment.total_quantity_kg.toLocaleString()}</strong> kg</p>
                )}
                <p className="text-xs text-stone-400">{totalEvents} event{totalEvents !== 1 ? 's' : ''} recorded</p>
              </div>
            </div>
          </div>

          {/* Timeline */}
          <div className="bg-white rounded-xl border border-stone-200 p-6">
            <h2 className="text-sm font-bold text-stone-900 flex items-center gap-2 mb-5">
              <LuMapPin className="w-4 h-4 text-stone-500" /> {t('track_timeline')}
            </h2>
            <Timeline milestones={shipment.milestones} events={shipment.events} />
          </div>

          {/* Link to compliance */}
          <div className="flex gap-3">
            <Link
              to={`/compliance?sscc=${encodeURIComponent(shipment.container_sscc)}`}
              className="inline-flex items-center gap-1.5 text-sm text-stone-600 hover:text-stone-800 transition"
            >
              <LuCircleCheck className="w-4 h-4" /> {t('track_view_compliance')}
            </Link>
          </div>
        </div>
      )}

      {/* Empty state */}
      {!shipment && !loading && !error && (
        <div className="text-center text-stone-400 py-16">
          <div className="w-20 h-20 mx-auto mb-4 rounded-full bg-gradient-to-br from-blue-100 via-stone-100 to-teal-100 flex items-center justify-center">
            <LuShip className="w-10 h-10 text-stone-400" />
          </div>
          <p className="text-sm mb-4">{t('track_empty')}</p>
          <Link
            to="/assistant"
            className="inline-flex items-center gap-1.5 text-sm text-stone-600 hover:text-stone-700 hover:scale-105 active:scale-95 transition-all"
          >
            <LuMessageCircle className="w-4 h-4" /> {t('track_ask_assistant')}
          </Link>
        </div>
      )}

      {/* Explainer */}
      <div className="mt-12 bg-gradient-to-br from-stone-50 to-stone-100/60 rounded-xl p-6 border border-stone-200">
        <h2 className="text-lg font-bold text-stone-800 mb-3 flex items-center gap-2">
          <LuInfo className="w-5 h-5" /> {t('track_about_title')}
        </h2>
        <div className="text-sm text-stone-600 space-y-2 leading-relaxed">
          <p>{t('track_about_p1')}</p>
          <p>{t('track_about_p2')}</p>
        </div>
      </div>
    </div>
  )
}
