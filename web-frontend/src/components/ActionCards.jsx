/**
 * ActionCards — Renders structured data from LiveKit agent via data channel.
 *
 * Each card type maps to a purpose-built card component.
 * Cards arrive as JSON strings on the `vl.action` text stream.
 */

import { useState, useMemo } from 'react'

/* ================================================================
   Dispatcher — parse incoming streams → route to card
   ================================================================ */

export default function ActionCards({ textStreams }) {
  const cards = useMemo(() => {
    if (!textStreams || textStreams.length === 0) return []
    return textStreams.map((raw, idx) => {
      try {
        // TextStreamData has .text (string), .participantInfo, .streamInfo
        const jsonStr = typeof raw === 'string' ? raw : raw?.text
        if (!jsonStr) return null
        const data = JSON.parse(jsonStr)
        return { ...data, _key: `${data.type}-${idx}` }
      } catch {
        return null
      }
    }).filter(Boolean)
  }, [textStreams])

  if (cards.length === 0) return null

  return (
    <div className="space-y-3">
      {cards.map((card) => {
        switch (card.type) {
          case 'batch_detail':
            return <BatchDetailCard key={card._key} data={card} />
          case 'batch_list':
            return <BatchListCard key={card._key} data={card} />
          case 'dpp_passport':
            return <DppPassportCard key={card._key} data={card} />
          default:
            return <GenericCard key={card._key} data={card} />
        }
      })}
    </div>
  )
}


/* ================================================================
   Shared card shell — glass-morphism wrapper
   ================================================================ */

function CardShell({ children, icon, title, accent = '#10B981' }) {
  return (
    <div className="rounded-2xl overflow-hidden"
         style={{
           background: 'rgba(255,255,255,0.04)',
           border: '1px solid rgba(255,255,255,0.06)',
           backdropFilter: 'blur(16px)',
         }}>
      {/* Header */}
      <div className="flex items-center gap-2 px-4 py-2.5"
           style={{ borderBottom: '1px solid rgba(255,255,255,0.04)' }}>
        <span style={{ color: accent }}>{icon}</span>
        <span className="text-xs font-semibold tracking-wide text-white/80">{title}</span>
      </div>
      {/* Body */}
      <div className="px-4 py-3">{children}</div>
    </div>
  )
}

function Field({ label, value, mono = false }) {
  if (!value && value !== 0) return null
  return (
    <div className="flex justify-between items-baseline py-0.5">
      <span className="text-[10px] text-white/30 uppercase tracking-wider">{label}</span>
      <span className={`text-xs text-white/70 ${mono ? 'font-mono' : ''}`}>{value}</span>
    </div>
  )
}

function StatusPill({ status }) {
  const color = {
    harvested: 'bg-emerald-500/20 text-emerald-300',
    processed: 'bg-blue-500/20 text-blue-300',
    exported: 'bg-purple-500/20 text-purple-300',
    delivered: 'bg-cyan-500/20 text-cyan-300',
    roasted: 'bg-amber-500/20 text-amber-300',
  }[status?.toLowerCase()] || 'bg-gray-500/20 text-gray-300'

  return (
    <span className={`inline-block px-2 py-0.5 rounded-full text-[10px] font-medium ${color}`}>
      {status || '—'}
    </span>
  )
}


/* ================================================================
   BatchDetailCard — single batch details
   ================================================================ */

function BatchDetailCard({ data }) {
  const b = data.batch || data
  return (
    <CardShell
      icon={<CoffeeIcon />}
      title="Batch Detail"
      accent="#10B981"
    >
      <Field label="Batch ID" value={b.batch_id || b.id} mono />
      <Field label="Origin" value={b.origin} />
      <Field label="Variety" value={b.variety} />
      <Field label="Grade" value={b.quality_grade || b.grade} />
      <Field label="Weight" value={b.quantity_kg ? `${b.quantity_kg} kg` : (b.weight_kg ? `${b.weight_kg} kg` : null)} />
      <Field label="Altitude" value={b.altitude ? `${b.altitude} m` : null} />
      <Field label="Processing" value={b.processing_method} />
      <div className="flex justify-between items-center pt-1">
        <span className="text-[10px] text-white/30 uppercase tracking-wider">Status</span>
        <StatusPill status={b.status} />
      </div>
      {b.farmer_name && <Field label="Farmer" value={b.farmer_name} />}
      {b.cooperative && <Field label="Cooperative" value={b.cooperative} />}
      {b.harvest_date && <Field label="Harvested" value={b.harvest_date} />}
    </CardShell>
  )
}


/* ================================================================
   BatchListCard — list of batches
   ================================================================ */

function BatchListCard({ data }) {
  const batches = data.batches || []
  const [expanded, setExpanded] = useState(false)
  const visible = expanded ? batches : batches.slice(0, 3)

  return (
    <CardShell
      icon={<ListIcon />}
      title={`Batches (${data.count || batches.length})`}
      accent="#10B981"
    >
      <div className="space-y-2">
        {visible.map((b, i) => (
          <div key={i} className="flex items-center justify-between px-2 py-1.5 rounded-lg"
               style={{ background: 'rgba(255,255,255,0.03)' }}>
            <div className="flex flex-col">
              <span className="text-xs text-white/70 font-mono">{b.batch_id || b.id}</span>
              <span className="text-[10px] text-white/30">{b.origin} {b.variety ? `• ${b.variety}` : ''}</span>
            </div>
            <StatusPill status={b.status} />
          </div>
        ))}
      </div>
      {batches.length > 3 && (
        <button onClick={() => setExpanded(v => !v)}
                className="w-full mt-2 text-[10px] text-emerald-400/60 hover:text-emerald-400 transition-colors">
          {expanded ? 'Show less' : `Show all ${batches.length} batches`}
        </button>
      )}
    </CardShell>
  )
}


