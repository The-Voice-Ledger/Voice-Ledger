import { useSearchParams, Link, useParams } from 'react-router-dom'
import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
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
  const { batchId: pathBatchId } = useParams()
  const [searchParams] = useSearchParams()
  const [batchId, setBatchId] = useState(pathBatchId || searchParams.get('batch') || '')
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    if (pathBatchId) {
      setBatchId(pathBatchId)
      performLookup(pathBatchId)
    } else if (searchParams.get('batch')) {
      performLookup(searchParams.get('batch'))
    }
  }, [pathBatchId, searchParams])

  const performLookup = async (id) => {
    if (!id.trim()) return
    setLoading(true)
    setError(null)
    setResult(null)
    try {
      const res = await fetchDPP(id.trim())
      setResult(res)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  const handleSearch = (e) => {
    e?.preventDefault()
    performLookup(batchId)
  }

  const dpp = result?.data?.dpp || result?.data || null

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


          {/* Structured DPP card */}
          {dpp && (
            <div className="bg-white rounded-2xl border border-stone-200 shadow-sm overflow-hidden hover:shadow-md transition-shadow duration-300">
              <div className="bg-stone-50 border-b border-stone-100 px-6 py-4">
                <h2 className="text-lg font-bold text-stone-900 flex items-center gap-2">
                  <LuSprout className="w-5 h-5 text-forest-600" /> {t('dpp_title')}
                </h2>
              </div>

              <div className="p-6 space-y-6">
                <dl className="grid sm:grid-cols-2 gap-x-8 gap-y-6">
                  {(dpp.batch_id || dpp.id) && <Field label="Batch ID" value={dpp.batch_id || dpp.id} highlight />}
                  {dpp.gtin && <Field label="GTIN" value={dpp.gtin} />}
                  {(dpp.origin || dpp.region) && <Field label="Origin" value={dpp.origin || dpp.region} />}
                  {dpp.variety && <Field label="Variety" value={dpp.variety} />}
                  {dpp.grade && <Field label="Grade" value={dpp.grade} />}
                  {(dpp.quantity_kg || dpp.quantity || dpp.amount) && (
                    <Field label="Quantity" value={`${dpp.quantity_kg || dpp.quantity || dpp.amount} kg`} />
                  )}
                  {dpp.farmer_name && <Field label="Farmer" value={dpp.farmer_name} />}
                  {dpp.cooperative && <Field label="Cooperative" value={dpp.cooperative} />}

                  {/* GPS */}
                  {(dpp.latitude || dpp.gps_coordinates) && (
                    <div className="sm:col-span-2">
                      <dt className="text-xs font-semibold text-stone-400 uppercase tracking-widest mb-1">GPS Location</dt>
                      <dd className="flex items-center gap-2 text-sm text-stone-700 font-medium">
                        <LuShieldCheck className="w-4 h-4 text-forest-600" />
                        {dpp.latitude && dpp.longitude ? `${dpp.latitude}, ${dpp.longitude}` : (dpp.gps_coordinates === '?, ?' ? 'Not available' : dpp.gps_coordinates)}
                      </dd>
                    </div>
                  )}

                  {/* Blockchain status */}
                  {(dpp.blockchain_anchored || dpp.tx_hash) && (
                    <div className="sm:col-span-2 space-y-2">
                      <dt className="text-xs font-semibold text-stone-400 uppercase tracking-widest mb-1">Blockchain Proof</dt>
                      <dd className="space-y-2">
                        <div className="flex items-center gap-2 text-sm font-medium text-stone-700">
                          <div className={`w-2 h-2 rounded-full ${dpp.blockchain_anchored ? 'bg-forest-500 animate-pulse' : 'bg-amber-400'}`} />
                          {dpp.blockchain_anchored ? 'Anchored on Base Sepolia' : 'Not yet anchored'}
                        </div>
                        {dpp.tx_hash && (
                          <div className="group relative">
                            <code className="block text-[11px] font-mono bg-stone-50 text-stone-500 p-3 rounded-xl border border-stone-100 break-all leading-relaxed">
                              {dpp.tx_hash}
                            </code>
                          </div>
                        )}
                      </dd>
                    </div>
                  )}
                </dl>

                {/* Certifications */}
                {dpp.certifications?.length > 0 && (
                  <div className="pt-4 border-t border-stone-50">
                    <dt className="text-xs font-semibold text-stone-400 uppercase tracking-widest mb-2">{t('dpp_certifications')}</dt>
                    <div className="flex flex-wrap gap-2">
                      {dpp.certifications.map((cert) => (
                        <span key={cert} className="inline-flex items-center px-3 py-1 rounded-full text-xs font-medium bg-forest-50 text-forest-700 border border-forest-100">
                          {cert}
                        </span>
                      ))}
                    </div>
                  </div>
                )}

                {/* QR code section - The star of the show */}
                {(dpp.qr_url || dpp.qr_image) && (
                  <div className="mt-8 pt-8 border-t border-stone-100 bg-stone-50/50 -mx-6 -mb-6 px-6 py-8 flex flex-col items-center text-center">
                    <h3 className="text-sm font-bold text-stone-900 mb-6 uppercase tracking-[0.2em]">View QR Code</h3>

                    {dpp.qr_image && (
                      <div className="relative group">
                        <div className="absolute -inset-4 bg-gradient-to-tr from-forest-100 to-amber-100 rounded-2xl blur-xl opacity-50 group-hover:opacity-100 transition duration-500" />
                        <div className="relative bg-white p-4 rounded-2xl border border-stone-200 shadow-xl">
                          <img
                            src={dpp.qr_image}
                            alt="DPP QR Code"
                            className="w-48 h-48 object-contain"
                          />
                        </div>
                      </div>
                    )}

                    <div className="mt-8 space-y-3 max-w-sm">
                      <p className="text-xs text-stone-500 leading-relaxed">
                        Scan this code to verify the full immutable history of this batch on the Voice Ledger network.
                      </p>
                      {dpp.qr_url && (
                        <a
                          href={dpp.qr_url}
                          target="_blank"
                          rel="noreferrer"
                          className="inline-flex items-center gap-2 text-[10px] font-mono text-stone-400 hover:text-forest-600 transition-colors bg-white px-3 py-1.5 rounded-full border border-stone-100 shadow-sm"
                        >
                          <LuLink className="w-3 h-3" />
                          {dpp.qr_url}
                        </a>
                      )}
                    </div>
                  </div>
                )}
              </div>
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

function Field({ label, value, highlight }) {
  return (
    <div>
      <dt className="text-xs font-semibold text-stone-400 uppercase tracking-widest mb-1">{label}</dt>
      <dd className={`text-sm font-medium ${highlight ? 'text-forest-700 font-bold' : 'text-stone-700'}`}>
        {value || '—'}
      </dd>
    </div>
  )
}
