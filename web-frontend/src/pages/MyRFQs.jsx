import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, Navigate } from 'react-router-dom'
import { IconFileText, IconRefreshCw, IconMessageCircle, IconX } from '../components/svg/Icons'
import { listMyRFQs, listRFQOffers } from '../api/marketplace'
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

function OfferStatusBadge({ status }) {
  const colors = {
    PENDING: 'bg-yellow-100 text-yellow-700',
    ACCEPTED: 'bg-green-100 text-green-700',
    REJECTED: 'bg-red-100 text-red-600',
  }
  return (
    <span className={`text-xs font-medium rounded-full px-2 py-0.5 ${colors[status] || 'bg-stone-100 text-stone-600'}`}>
      {status}
    </span>
  )
}

export default function MyRFQs() {
  const { t } = useTranslation()
  const { isAuthenticated, user } = useAuthStore()
  const [rfqs, setRFQs] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [selectedRFQ, setSelectedRFQ] = useState(null)
  const [offers, setOffers] = useState([])
  const [loadingOffers, setLoadingOffers] = useState(false)

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

  const loadOffers = async (rfqId) => {
    setLoadingOffers(true)
    try {
      const data = await listRFQOffers(rfqId)
      setOffers(Array.isArray(data) ? data : [])
    } catch (e) {
      console.error('Failed to load offers:', e)
    } finally {
      setLoadingOffers(false)
    }
  }

  const handleViewOffers = (rfq) => {
    setSelectedRFQ(rfq)
    setOffers([])
    loadOffers(rfq.id)
  }

  const closeOffersModal = () => {
    setSelectedRFQ(null)
    setOffers([])
  }

  useEffect(() => {
    if (isAuthenticated) load()
  }, [isAuthenticated])

  if (!isAuthenticated) return <Navigate to="/login" replace />
  
  // Role-based access: Only BUYER role can access MyRFQs
  if (user?.role !== 'BUYER') {
    return (
      <div className="max-w-5xl mx-auto px-4 py-8">
        <div className="text-center">
          <h1 className="text-xl sm:text-2xl font-extrabold text-stone-900 mb-4">
            Access Restricted
          </h1>
          <p className="text-stone-600 mb-6">
            This page is only available to users with BUYER role.
          </p>
          <Link
            to="/"
            className="inline-flex items-center gap-2 text-sm bg-stone-900 text-white rounded-full px-4 py-2 hover:bg-stone-800 transition"
          >
            Go Home
          </Link>
        </div>
      </div>
    )
  }

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
                      <td className="px-4 py-3 text-center">
                        {r.offer_count > 0 ? (
                          <button
                            onClick={() => handleViewOffers(r)}
                            className="text-blue-600 hover:text-blue-800 font-medium hover:underline"
                          >
                            {r.offer_count} offer{r.offer_count > 1 ? 's' : ''}
                          </button>
                        ) : (
                          <span className="text-stone-400">0</span>
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

      {/* Offers Modal */}
      {selectedRFQ && (
        <div className="fixed inset-0 z-50 bg-black/40 backdrop-blur-sm flex items-center justify-center p-4" onClick={closeOffersModal}>
          <div
            className="bg-white rounded-2xl shadow-xl max-w-2xl w-full max-h-[80vh] overflow-hidden animate-fade-in-up"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between px-6 py-4 border-b border-stone-200">
              <div>
                <h3 className="text-lg font-bold text-stone-900">Offers for {selectedRFQ.rfq_number}</h3>
                <p className="text-xs text-stone-500">{selectedRFQ.variety || 'Any variety'} • {selectedRFQ.quantity_kg?.toLocaleString()} kg</p>
              </div>
              <button onClick={closeOffersModal} className="text-stone-400 hover:text-stone-600 transition">
                <IconX className="w-5 h-5" />
              </button>
            </div>

            <div className="p-6 overflow-y-auto max-h-[60vh]">
              {loadingOffers ? (
                <div className="text-center py-8 text-stone-500">Loading offers...</div>
              ) : offers.length === 0 ? (
                <div className="text-center py-8 text-stone-500">No offers found for this RFQ.</div>
              ) : (
                <div className="space-y-3">
                  {offers.map((offer) => (
                    <div key={offer.id} className="border border-stone-200 rounded-lg p-4 hover:border-stone-300 transition">
                      <div className="flex items-start justify-between mb-2">
                        <div>
                          <p className="font-semibold text-stone-900">{offer.offer_number}</p>
                          <p className="text-sm text-stone-600">{offer.cooperative_name}</p>
                        </div>
                        <OfferStatusBadge status={offer.status} />
                      </div>
                      <div className="grid grid-cols-2 gap-4 text-sm">
                        <div>
                          <p className="text-xs text-stone-500">Quantity</p>
                          <p className="font-medium text-stone-900">{offer.quantity_offered_kg?.toLocaleString()} kg</p>
                        </div>
                        <div>
                          <p className="text-xs text-stone-500">Price</p>
                          <p className="font-medium text-stone-900">${offer.price_per_kg}/kg</p>
                        </div>
                        <div className="col-span-2">
                          <p className="text-xs text-stone-500">Total Value</p>
                          <p className="font-medium text-stone-900">${(offer.quantity_offered_kg * offer.price_per_kg)?.toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2})}</p>
                        </div>
                        {offer.delivery_timeline && (
                          <div className="col-span-2">
                            <p className="text-xs text-stone-500">Delivery Timeline</p>
                            <p className="font-medium text-stone-900">{offer.delivery_timeline}</p>
                          </div>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
