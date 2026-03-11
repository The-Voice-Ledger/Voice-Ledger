import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, Navigate } from 'react-router-dom'
import { IconFileText, IconRefreshCw, IconMessageCircle } from '../components/svg/Icons'
import { listMyRFQs } from '../api/marketplace'
import useAuthStore from '../stores/authStore'
import PageHeroBg from '../components/svg/PageHeroBg'
import EmptyState from '../components/svg/EmptyState'

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
      <div className="relative flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-6">
        <PageHeroBg variant="rfqs" />
        <h1 className="text-xl sm:text-2xl font-extrabold text-stone-900 flex items-center gap-2 page-header-accent">
          <IconFileText className="w-6 h-6 shrink-0" /> {t('nav_my_rfqs')}
        </h1>
        <div className="flex items-center gap-3">
          <button
            onClick={load}
            disabled={loading}
            className="inline-flex items-center gap-1 text-sm text-stone-500 hover:text-stone-700 transition"
          >
            <IconRefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} /> Refresh
          </button>
          <Link
            to="/assistant"
            className="inline-flex items-center gap-1 text-sm bg-stone-900 text-white rounded-full px-4 py-1.5 hover:bg-stone-800 transition"
          >
            <IconMessageCircle className="w-4 h-4" /> Create RFQ
          </Link>
        </div>
      </div>

      {error && (
        <div className="text-sm text-red-600 bg-red-50 rounded-lg p-3 mb-4">{error}</div>
      )}

      {loading && (
        <div className="bg-white rounded-xl border border-stone-200 overflow-hidden">
          <div className="animate-pulse">
            <div className="bg-stone-50 px-4 py-3 flex gap-4">
              {[80, 64, 56, 48, 64, 48, 40].map((w, i) => (
                <div key={i} className="h-3 bg-stone-200 rounded" style={{ width: w }} />
              ))}
            </div>
            {[...Array(4)].map((_, i) => (
              <div key={i} className="px-4 py-3.5 flex gap-4 border-t border-stone-100">
                {[72, 56, 48, 40, 60, 52, 32].map((w, j) => (
                  <div key={j} className="h-3 bg-stone-100 rounded" style={{ width: w }} />
                ))}
              </div>
            ))}
          </div>
        </div>
      )}

      {!loading && (
        <div className="bg-white rounded-xl border border-stone-200 overflow-hidden">
          {rfqs.length === 0 ? (
            <EmptyState
              variant="rfqs"
              message="You have no RFQs yet."
              sub="Create one using the voice assistant or chat."
              actionLabel="Create RFQ"
              actionTo="/assistant"
            />
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
