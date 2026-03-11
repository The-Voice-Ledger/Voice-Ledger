import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'
import {
  IconLandmark, IconRefreshCw, IconMessageCircle, IconTrendingUp,
  IconChartBar, IconWallet, IconArrowRight, IconInfo, IconShieldCheck,
} from '../components/svg/Icons'
import { getPoolStats, getFeeStats, getTrade } from '../api/financing'
import useAuthStore from '../stores/authStore'
import PageHeroBg from '../components/svg/PageHeroBg'
import TechCardBg from '../components/svg/TechCardBg'

/* ── Stat card ──────────────────────────────────────────────────── */

function StatCard({ icon: Icon, label, value, sub, accent }) {
  return (
    <div className="relative overflow-hidden bg-white rounded-xl border border-stone-200 p-5 flex flex-col gap-1 hover:-translate-y-0.5 hover:shadow-lg transition-all duration-200">
      <TechCardBg variant="finance" />
      <div className="relative z-10 flex items-center gap-2 text-xs text-stone-400 uppercase tracking-wider">
        <Icon className={`w-4 h-4 ${accent || 'text-stone-400'}`} />
        {label}
      </div>
      <p className="relative z-10 text-2xl font-bold font-mono text-stone-900">{value}</p>
      {sub && <p className="relative z-10 text-xs text-stone-500">{sub}</p>}
    </div>
  )
}

/* ── Skeleton loader ────────────────────────────────────────────── */

function SkeletonCard() {
  return (
    <div className="bg-white rounded-xl border border-stone-200 p-5 animate-pulse">
      <div className="h-3 w-24 bg-stone-200 rounded mb-3" />
      <div className="h-7 w-32 bg-stone-200 rounded mb-2" />
      <div className="h-3 w-20 bg-stone-100 rounded" />
    </div>
  )
}

/* ── Trade status helpers ───────────────────────────────────────── */

const STATUS_COLORS = {
  ACTIVE: 'bg-blue-100 text-blue-700',
  SETTLED: 'bg-green-100 text-green-700',
  CANCELLED: 'bg-stone-100 text-stone-500',
  DEFAULTED: 'bg-red-100 text-red-700',
}

function TradeStatusBadge({ status }) {
  return (
    <span className={`text-xs font-medium rounded-full px-2 py-0.5 ${STATUS_COLORS[status] || 'bg-stone-100 text-stone-600'}`}>
      {status}
    </span>
  )
}

/* ── Trade lookup card ──────────────────────────────────────────── */

