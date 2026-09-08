import { useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import TechCardBg from '../components/svg/TechCardBg'
import EmptyState from '../components/svg/EmptyState'
import PageHeroBg from '../components/svg/PageHeroBg'
import { verifyDid } from '../api/ssi'

/* ── Skeleton ───────────────────────────────────────────────────── */

function DidSkeleton() {
  return (
    <div className="space-y-4 animate-pulse">
      <div className="bg-white rounded-xl border border-stone-200 p-5">
        <div className="h-3 w-24 bg-stone-200 rounded mb-3" />
        <div className="h-4 w-72 bg-stone-200 rounded mb-2" />
        <div className="h-3 w-40 bg-stone-100 rounded" />
      </div>
      <div className="bg-white rounded-xl border border-stone-200 p-5 space-y-3">
        {[...Array(3)].map((_, i) => (
          <div key={i} className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-full bg-stone-200 shrink-0" />
            <div className="flex-1">
              <div className="h-3 w-48 bg-stone-200 rounded mb-1" />
              <div className="h-2.5 w-32 bg-stone-100 rounded" />
            </div>
            <div className="w-14 h-5 bg-stone-200 rounded-full" />
          </div>
        ))}
      </div>
    </div>
  )
}

/* ── Credential card ─────────────────────────────────────────────── */

function CredentialCard({ cred }) {
  const types = Array.isArray(cred.type)
    ? cred.type.filter((t) => t !== 'VerifiableCredential')
    : [cred.type || 'Credential']

  return (
    <div className={`relative overflow-hidden rounded-xl border p-4 ${
      cred.verified ? 'border-green-200 bg-green-50' : 'border-red-200 bg-red-50'
    }`}>
      <TechCardBg variant="circuit" className={cred.verified ? '!text-green-400' : '!text-red-400'} />
      <div className="relative z-10 flex items-start gap-3">
        <span className="text-xl mt-0.5">{cred.verified ? '✅' : '❌'}</span>
        <div className="flex-1 min-w-0">
          <p className="font-semibold text-stone-800 text-sm truncate">
            {types.join(', ') || 'Credential'}
          </p>
          {cred.issuance_date && (
            <p className="text-xs text-stone-500 mt-0.5">
              Issued: {cred.issuance_date.slice(0, 10)}
            </p>
          )}
          {cred.issuer && (
            <p className="text-xs text-stone-400 truncate mt-0.5">
              Issuer: {typeof cred.issuer === 'string' ? cred.issuer : JSON.stringify(cred.issuer)}
            </p>
          )}
        </div>
        <span className={`shrink-0 text-xs font-medium px-2 py-0.5 rounded-full ${
          cred.verified ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'
        }`}>
          {cred.verified ? 'Verified' : 'Invalid'}
        </span>
      </div>
    </div>
  )
}

/* ── Stat pill ───────────────────────────────────────────────────── */

function StatPill({ label, value, accent = 'violet' }) {
  const colors = {
    violet: 'bg-violet-50 border-violet-200 text-violet-700',
    green:  'bg-green-50  border-green-200  text-green-700',
    blue:   'bg-blue-50   border-blue-200   text-blue-700',
    amber:  'bg-amber-50  border-amber-200  text-amber-700',
  }
  return (
    <div className={`rounded-xl border px-4 py-3 text-center ${colors[accent]}`}>
      <div className="text-xl font-bold">{value ?? '—'}</div>
      <div className="text-[10px] uppercase tracking-wide mt-0.5 opacity-70">{label}</div>
    </div>
  )
}

/* ── Main page ───────────────────────────────────────────────────── */

export default function DidVerifier() {
  const { t } = useTranslation()
  const [searchParams, setSearchParams] = useSearchParams()

  const [input, setInput]     = useState(searchParams.get('did') || '')
  const [loading, setLoading] = useState(false)
  const [result, setResult]   = useState(null)
  const [error, setError]     = useState(null)

  const handleSearch = async (e) => {
    e?.preventDefault()
    const trimmed = input.trim()
    if (!trimmed) return
    setSearchParams({ did: trimmed })
    setLoading(true)
    setError(null)
    setResult(null)
    try {
      const data = await verifyDid(trimmed)
      setResult(data)
    } catch (err) {
      if (err.status === 404) {
        setError('No credentials found for this DID. The identity may not be registered on Voice Ledger.')
      } else if (err.status >= 500) {
        setError('Server error while verifying credentials. Please try again.')
      } else {
        setError(err.message || 'Verification failed. Check the DID and try again.')
      }
    } finally {
      setLoading(false)
    }
  }

  const summary = result?.summary || {}
  const creds   = result?.credentials || []
  const user    = result?.user_info   || {}
  const allOk   = creds.length > 0 && creds.every((c) => c.verified)

  return (
    <div className="max-w-4xl mx-auto px-4 py-8">

      {/* Header */}
      <div className="relative mb-2">
        <PageHeroBg variant="tracking" />
        <h1 className="text-2xl font-extrabold text-stone-900 flex items-center gap-2 page-header-accent">
          🪪 {t('nav_did', 'DID Verifier')}
        </h1>
      </div>
      <p className="text-sm text-stone-500 mb-6">
        Look up any registered identity and verify their credentials — organic certifications,
        farm registrations, and track record. No authentication required.
      </p>

      {/* Search */}
      <form
        onSubmit={handleSearch}
        className="flex flex-col sm:flex-row gap-2 mb-8"
      >
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="did:key:z6MkhaXgBZ… or paste a full DID"
          className="flex-1 px-4 py-2.5 rounded-lg border border-stone-300 text-sm outline-none focus:border-stone-400 focus:ring-2 focus:ring-stone-200 transition"
        />
        <button
          type="submit"
          disabled={loading || !input.trim()}
          className="bg-stone-900 text-white font-medium rounded-lg px-6 py-2.5 text-sm hover:bg-stone-800 hover:scale-105 active:scale-95 transition-all disabled:opacity-50 shrink-0"
        >
          {loading ? 'Verifying…' : 'Verify'}
        </button>
      </form>

      <div className="space-y-6">

        {loading && <DidSkeleton />}

        {error && (
          <div className="rounded-xl border border-amber-200 bg-amber-50 p-5 text-sm text-amber-800">
            <strong className="block mb-1">Identity not found</strong>
            {error}
          </div>
        )}

        {result && (
          <>
            {/* Identity summary */}
            <div className="relative overflow-hidden rounded-xl border border-stone-200 bg-white p-5 hover:shadow-md transition-shadow">
              <TechCardBg variant="circuit" className="!text-violet-400" />
              <div className="relative z-10">
                <div className="flex items-start gap-3">
                  <span className="text-2xl">🪪</span>
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2 flex-wrap">
                      {user.name && (
                        <span className="font-semibold text-stone-800">{user.name}</span>
                      )}
                      <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${
                        allOk ? 'bg-green-100 text-green-700' : 'bg-amber-100 text-amber-700'
                      }`}>
                        {allOk
                          ? '✅ All verified'
                          : `⚠️ ${summary.verified_credentials ?? 0}/${summary.total_credentials ?? 0} verified`}
                      </span>
                    </div>
                    <code className="mt-1 block text-[11px] text-stone-400 break-all">
                      {result.did}
                    </code>
                    {user.created_at && (
                      <p className="text-xs text-stone-400 mt-1">
                        Registered: {user.created_at.slice(0, 10)}
                      </p>
                    )}
                  </div>
                </div>

                {/* Stats */}
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mt-4">
                  <StatPill label="Credit Score" value={summary.credit_score}  accent="violet" />
                  <StatPill label="Batches"      value={summary.total_batches} accent="green" />
                  <StatPill
                    label="Volume (kg)"
                    value={summary.total_volume_kg != null
                      ? Number(summary.total_volume_kg).toLocaleString()
                      : null}
                    accent="blue"
                  />
                  <StatPill label="Days Active"  value={summary.days_active}   accent="amber" />
                </div>
              </div>
            </div>

            {/* Credentials */}
            <div>
              <h2 className="text-sm font-semibold text-stone-700 mb-3 flex items-center gap-2">
                <span>📜</span>
                Verifiable Credentials
                <span className="text-xs font-normal text-stone-400">({creds.length})</span>
              </h2>
              {creds.length === 0 ? (
                <EmptyState message="No credentials found for this DID." />
              ) : (
                <div className="space-y-3">
                  {creds.map((cred, i) => (
                    <CredentialCard key={cred.credential_id || i} cred={cred} />
                  ))}
                </div>
              )}
            </div>
          </>
        )}

        {!loading && !result && !error && (
          <EmptyState
            message="Enter a DID above to verify identity and credentials."
          />
        )}

        {/* About */}
        <div className="rounded-xl border border-stone-200 bg-white p-5 text-sm text-stone-600 space-y-2">
          <h3 className="font-semibold text-stone-800">About DID Verification</h3>
          <p>
            Every registered farmer, cooperative, and exporter on the Voice Ledger network
            has a <strong>Decentralized Identifier (DID)</strong> based on the W3C DID Core
            standard. Their credentials — farm registrations, organic certifications, batch
            track record — are issued as <strong>W3C Verifiable Credentials</strong> and
            cryptographically signed.
          </p>
        </div>

      </div>
    </div>
  )
}