/* ================================================================
   DppPassportCard — Digital Product Passport
   ================================================================ */

function DppPassportCard({ data }) {
  const p = data.product || {}
  const o = data.origin || {}
  const c = data.compliance || {}
  const bc = data.blockchain || {}
  const certs = data.certifications || []
  const [showFull, setShowFull] = useState(false)

  return (
    <CardShell
      icon={<DppIcon />}
      title="Digital Product Passport"
      accent="#06B6D4"
    >
      {/* Product summary */}
      <Field label="Batch" value={p.batch_id || data.batch_id} mono />
      <Field label="Grade" value={p.grade} />
      <Field label="Weight" value={p.quantity_kg ? `${p.quantity_kg} kg` : null} />
      <Field label="Processing" value={p.processing} />

      {/* Origin */}
      {(o.region || o.country) && (
        <div className="mt-2 pt-2" style={{ borderTop: '1px solid rgba(255,255,255,0.04)' }}>
          <span className="text-[10px] text-white/20 uppercase tracking-widest">Origin</span>
          <Field label="Region" value={o.region} />
          <Field label="Country" value={o.country || 'Ethiopia'} />
          <Field label="Altitude" value={o.altitude ? `${o.altitude} m` : null} />
        </div>
      )}

      {/* Compliance */}
      {c.eudr_compliant !== undefined && (
        <div className="mt-2 pt-2" style={{ borderTop: '1px solid rgba(255,255,255,0.04)' }}>
          <span className="text-[10px] text-white/20 uppercase tracking-widest">Compliance</span>
          <div className="flex justify-between items-center py-0.5">
            <span className="text-[10px] text-white/30">EUDR</span>
            <span className={`text-xs font-semibold ${c.eudr_compliant ? 'text-emerald-400' : 'text-red-400'}`}>
              {c.eudr_compliant ? '✓ Compliant' : '✗ Non-compliant'}
            </span>
          </div>
          {c.deforestation_risk !== undefined && (
            <div className="flex justify-between items-center py-0.5">
              <span className="text-[10px] text-white/30">Deforestation Risk</span>
              <span className={`text-xs font-semibold ${
                c.deforestation_risk === 'low' ? 'text-emerald-400' :
                c.deforestation_risk === 'medium' ? 'text-amber-400' : 'text-red-400'
              }`}>
                {c.deforestation_risk || 'Unknown'}
              </span>
            </div>
          )}
        </div>
      )}

      {/* Certs */}
      {certs.length > 0 && (
        <div className="mt-2 pt-2 flex flex-wrap gap-1" style={{ borderTop: '1px solid rgba(255,255,255,0.04)' }}>
          {certs.map((cert, i) => (
            <span key={i} className="inline-block px-2 py-0.5 rounded-full text-[9px] font-medium bg-cyan-500/15 text-cyan-300/70">
              {cert.name || cert}
            </span>
          ))}
        </div>
      )}

      {/* Blockchain */}
      {bc.tx_hash && (
        <div className="mt-2 pt-2" style={{ borderTop: '1px solid rgba(255,255,255,0.04)' }}>
          <span className="text-[10px] text-white/20 uppercase tracking-widest">Blockchain</span>
          <Field label="Tx Hash" value={`${bc.tx_hash.slice(0, 10)}…${bc.tx_hash.slice(-6)}`} mono />
          {bc.network && <Field label="Network" value={bc.network} />}
          {bc.ipfs_cid && <Field label="IPFS CID" value={`${bc.ipfs_cid.slice(0, 12)}…`} mono />}
        </div>
      )}

      {/* QR link */}
      {(data.qr?.url || data.qr?.image_url) && (
        <div className="mt-3 flex justify-center">
          <button onClick={() => window.open(data.qr.url || data.qr.image_url, '_blank')}
                  className="text-[10px] text-cyan-400/60 hover:text-cyan-400 transition-colors">
            Open full passport ↗
          </button>
        </div>
      )}
    </CardShell>
  )
}


/* ================================================================
   GenericCard — fallback for unknown types
   ================================================================ */

function GenericCard({ data }) {
  return (
    <CardShell icon={<InfoIcon />} title={data.type || 'Info'} accent="#6B7280">
      <pre className="text-[10px] text-white/40 whitespace-pre-wrap overflow-x-auto">
        {JSON.stringify(data, null, 2)}
      </pre>
    </CardShell>
  )
}


/* ================================================================
   Micro-icons
   ================================================================ */

function CoffeeIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round">
      <path d="M2 5h8v5a3 3 0 01-3 3H5a3 3 0 01-3-3V5z" />
      <path d="M10 6h1a2 2 0 010 4h-1" />
      <path d="M4 1v2M6 1v2M8 1v2" />
    </svg>
  )
}

function ListIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round">
      <path d="M4 3h8M4 7h8M4 11h6" />
      <circle cx="2" cy="3" r="0.5" fill="currentColor" />
      <circle cx="2" cy="7" r="0.5" fill="currentColor" />
      <circle cx="2" cy="11" r="0.5" fill="currentColor" />
    </svg>
  )
}

function DppIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" strokeLinejoin="round">
      <rect x="2" y="1" width="10" height="12" rx="1.5" />
      <path d="M5 4h4M5 7h4M5 10h2" />
    </svg>
  )
}

function InfoIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round">
      <circle cx="7" cy="7" r="5.5" />
      <path d="M7 6v4M7 4.5v0" />
    </svg>
  )
}
