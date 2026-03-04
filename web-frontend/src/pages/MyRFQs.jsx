import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, Navigate } from 'react-router-dom'
import { LuFileText, LuRefreshCw, LuMessageCircle } from 'react-icons/lu'
import { listMyRFQs } from '../api/marketplace'
import useAuthStore from '../stores/authStore'

function StatusBadge({ status }) {
  const colors = {
    OPEN: 'bg-green-100 text-green-700',
    PARTIALLY_FILLED: 'bg-yellow-100 text-yellow-700',
    FULFILLED: 'bg-stone-100 text-stone-500',
    CANCELLED: 'bg-red-100 text-red-600',
  }
  return (
    <span className={`text-xs font-medium rounded-full px-2 py-0.5 ${colors[status] || 'bg-stone-100 text-stone-600'}`}>
      {status}
    </span>
  )
}

export default function MyRFQs() {
  const { t } = useTranslation()
  const { isAuthenticated } = useAuthStore()
  const [rfqs, setRFQs] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  const load = async () => {
    setLoading(true)
    setError(null)
    try {
      const data = await listMyRFQs()
      setRFQs(Array.isArray(data) ? data : [])
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    if (isAuthenticated) load()
  }, [isAuthenticated])

  if (!isAuthenticated) return <Navigate to="/login" replace />

  return (
    <div className="max-w-5xl mx-auto px-4 py-8">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-stone-900 flex items-center gap-2">
          <LuFileText className="w-6 h-6" /> {t('nav_my_rfqs')}
        </h1>
        <div className="flex items-center gap-3">
          <button
            onClick={load}
            disabled={loading}
            className="inline-flex items-center gap-1 text-sm text-stone-500 hover:text-stone-700 transition"
          >
            <LuRefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} /> Refresh
          </button>
          <Link
            to="/assistant"
            className="inline-flex items-center gap-1 text-sm bg-stone-900 text-white rounded-full px-4 py-1.5 hover:bg-stone-800 transition"
          >
            <LuMessageCircle className="w-4 h-4" /> Create RFQ
          </Link>
        </div>
      </div>

      {error && (
        <div className="text-sm text-red-600 bg-red-50 rounded-lg p-3 mb-4">{error}</div>
      )}

      {loading && (
        <div className="text-center text-stone-400 py-16 text-sm">Loading your RFQs…</div>
      )}

      {!loading && (
        <div className="bg-white rounded-xl border border-stone-200 overflow-hidden">
          {rfqs.length === 0 ? (
            <div className="text-center text-stone-400 py-12 text-sm">
              You have no RFQs yet. <Link to="/assistant" className="text-stone-600 underline">Create one via the assistant</Link>.
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="bg-stone-50 text-left text-xs text-stone-500 uppercase tracking-wider">
                  <tr>
                    <th className="px-4 py-3">RFQ #</th>
                    <th className="px-4 py-3">Variety</th>
                    <th className="px-4 py-3">Quantity</th>
                    <th className="px-4 py-3">Grade</th>
                    <th className="px-4 py-3">Delivery</th>
                    <th className="px-4 py-3">Status</th>
                    <th className="px-4 py-3">Offers</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-stone-100">
                  {rfqs.map((r) => (
                    <tr key={r.id} className="hover:bg-stone-50 transition">
                      <td className="px-4 py-3 font-medium text-stone-700">{r.rfq_number}</td>
                      <td className="px-4 py-3">{r.variety || '-'}</td>
                      <td className="px-4 py-3">{r.quantity_kg?.toLocaleString()} kg</td>
                      <td className="px-4 py-3">{r.grade || '-'}</td>
                      <td className="px-4 py-3 text-xs">{r.delivery_location || '-'}</td>
                      <td className="px-4 py-3"><StatusBadge status={r.status} /></td>
                      <td className="px-4 py-3 text-center">{r.offer_count ?? 0}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
