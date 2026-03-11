import { useState, useEffect } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useSearchParams } from 'react-router-dom'
import {
  IconShieldCheck, IconCircleCheck, IconCircleX, IconCheck, IconX,
  IconMessageCircle, IconPackage, IconFileText, IconSearch,
} from '../components/svg/Icons'
import { checkCompliance } from '../api/marketplace'
import { getEudrCompliance, getContainerEudr } from '../api/logistics'
import PageHeroBg from '../components/svg/PageHeroBg'
import ComplianceShield from '../components/svg/ComplianceShield'
import EmptyState from '../components/svg/EmptyState'
import BlockchainPulse from '../components/svg/BlockchainPulse'
import TechCardBg from '../components/svg/TechCardBg'

/* ── Compliance level badge ─────────────────────────────────────── */

const LEVEL_COLORS = {
  Gold: 'bg-yellow-100 text-yellow-800 border-yellow-300',
  Silver: 'bg-stone-100 text-stone-700 border-stone-300',
  Bronze: 'bg-amber-100 text-amber-800 border-amber-300',
  'Non-Compliant': 'bg-red-100 text-red-700 border-red-300',
  Unknown: 'bg-stone-50 text-stone-500 border-stone-200',
}

function LevelBadge({ level }) {
  return <ComplianceShield level={level} size="sm" />
}

/* ── Article 9 detail card ──────────────────────────────────────── */

function Article9Card({ data }) {
  const { t } = useTranslation()
  if (!data) return null

  const fields = [
    ['Batch ID', data.batch_id],
    ['Commodity', data.commodity_description],
    ['Quantity', data.quantity_kg ? `${data.quantity_kg} kg` : null],
    ['Country of Production', data.country_of_production],
    ['Region', data.region_of_production],
    ['GTIN', data.gtin],
    ['Supplier', data.supplier_name],
    ['Supplier DID', data.supplier_did],
    ['Cooperative', data.cooperative_name],
    ['Date of Production', data.date_of_production],
    ['Geolocation', data.geolocation_latitude && data.geolocation_longitude
      ? `${data.geolocation_latitude}, ${data.geolocation_longitude}`
      : null],
    ['GPS Source', data.geolocation_source],
    ['GPS Verified', data.geolocation_verified_at],
    ['Deforestation Risk', data.deforestation_risk],
    ['Deforestation Compliant', data.deforestation_compliant != null
      ? (data.deforestation_compliant ? 'Yes' : 'No')
      : null],
    ['Confidence', data.deforestation_confidence != null
      ? `${(data.deforestation_confidence * 100).toFixed(1)}%`
      : null],
    ['Data Source', data.deforestation_data_source],
    ['Compliance Status', data.compliance_status],
    ['Blockchain Events', data.blockchain_event_count],
  ]

  return (
    <div className="relative overflow-hidden bg-white rounded-xl border border-stone-200 p-6 space-y-4 hover:-translate-y-0.5 hover:shadow-lg transition-all duration-200">
      <TechCardBg variant="hex" />
      <div className="relative z-10 flex items-center justify-between">
        <h3 className="text-sm font-bold text-stone-900">
          {data.batch_id}
        </h3>
        <LevelBadge level={data.compliance_level} />
      </div>

      <div className="grid sm:grid-cols-2 gap-x-6 gap-y-2 text-sm">
        {fields.map(([label, value]) => (
          value != null && value !== '' ? (
            <div key={label}>
              <dt className="text-xs text-stone-500">{label}</dt>
              <dd className="font-medium text-stone-800 break-all">{String(value)}</dd>
            </div>
          ) : null
        ))}
      </div>

      {/* Proof links */}
      {(data.geolocation_proof_ipfs_cid || data.geolocation_proof_blockchain_tx) && (
        <div className="border-t border-stone-100 pt-3 space-y-1">
          <p className="text-xs font-semibold text-stone-500 uppercase tracking-wider flex items-center gap-1.5">
            <BlockchainPulse size={16} />
            {t('comp_verification_proofs')}
          </p>
          {data.geolocation_proof_ipfs_cid && (
            <p className="text-xs text-stone-600">IPFS: <code className="text-[10px] font-mono">{data.geolocation_proof_ipfs_cid}</code></p>
          )}
          {data.geolocation_proof_blockchain_tx && (
            <p className="text-xs text-stone-600">Blockchain: <code className="text-[10px] font-mono truncate">{data.geolocation_proof_blockchain_tx}</code></p>
          )}
        </div>
      )}

      {data.dpp_url && (
        <Link
          to={`/dpp?batch=${encodeURIComponent(data.batch_id)}`}
          className="inline-block text-sm text-forest-600 hover:underline"
        >
          {t('comp_view_dpp')}
        </Link>
      )}
    </div>
  )
}

