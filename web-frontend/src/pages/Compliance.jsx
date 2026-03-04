import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'
import { LuShieldCheck, LuCircleCheck, LuCircleX, LuCheck, LuX, LuMessageCircle } from 'react-icons/lu'
import { checkCompliance } from '../api/marketplace'

export default function Compliance() {
  const { t } = useTranslation()
  const [batchInput, setBatchInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)

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

  const data = result?.data || null
  const compliant = data?.compliant ?? data?.is_compliant
  const checks = data?.checks || data?.details || {}
  const text = result?.text || ''

  return (
    <div className="max-w-4xl mx-auto px-4 py-8">
      {/* Header */}
      <h1 className="text-2xl font-bold text-stone-900 flex items-center gap-2 mb-2">
        <LuShieldCheck className="w-6 h-6" /> {t('nav_compliance')}
      </h1>
      <p className="text-sm text-stone-500 mb-6">
        Run EUDR 2023/1115 compliance checks on coffee batches. Validates GPS coordinates, deforestation risk,
        and audit-readiness for EU imports.
      </p>

      {/* Input */}
      <form onSubmit={handleCheck} className="mb-8">
        <label className="block text-sm font-medium text-stone-700 mb-1.5">
          Batch IDs (comma or space separated)
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
            className="bg-stone-900 text-white font-medium rounded-lg px-6 py-2.5 text-sm hover:bg-stone-800 transition disabled:opacity-50 shrink-0"
          >
            {loading ? 'Checking...' : 'Run Check'}
          </button>
        </div>
      </form>

      {error && (
        <div className="text-sm text-red-600 bg-red-50 rounded-lg p-3 mb-4">{error}</div>
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
                {compliant ? <LuCircleCheck className="w-6 h-6" /> : <LuCircleX className="w-6 h-6" />}
                {compliant ? 'EUDR Compliant' : 'Not EUDR Compliant'}
              </div>

              {/* Check details */}
              {Object.keys(checks).length > 0 && (
                <ul className="mt-3 space-y-1.5 text-sm text-stone-700">
                  {Object.entries(checks).map(([k, v]) => (
                    <li key={k} className="flex items-center gap-2">
                      {v ? (
                        <LuCheck className="w-4 h-4 text-forest-600 shrink-0" />
                      ) : (
                        <LuX className="w-4 h-4 text-red-500 shrink-0" />
                      )}
                      <span className="capitalize">{k.replaceAll('_', ' ')}</span>
                    </li>
                  ))}
                </ul>
              )}

              {data?.deforestation_risk != null && (
                <div className="mt-3 text-sm text-stone-600">
                  Deforestation risk score: <strong>{(data.deforestation_risk * 100).toFixed(1)}%</strong>
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
                    <th className="px-4 py-3">Batch</th>
                    <th className="px-4 py-3">GPS</th>
                    <th className="px-4 py-3">Deforestation</th>
                    <th className="px-4 py-3">Status</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-stone-100">
                  {data.batch_results.map((b, i) => (
                    <tr key={b.batch_id || i} className="hover:bg-stone-50">
                      <td className="px-4 py-3 font-medium text-stone-700">{b.batch_id}</td>
                      <td className="px-4 py-3">
                        {b.has_gps ? (
                          <LuCheck className="w-4 h-4 text-forest-600" />
                        ) : (
                          <LuX className="w-4 h-4 text-red-500" />
                        )}
                      </td>
                      <td className="px-4 py-3">
                        {b.deforestation_risk != null
                          ? `${(b.deforestation_risk * 100).toFixed(1)}%`
                          : '-'}
                      </td>
                      <td className="px-4 py-3">
                        {b.compliant ? (
                          <span className="text-xs font-medium bg-green-100 text-green-700 rounded-full px-2 py-0.5">Pass</span>
                        ) : (
                          <span className="text-xs font-medium bg-red-100 text-red-700 rounded-full px-2 py-0.5">Fail</span>
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
        <div className="text-center text-stone-400 py-16">
          <LuShieldCheck className="w-12 h-12 mx-auto mb-3 opacity-40" />
          <p className="text-sm mb-4">Enter batch IDs above to run an EUDR compliance check.</p>
          <Link
            to="/assistant"
            className="inline-flex items-center gap-1.5 text-sm text-stone-600 hover:text-stone-700"
          >
            <LuMessageCircle className="w-4 h-4" /> Or ask the assistant
          </Link>
        </div>
      )}

      {/* Explainer */}
      <div className="mt-12 bg-stone-50 rounded-xl p-6 border border-stone-100">
        <h2 className="text-lg font-bold text-stone-800 mb-3">About EUDR Compliance</h2>
        <div className="text-sm text-stone-600 space-y-2 leading-relaxed">
          <p>
            The EU Deforestation Regulation (2023/1115) requires importers to demonstrate that commodities
            including coffee were not produced on land deforested after December 31, 2020.
          </p>
          <p>
            WAGA Coffee automatically validates: GPS coordinates for all contributing farms,
            deforestation risk assessment via Global Forest Watch satellite data,
            and complete supply chain traceability from farmer to port.
          </p>
        </div>
      </div>
    </div>
  )
}