function TradeLookup() {
  const { t } = useTranslation()
  const [tradeId, setTradeId] = useState('')
  const [trade, setTrade] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  const handleSearch = async (e) => {
    e?.preventDefault()
    if (!tradeId.trim()) return
    setLoading(true)
    setError(null)
    setTrade(null)
    try {
      const result = await getTrade(parseInt(tradeId, 10))
      setTrade(result)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="bg-white rounded-xl border border-stone-200 p-6">
      <h3 className="text-sm font-bold text-stone-900 flex items-center gap-2 mb-3">
        <IconChartBar className="w-4 h-4 text-stone-500" /> {t('fin_trade_lookup')}
      </h3>

      <form onSubmit={handleSearch} className="flex flex-col sm:flex-row gap-2 mb-4">
        <input
          type="number"
          min="0"
          value={tradeId}
          onChange={(e) => setTradeId(e.target.value)}
          placeholder={t('fin_trade_placeholder')}
          className="flex-1 rounded-lg border border-stone-300 px-4 py-2.5 text-sm outline-none focus:border-stone-400 focus:ring-2 focus:ring-stone-200 transition"
        />
        <button
          type="submit"
          disabled={!tradeId.trim() || loading}
          className="bg-stone-900 text-white font-medium rounded-lg px-6 py-2.5 text-sm hover:bg-stone-800 hover:scale-105 active:scale-95 transition-all disabled:opacity-50 shrink-0"
        >
          {loading ? t('fin_loading') : t('fin_look_up')}
        </button>
      </form>

      {error && <div className="text-sm text-red-600 bg-red-50 border border-red-100 rounded-lg p-3 mb-3">{error}</div>}

      {trade && (
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <span className="text-sm font-semibold text-stone-800">Trade #{trade.trade_id}</span>
            <TradeStatusBadge status={trade.status} />
          </div>

          <div className="grid sm:grid-cols-2 gap-x-6 gap-y-2 text-sm">
            <Field label="Token ID" value={trade.token_id} />
            <Field label="Token Amount" value={trade.token_amount} />
            <Field label="Agreed Price" value={`$${trade.agreed_price_usdc?.toLocaleString()} USDC`} />
            <Field label="Advance" value={`$${trade.advance_amount_usdc?.toLocaleString()} USDC`} />
            <Field label="Fee" value={`${trade.fee_bps} bps ($${trade.fee_amount_usdc?.toLocaleString()})`} />
            <Field label="Farm ID" value={trade.farm_id || '-'} />
            <Field label="Seller" value={truncAddr(trade.seller)} />
            <Field label="Buyer" value={truncAddr(trade.buyer)} />
            <Field label="Created" value={formatUnix(trade.created_at)} />
            <Field label="Deadline" value={formatUnix(trade.deadline)} />
            {trade.settled_at > 0 && <Field label="Settled" value={formatUnix(trade.settled_at)} />}
          </div>
        </div>
      )}
    </div>
  )
}

/* ── Helpers ─────────────────────────────────────────────────────── */

function Field({ label, value }) {
  return (
    <div>
      <dt className="text-xs text-stone-500">{label}</dt>
      <dd className="font-medium text-stone-800 break-all">{value ?? '-'}</dd>
    </div>
  )
}

function truncAddr(addr) {
  if (!addr) return '-'
  if (addr.length <= 12) return addr
  return `${addr.slice(0, 6)}...${addr.slice(-4)}`
}

function formatUnix(ts) {
  if (!ts || ts === 0) return '-'
  return new Date(ts * 1000).toLocaleDateString('en-US', {
    year: 'numeric', month: 'short', day: 'numeric',
  })
}

function fmtUsd(n) {
  if (n == null) return '-'
  return `$${Number(n).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
}

function fmtPct(n) {
  if (n == null) return '-'
  return `${Number(n).toFixed(1)}%`
}

/* ── Main page ──────────────────────────────────────────────────── */

export default function Financing() {
  const { t } = useTranslation()
  const { isAuthenticated } = useAuthStore()
  const [pool, setPool] = useState(null)
  const [fees, setFees] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  const load = async () => {
    setLoading(true)
    setError(null)
    try {
      const [poolRes, feeRes] = await Promise.all([
        getPoolStats().catch(() => null),
        getFeeStats().catch(() => null),
      ])
      setPool(poolRes)
      setFees(feeRes)
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [])

  return (
    <div className="max-w-6xl mx-auto px-4 py-8">
      {/* Header */}
      <div className="relative flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-6">
        <PageHeroBg variant="financing" />
        <div>
          <h1 className="text-xl sm:text-2xl font-extrabold text-stone-900 flex items-center gap-2 page-header-accent">
            <IconLandmark className="w-6 h-6 shrink-0" /> {t('nav_financing')}
          </h1>
          <p className="text-sm text-stone-500 mt-1">
            {t('fin_subtitle')}
          </p>
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={load}
            disabled={loading}
            className="inline-flex items-center gap-1 text-sm text-stone-500 hover:text-stone-700 transition"
          >
            <IconRefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} /> {t('mkt_refresh')}
          </button>
          <Link
            to="/assistant"
            className="inline-flex items-center gap-1 text-sm bg-stone-900 text-white rounded-full px-4 py-1.5 hover:bg-stone-800 transition"
          >
            <IconMessageCircle className="w-4 h-4" /> {t('fin_ask_assistant')}
          </Link>
        </div>
      </div>

      {error && (
        <div className="text-sm text-red-600 bg-red-50 border border-red-100 rounded-lg p-3 mb-4">{error}</div>
      )}

      {loading && (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4 mb-8">
          {[...Array(4)].map((_, i) => <SkeletonCard key={i} />)}
        </div>
      )}

      {/* Pool stats grid */}
      {!loading && pool && (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4 mb-8">
          <StatCard
            icon={IconLandmark}
            label={t('fin_tvl')}
            value={fmtUsd(pool.total_assets_usdc)}
            sub={`${fmtUsd(pool.available_for_advance_usdc)} available`}
            accent="text-green-600"
          />
          <StatCard
            icon={IconTrendingUp}
            label={t('fin_utilisation')}
            value={fmtPct(pool.utilisation_pct)}
            sub={`${fmtUsd(pool.total_advanced_usdc)} advanced`}
            accent="text-blue-600"
          />
          <StatCard
            icon={IconWallet}
            label={t('fin_share_price')}
            value={fmtUsd(pool.share_price_usdc)}
            sub={`${Number(pool.total_shares || 0).toLocaleString()} vlUSDC shares`}
            accent="text-purple-600"
          />
          <StatCard
            icon={IconChartBar}
            label={t('fin_fees_collected')}
            value={fmtUsd(pool.cumulative_fees_usdc)}
            sub={fees ? `${fmtUsd(fees.total_to_investors_usdc)} to investors` : ''}
            accent="text-amber-600"
          />
        </div>
      )}

      {/* Pool unavailable */}
      {!loading && !pool && !error && (
        <div className="bg-amber-50 border border-amber-200 rounded-xl p-5 mb-8 flex items-start gap-3">
          <IconInfo className="w-5 h-5 text-amber-600 shrink-0 mt-0.5" />
          <div className="text-sm text-amber-800">
            <p className="font-semibold mb-1">{t('fin_unavailable_title')}</p>
            <p>{t('fin_unavailable_desc')}</p>
          </div>
        </div>
      )}

      {/* Fee breakdown (when available) */}
      {!loading && fees && (
        <div className="bg-white rounded-xl border border-stone-200 p-6 mb-8">
          <h3 className="text-sm font-bold text-stone-900 flex items-center gap-2 mb-4">
            <IconChartBar className="w-4 h-4 text-stone-500" /> {t('fin_fee_breakdown')}
          </h3>
          <div className="grid sm:grid-cols-3 gap-4">
            <FeeBar label={t('fin_fee_investors')} value={fees.total_to_investors_usdc} bps={fees.investor_bps} color="bg-green-500" />
            <FeeBar label={t('fin_fee_protocol')} value={fees.total_to_protocol_usdc} bps={fees.protocol_bps} color="bg-blue-500" />
            <FeeBar label={t('fin_fee_reserve')} value={fees.total_to_reserve_usdc} bps={fees.reserve_bps} color="bg-amber-500" />
          </div>
        </div>
      )}

      {/* Trade lookup */}
      <div className="mb-8">
        <TradeLookup />
      </div>

      {/* How it works */}
      <div className="bg-gradient-to-br from-stone-50 to-stone-100/60 rounded-xl p-6 border border-stone-200">
        <h3 className="text-sm font-bold text-stone-900 mb-3 flex items-center gap-2">
          <IconShieldCheck className="w-4 h-4" /> {t('fin_how_title')}
        </h3>
        <div className="relative grid sm:grid-cols-4 gap-4 text-center">
          {/* Connecting line */}
          <div className="hidden sm:block absolute top-4 left-[calc(12.5%+16px)] right-[calc(12.5%+16px)] h-0.5 bg-stone-300" />
          {[
            { step: '1', label: t('fin_step1_label'), desc: t('fin_step1_desc') },
            { step: '2', label: t('fin_step2_label'), desc: t('fin_step2_desc') },
            { step: '3', label: t('fin_step3_label'), desc: t('fin_step3_desc') },
            { step: '4', label: t('fin_step4_label'), desc: t('fin_step4_desc') },
          ].map((s) => (
            <div key={s.step} className="relative flex flex-col items-center gap-1">
              <span className="w-8 h-8 rounded-full bg-stone-900 text-white text-sm font-bold flex items-center justify-center z-10">{s.step}</span>
              <p className="text-xs font-semibold text-stone-700">{s.label}</p>
              <p className="text-xs text-stone-500">{s.desc}</p>
            </div>
          ))}
        </div>
        <div className="text-center mt-4">
          <Link
            to="/assistant"
            className="inline-flex items-center gap-2 bg-stone-900 text-white font-semibold rounded-full px-6 py-2.5 hover:bg-stone-800 hover:scale-105 active:scale-95 transition-all text-sm"
          >
            <IconMessageCircle className="w-4 h-4" /> {t('fin_ask_assistant')} <IconArrowRight className="w-4 h-4" />
          </Link>
        </div>
      </div>
    </div>
  )
}

/* ── Fee distribution bar ───────────────────────────────────────── */

function FeeBar({ label, value, bps, color }) {
  return (
    <div className="text-sm">
      <div className="flex items-center justify-between mb-1">
        <span className="text-stone-600">{label}</span>
        <span className="font-semibold text-stone-900">{fmtUsd(value)}</span>
      </div>
      <div className="w-full bg-stone-100 rounded-full h-2 overflow-hidden">
        <div className={`h-full rounded-full ${color}`} style={{ width: `${Math.min((bps || 0) / 100, 100)}%` }} />
      </div>
      <p className="text-xs text-stone-400 mt-0.5">{bps || 0} bps</p>
    </div>
  )
}