/* ── Main page ──────────────────────────────────────────────────── */

export default function Compliance() {
  const { t } = useTranslation()
  const [searchParams] = useSearchParams()
  const initialTab = searchParams.get('sscc') ? 'container' : 'batch'

  const [tab, setTab] = useState(initialTab)

  // Batch check state (original)
  const [batchInput, setBatchInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)

  // Article 9 state
  const [a9BatchId, setA9BatchId] = useState('')
  const [a9Loading, setA9Loading] = useState(false)
  const [a9Data, setA9Data] = useState(null)
  const [a9Error, setA9Error] = useState(null)

  // Container EUDR state
  const [containerSscc, setContainerSscc] = useState(searchParams.get('sscc') || '')
  const [containerLoading, setContainerLoading] = useState(false)
  const [containerData, setContainerData] = useState(null)
  const [containerError, setContainerError] = useState(null)

  const handleCheck = async (e) => {
    e?.preventDefault()
    if (!batchInput.trim()) return
    setLoading(true)
    setError(null)
    setResult(null)
    try {
      const ids = batchInput.split(/[,\s]+/).filter(Boolean)
      const res = await checkCompliance(ids)
      setResult(res)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  async function handleA9Search(e) {
    e?.preventDefault()
    if (!a9BatchId.trim()) return
    setA9Loading(true)
    setA9Error(null)
    setA9Data(null)
    try {
      const res = await getEudrCompliance(a9BatchId.trim())
      setA9Data(res)
    } catch (err) {
      setA9Error(err.message)
    } finally {
      setA9Loading(false)
    }
  }

  async function handleContainerSearch(e) {
    e?.preventDefault()
    if (!containerSscc.trim()) return
    setContainerLoading(true)
    setContainerError(null)
    setContainerData(null)
    try {
      const res = await getContainerEudr(containerSscc.trim())
      setContainerData(res)
    } catch (err) {
      setContainerError(err.message)
    } finally {
      setContainerLoading(false)
    }
  }

  // Auto-search if sscc query param is provided (e.g. linked from Tracking page)
  useEffect(() => {
    if (searchParams.get('sscc')) {
      handleContainerSearch()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const data = result?.data || null
  const compliant = data?.compliant ?? data?.is_compliant
  const checks = data?.checks || data?.details || {}
  const text = result?.text || ''

  return (
    <div className="max-w-4xl mx-auto px-4 py-8">
      {/* Header */}
      <div className="relative mb-2">
        <PageHeroBg variant="compliance" />
        <h1 className="text-2xl font-extrabold text-stone-900 flex items-center gap-2 page-header-accent">
          <IconShieldCheck className="w-6 h-6" /> {t('nav_compliance')}
        </h1>
      </div>
      <p className="text-sm text-stone-500 mb-6">
        {t('comp_subtitle')}
      </p>

      {/* Tabs */}
      <div className="flex gap-1 border-b border-stone-200 mb-6">
        <button
          onClick={() => setTab('batch')}
          className={`px-4 py-2 text-sm font-medium border-b-2 transition ${
            tab === 'batch'
              ? 'border-stone-900 text-stone-900'
              : 'border-transparent text-stone-500 hover:text-stone-700'
          }`}
        >
          <IconShieldCheck className="w-4 h-4 inline mr-1 -mt-0.5" />
          {t('comp_tab_batch')}
        </button>
        <button
          onClick={() => setTab('article9')}
          className={`px-4 py-2 text-sm font-medium border-b-2 transition ${
            tab === 'article9'
              ? 'border-stone-900 text-stone-900'
              : 'border-transparent text-stone-500 hover:text-stone-700'
          }`}
        >
          <IconFileText className="w-4 h-4 inline mr-1 -mt-0.5" />
          {t('comp_tab_article9')}
        </button>
        <button
          onClick={() => setTab('container')}
          className={`px-4 py-2 text-sm font-medium border-b-2 transition ${
            tab === 'container'
              ? 'border-stone-900 text-stone-900'
              : 'border-transparent text-stone-500 hover:text-stone-700'
          }`}
        >
          <IconPackage className="w-4 h-4 inline mr-1 -mt-0.5" />
          {t('comp_tab_container')}
        </button>
      </div>

      {/* ──────────── Tab: Batch Check (original) ──────────── */}
      {tab === 'batch' && (
        <>
          <form onSubmit={handleCheck} className="mb-8">
            <label className="block text-sm font-medium text-stone-700 mb-1.5">
              {t('comp_batch_label')}
            </label>
            <div className="flex flex-col sm:flex-row gap-2">
              <input
                type="text"
                value={batchInput}
                onChange={(e) => setBatchInput(e.target.value)}
                placeholder="ETH-COOP-001-2025-00001"
                className="flex-1 rounded-lg border border-stone-300 px-4 py-2.5 text-sm outline-none focus:border-stone-400 focus:ring-2 focus:ring-stone-200 transition"
              />
              <button
                type="submit"
                disabled={!batchInput.trim() || loading}
                className="bg-stone-900 text-white font-medium rounded-lg px-6 py-2.5 text-sm hover:bg-stone-800 hover:scale-105 active:scale-95 transition-all disabled:opacity-50 shrink-0"
              >
                {loading ? t('comp_checking') : t('comp_run_check')}
              </button>
            </div>
          </form>

          {error && (
            <div className="text-sm text-red-600 bg-red-50 border border-red-100 rounded-lg p-3 mb-4">{error}</div>
          )}

          {/* Results */}
          {result && (
            <div className="space-y-6">
              {/* Overall status banner */}
              {compliant != null && (
                <div
                  className={`rounded-xl p-5 border ${
                    compliant
                      ? 'bg-forest-50 border-forest-200'
                      : 'bg-red-50 border-red-200'
                  }`}
                >
                  <div className={`flex items-center gap-2 text-lg font-bold ${compliant ? 'text-forest-700' : 'text-red-700'}`}>
                    {compliant ? <IconCircleCheck className="w-6 h-6" /> : <IconCircleX className="w-6 h-6" />}
                    {compliant ? t('comp_eudr_compliant') : t('comp_eudr_not_compliant')}
                  </div>

                  {/* Check details */}
                  {Object.keys(checks).length > 0 && (
                    <ul className="mt-3 space-y-1.5 text-sm text-stone-700">
                      {Object.entries(checks).map(([k, v]) => (
                        <li key={k} className="flex items-center gap-2">
                          {v ? (
                            <IconCheck className="w-4 h-4 text-forest-600 shrink-0" />
                          ) : (
                            <IconX className="w-4 h-4 text-red-500 shrink-0" />
                          )}
                          <span className="capitalize">{k.replaceAll('_', ' ')}</span>
                        </li>
                      ))}
                    </ul>
                  )}

                  {data?.deforestation_risk != null && (
                    <div className="mt-3 text-sm text-stone-600">
                      {t('comp_deforestation_risk')}: <strong>{typeof data.deforestation_risk === 'number' ? `${(data.deforestation_risk * 100).toFixed(1)}%` : data.deforestation_risk}</strong>
                    </div>
                  )}
                </div>
              )}

              {/* Agent text explanation */}
              {text && (
                <div className="bg-white rounded-xl border border-stone-200 p-5 text-sm text-stone-700 whitespace-pre-wrap leading-relaxed">
                  {text}
                </div>
              )}

              {/* Batch-level results */}
              {data?.batch_results && data.batch_results.length > 0 && (
                <div className="bg-white rounded-xl border border-stone-200 overflow-hidden overflow-x-auto">
                  <table className="w-full text-sm min-w-[500px]">
                    <thead className="bg-stone-50 text-left text-xs text-stone-500 uppercase tracking-wider">
                      <tr>
                        <th className="px-4 py-3">{t('comp_col_batch')}</th>
                        <th className="px-4 py-3">{t('comp_col_gps')}</th>
                        <th className="px-4 py-3">Photo Verified</th>
                        <th className="px-4 py-3">{t('comp_col_deforestation')}</th>
                        <th className="px-4 py-3">{t('comp_col_status')}</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-stone-100">
                      {data.batch_results.map((b, i) => (
                        <tr key={b.batch_id || i} className={`hover:bg-stone-50 ${i % 2 === 1 ? 'bg-stone-50/30' : ''}`}>
                          <td className="px-4 py-3 font-medium text-stone-700">{b.batch_id}</td>
                          <td className="px-4 py-3">
                            {b.has_gps ? (
                              <IconCheck className="w-4 h-4 text-forest-600" />
                            ) : (
                              <IconX className="w-4 h-4 text-red-500" />
                            )}
                          </td>
                          <td className="px-4 py-3">
                            {b.photo_verified ? (
                              <IconCheck className="w-4 h-4 text-forest-600" />
                            ) : (
                              <IconX className="w-4 h-4 text-red-500" />
                            )}
                          </td>
                          <td className="px-4 py-3">
                            {b.deforestation_risk != null
                              ? (typeof b.deforestation_risk === 'number'
                                  ? `${(b.deforestation_risk * 100).toFixed(1)}%`
                                  : b.deforestation_risk)
                              : '-'}
                          </td>
                          <td className="px-4 py-3">
                            {b.compliant ? (
                              <span className="text-xs font-medium bg-green-100 text-green-700 rounded-full px-2 py-0.5">{t('comp_pass')}</span>
                            ) : (
                              <span className="text-xs font-medium bg-red-100 text-red-700 rounded-full px-2 py-0.5">{t('comp_fail')}</span>
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

          {/* Empty state */}
          {!result && !loading && (
            <EmptyState
              variant="compliance"
              message={t('comp_batch_empty')}
              actionLabel={t('comp_or_ask_assistant')}
              actionTo="/assistant"
            />
          )}
        </>
      )}

      {/* ──────────── Tab: Article 9 Viewer ──────────── */}
      {tab === 'article9' && (
        <>
          <form onSubmit={handleA9Search} className="mb-8">
            <label className="block text-sm font-medium text-stone-700 mb-1.5">
              {t('comp_a9_label')}
            </label>
            <div className="flex flex-col sm:flex-row gap-2">
              <div className="relative flex-1">
                <IconSearch className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-stone-400" />
                <input
                  type="text"
                  value={a9BatchId}
                  onChange={(e) => setA9BatchId(e.target.value)}
                  placeholder="ETH-COOP-001-2025-00001"
                  className="w-full pl-9 pr-4 py-2.5 rounded-lg border border-stone-300 text-sm outline-none focus:border-stone-400 focus:ring-2 focus:ring-stone-200 transition"
                />
              </div>
              <button
                type="submit"
                disabled={!a9BatchId.trim() || a9Loading}
                className="bg-stone-900 text-white font-medium rounded-lg px-6 py-2.5 text-sm hover:bg-stone-800 hover:scale-105 active:scale-95 transition-all disabled:opacity-50 shrink-0"
              >
                {a9Loading ? t('fin_loading') : t('comp_a9_fetch')}
              </button>
            </div>
          </form>

          {a9Error && (
            <div className="text-sm text-red-600 bg-red-50 border border-red-100 rounded-lg p-3 mb-4">{a9Error}</div>
          )}

          {a9Data && <Article9Card data={a9Data} />}

          {!a9Data && !a9Loading && !a9Error && (
            <EmptyState
              variant="compliance"
              message={t('comp_a9_empty')}
              sub={t('comp_a9_empty_sub')}
            />
          )}
        </>
      )}

      {/* ──────────── Tab: Container Compliance ──────────── */}
      {tab === 'container' && (
        <>
          <form onSubmit={handleContainerSearch} className="mb-8">
            <label className="block text-sm font-medium text-stone-700 mb-1.5">
              {t('comp_container_label')}
            </label>
            <div className="flex flex-col sm:flex-row gap-2">
              <div className="relative flex-1">
                <IconSearch className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-stone-400" />
                <input
                  type="text"
                  value={containerSscc}
                  onChange={(e) => setContainerSscc(e.target.value)}
                  placeholder="034012345000000001"
                  className="w-full pl-9 pr-4 py-2.5 rounded-lg border border-stone-300 text-sm outline-none focus:border-stone-400 focus:ring-2 focus:ring-stone-200 transition"
                />
              </div>
              <button
                type="submit"
                disabled={!containerSscc.trim() || containerLoading}
                className="bg-stone-900 text-white font-medium rounded-lg px-6 py-2.5 text-sm hover:bg-stone-800 hover:scale-105 active:scale-95 transition-all disabled:opacity-50 shrink-0"
              >
                {containerLoading ? t('fin_loading') : t('comp_container_fetch')}
              </button>
            </div>
          </form>

          {containerError && (
            <div className="text-sm text-red-600 bg-red-50 border border-red-100 rounded-lg p-3 mb-4">{containerError}</div>
          )}

          {containerData && (
            <div className="space-y-6">
              {/* Container summary */}
              <div className="bg-white rounded-xl border border-stone-200 p-5">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                  <div>
                    <p className="text-xs text-stone-400 font-mono mb-1">{containerData.container_sscc}</p>
                    <div className="flex items-center gap-3">
                      <LevelBadge level={containerData.overall_compliance_level} />
                      <span className="text-sm text-stone-600">{containerData.batch_count} batches</span>
                    </div>
                  </div>
                  <div className="text-sm text-stone-600">
                    <strong>{containerData.total_quantity_kg?.toLocaleString()}</strong> kg total
                  </div>
                </div>
              </div>

              {/* Per-batch Article 9 cards */}
              {containerData.batches?.map((batch) => (
                <Article9Card key={batch.batch_id} data={batch} />
              ))}

              {containerData.batches?.length === 0 && (
                <div className="text-center text-stone-400 py-8 text-sm">
                  {t('comp_no_batches')}
                </div>
              )}

              {/* Link to tracking */}
              <div className="flex gap-3">
                <Link
                  to={`/tracking?sscc=${encodeURIComponent(containerData.container_sscc)}`}
                  className="inline-flex items-center gap-1.5 text-sm text-stone-600 hover:text-stone-800 transition"
                >
                  <IconPackage className="w-4 h-4" /> {t('comp_view_tracking')}
                </Link>
              </div>
            </div>
          )}

          {!containerData && !containerLoading && !containerError && (
            <EmptyState
              variant="containers"
              message={t('comp_container_empty')}
              sub={t('comp_container_empty_sub')}
            />
          )}
        </>
      )}

      {/* Explainer */}
      <div className="mt-12 bg-gradient-to-br from-stone-50 to-stone-100/60 rounded-xl p-6 border border-stone-200">
        <h2 className="text-lg font-bold text-stone-800 mb-3 section-heading">{t('comp_about_title')}</h2>
        <div className="text-sm text-stone-600 space-y-2 leading-relaxed">
          <p>{t('comp_about_p1')}</p>
          <p>{t('comp_about_p2')}</p>
          <p>{t('comp_about_p3')}</p>
        </div>
      </div>
    </div>
  )
}
