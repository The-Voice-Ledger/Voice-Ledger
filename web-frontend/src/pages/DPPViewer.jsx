import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useSearchParams, Link } from 'react-router-dom'
import { LuSprout, LuSearch, LuLink, LuShieldCheck, LuMessageCircle } from 'react-icons/lu'
import { fetchDPP } from '../api/marketplace'

/* ── Skeleton loader ───────────────────────────────────────────── */

function DPPSkeleton() {
  return (
    <div className="space-y-6 animate-pulse">
      <div className="bg-white rounded-xl border border-stone-200 p-5">
        <div className="h-4 w-48 bg-stone-200 rounded mb-3" />
        <div className="h-3 w-full bg-stone-100 rounded mb-2" />
        <div className="h-3 w-3/4 bg-stone-100 rounded" />
      </div>
      <div className="bg-white rounded-xl border border-forest-200 p-6">
        <div className="h-5 w-52 bg-stone-200 rounded mb-4" />
        <div className="grid sm:grid-cols-2 gap-4">
          {[...Array(6)].map((_, i) => (
            <div key={i}>
              <div className="h-3 w-16 bg-stone-200 rounded mb-1" />
              <div className="h-4 w-32 bg-stone-100 rounded" />
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

export default function DPPViewer() {
  const { t } = useTranslation()
  const [searchParams] = useSearchParams()
  const [batchId, setBatchId] = useState(searchParams.get('batch') || '')
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)

  const handleSearch = async (e) => {
    e?.preventDefault()
    if (!batchId.trim()) return
    setLoading(true)
    setError(null)
    setResult(null)
    try {
      const res = await fetchDPP(batchId.trim())
      setResult(res)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  const dpp = result?.data?.dpp || result?.data || null
  const text = result?.text || ''

  return (
    <div className="max-w-4xl mx-auto px-4 py-8">
      {/* Header */}
      <h1 className="text-2xl font-bold text-stone-900 flex items-center gap-2 mb-2">
        <LuSprout className="w-6 h-6" /> {t('nav_dpp')}
      </h1>
      <p className="text-sm text-stone-500 mb-6">
        {t('dpp_subtitle')}
      </p>

      {/* Search */}
      <form onSubmit={handleSearch} className="flex flex-col sm:flex-row gap-2 mb-8">
        <div className="relative flex-1">
          <LuSearch className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-stone-400" />
          <input
            type="text"
            value={batchId}
            onChange={(e) => setBatchId(e.target.value)}
            placeholder={t('dpp_placeholder')}
            className="w-full pl-9 pr-4 py-2.5 rounded-lg border border-stone-300 text-sm outline-none focus:border-stone-400 focus:ring-2 focus:ring-stone-200 transition"
          />
        </div>
        <button
          type="submit"
          disabled={!batchId.trim() || loading}
          className="bg-stone-900 text-white font-medium rounded-lg px-6 py-2.5 text-sm hover:bg-stone-800 hover:scale-105 active:scale-95 transition-all disabled:opacity-50 shrink-0"
        >
          {loading ? t('dpp_looking_up') : t('dpp_look_up')}
        </button>
      </form>

      {error && (
        <div className="text-sm text-red-600 bg-red-50 border border-red-100 rounded-lg p-3 mb-4">{error}</div>
      )
      }

      {/* Loading skeleton */}
      {loading && !result && <DPPSkeleton />}

      {/* DPP Result */}
      {result && (
        <div className="space-y-6">
          {/* Agent text response */}
          {text && (
            <div className="bg-white rounded-xl border border-stone-200 p-5 text-sm text-stone-700 whitespace-pre-wrap leading-relaxed">
              {text}
            </div>
          )}

          {/* Structured DPP card */}
          {dpp && (
            <div className="bg-white rounded-xl border border-forest-200 p-6 space-y-4 hover:-translate-y-0.5 hover:shadow-lg transition-all duration-200">
              <h2 className="text-lg font-bold text-forest-700 flex items-center gap-2">
                <LuSprout className="w-5 h-5" /> {t('dpp_title')}
              </h2>

              <div className="grid sm:grid-cols-2 gap-4 text-sm">
                {dpp.batch_id && <Field label="Batch ID" value={dpp.batch_id} />}
                {dpp.gtin && <Field label="GTIN" value={dpp.gtin} />}
                {dpp.origin && <Field label="Origin" value={dpp.origin} />}
                {dpp.variety && <Field label="Variety" value={dpp.variety} />}
                {dpp.processing && <Field label="Processing" value={dpp.processing} />}
                {dpp.grade && <Field label="Grade" value={dpp.grade} />}
                {dpp.quantity_kg && <Field label="Quantity" value={`${dpp.quantity_kg} kg`} />}
                {dpp.farmer_name && <Field label="Farmer" value={dpp.farmer_name} />}
                {dpp.cooperative && <Field label="Cooperative" value={dpp.cooperative} />}
              </div>

              {/* Certifications */}
              {dpp.certifications?.length > 0 && (
                <div>
                  <h3 className="text-xs font-semibold text-stone-500 uppercase tracking-wider mb-1">{t('dpp_certifications')}</h3>
                  <div className="flex flex-wrap gap-1.5">
                    {dpp.certifications.map((cert) => (
                      <span key={cert} className="text-xs bg-forest-100 text-forest-700 rounded-full px-2.5 py-0.5">
                        {cert}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {/* GPS */}
              {(dpp.latitude || dpp.gps_coordinates) && (
                <div className="flex items-center gap-2 text-xs text-stone-500">
                  <LuShieldCheck className="w-3.5 h-3.5 text-forest-600" />
                  GPS: {dpp.latitude && dpp.longitude ? `${dpp.latitude}, ${dpp.longitude}` : dpp.gps_coordinates}
                </div>
              )}

              {/* Blockchain status */}
              {(dpp.blockchain_anchored || dpp.tx_hash) && (
                <div className="flex items-center gap-2 text-xs text-stone-500">
                  <LuLink className="w-3.5 h-3.5 text-stone-600" />
                  {dpp.blockchain_anchored ? 'Anchored on Base Sepolia' : 'Not yet anchored'}
                  {dpp.tx_hash && <code className="text-[10px] truncate max-w-[200px]">{dpp.tx_hash}</code>}
                </div>
              )}

              {/* QR code link */}
              {dpp.qr_url && (
                <a
                  href={dpp.qr_url}
                  target="_blank"
                  rel="noreferrer"
                  className="inline-block text-sm text-forest-600 underline"
                >
                  View QR Code
                </a>
              )}
            </div>
          )}

          {/* Lineage */}
          {dpp?.lineage && dpp.lineage.length > 0 && (
            <div className="bg-white rounded-xl border border-stone-200 p-6">
              <h2 className="text-lg font-bold text-stone-800 mb-4">{t('dpp_lineage')}</h2>
              <div className="relative pl-8">
                {/* Vertical line */}
                <div className="absolute left-3.5 top-2 bottom-2 w-0.5 bg-stone-200" />
                <div className="space-y-5">
                  {dpp.lineage.map((step, i) => (
                    <div key={i} className="relative flex gap-3">
                      <div className="absolute -left-8 top-0.5 w-7 h-7 rounded-full bg-forest-100 text-forest-700 flex items-center justify-center text-xs font-bold shrink-0 z-10">
                        {i + 1}
                      </div>
                      <div>
                        <div className="font-medium text-stone-800">{step.event_type || step.type}</div>
                        <div className="text-xs text-stone-500">{step.description || step.batch_id}</div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Empty state */}
      {!result && !loading && (
        <div className="text-center text-stone-400 py-16">
          <div className="w-20 h-20 mx-auto mb-4 rounded-full bg-gradient-to-br from-forest-100 via-stone-100 to-amber-100 flex items-center justify-center">
            <LuSprout className="w-10 h-10 text-stone-400" />
          </div>
          <p className="text-sm mb-4">{t('dpp_empty')}</p>
          <Link
            to="/assistant"
            className="inline-flex items-center gap-1.5 text-sm text-stone-600 hover:text-stone-700 hover:scale-105 active:scale-95 transition-all"
          >
            <LuMessageCircle className="w-4 h-4" /> {t('dpp_or_ask_assistant')}
          </Link>
        </div>
      )}
    </div>
  )
}

function Field({ label, value }) {
  return (
    <div>
      <dt className="text-xs text-stone-500">{label}</dt>
      <dd className="font-medium text-stone-800">{value}</dd>
    </div>
  )
}
