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
          /* ── Batch ── */
          case 'batch_detail':
            return <BatchDetailCard key={card._key} data={card} />
          case 'batch_list':
            return <BatchListCard key={card._key} data={card} />

          /* ── Supply-chain events ── */
          case 'record_commission':
            return <EventConfirmCard key={card._key} data={card} verb="Commissioned" accent="#10B981" />
          case 'record_shipment':
            return <EventConfirmCard key={card._key} data={card} verb="Shipped" accent="#6366F1" />
          case 'record_receipt':
            return <EventConfirmCard key={card._key} data={card} verb="Received" accent="#06B6D4" />
          case 'record_transformation':
            return <TransformationCard key={card._key} data={card} />
          case 'pack_batches':
            return <PackCard key={card._key} data={card} verb="Packed" />
          case 'unpack_batches':
            return <PackCard key={card._key} data={card} verb="Unpacked" />
          case 'split_batch':
            return <SplitCard key={card._key} data={card} />

          /* ── Knowledge ── */
          case 'search_knowledge':
            return <KnowledgeCard key={card._key} data={card} />

          /* ── Marketplace ── */
          case 'create_rfq':
            return <RfqCreatedCard key={card._key} data={card} />
          case 'browse_rfqs':
            return <RfqListCard key={card._key} data={card} />
          case 'submit_offer':
            return <OfferCard key={card._key} data={card} verb="Submitted" />
          case 'accept_offer':
            return <OfferCard key={card._key} data={card} verb="Accepted" accent="#10B981" />
          case 'list_my_offers':
            return <OfferListCard key={card._key} data={card} />
          case 'list_rfq_offers':
            return <RfqOffersCard key={card._key} data={card} />

          /* ── Containers & pools ── */
          case 'browse_containers':
            return <ContainerListCard key={card._key} data={card} />
          case 'purchase_container':
            return <PurchaseCard key={card._key} data={card} />
          case 'browse_pools':
            return <PoolListCard key={card._key} data={card} />
          case 'commit_to_pool':
            return <PoolCommitCard key={card._key} data={card} />
          case 'list_my_commitments':
            return <CommitmentListCard key={card._key} data={card} />

          /* ── Compliance ── */
          case 'check_eudr_compliance':
            return <EudrComplianceCard key={card._key} data={card} />
          case 'check_mass_balance':
            return <MassBalanceCard key={card._key} data={card} />

          /* ── DPP / Traceability ── */
          case 'dpp_passport':
            return <DppPassportCard key={card._key} data={card} />
          case 'get_container_dpp':
            return <ContainerDppCard key={card._key} data={card} />
          case 'trace_lineage':
            return <LineageCard key={card._key} data={card} />
          case 'validate_dpp':
            return <ValidateDppCard key={card._key} data={card} />

          /* ── Verification ── */
          case 'list_pending_verifications':
            return <PendingVerificationsCard key={card._key} data={card} />
          case 'verify_batch':
            return <VerifyBatchCard key={card._key} data={card} />

          /* ── Blockchain ── */
          case 'check_blockchain_anchor':
            return <BlockchainAnchorCard key={card._key} data={card} />
          case 'get_token_info':
            return <TokenInfoCard key={card._key} data={card} />
          case 'verify_batch_hash':
            return <HashVerifyCard key={card._key} data={card} />

          /* ── DON / CRE ── */
          case 'request_don_attestation':
            return <DonAttestCard key={card._key} data={card} verb="Requested" />
          case 'check_don_attestation':
            return <DonAttestCard key={card._key} data={card} verb="Result" />
          case 'get_don_provenance_metrics':
            return <ProvenanceMetricsCard key={card._key} data={card} />

          /* ── Settlement ── */
          case 'confirm_payment':
          case 'check_payment_status':
          case 'record_cooperative_payout':
          case 'confirm_payment_received':
            return <PaymentCard key={card._key} data={card} />
          case 'dispute_payment':
            return <DisputePaymentCard key={card._key} data={card} />
          case 'confirm_shipment':
            return <ShipmentConfirmCard key={card._key} data={card} />
          case 'confirm_delivery':
            return <DeliveryConfirmCard key={card._key} data={card} />

          /* ── DeFi ── */
          case 'check_financing_pool':
            return <FinancingPoolCard key={card._key} data={card} />
          case 'request_financing_advance':
            return <FinancingAdvanceCard key={card._key} data={card} />
          case 'check_trade_financing':
            return <TradeFinancingCard key={card._key} data={card} />

          /* ── Logistics / LSP Milestones */
          case 'ingest_milestone':
            return <MilestoneCard key={card._key} data={card} />

          /* ── Webhook Subscription Management*/
          case 'register_webhook_subscription':
            return <WebhookRegisteredCard key={card._key} data={card} />
          case 'list_webhook_subscriptions':
            return <WebhookListCard key={card._key} data={card} />
          case 'unregister_webhook_subscription':
            return <WebhookRemovedCard key={card._key} data={card} />

          /* ── Shipment Status / Timeline*/
          case 'get_shipment_status':
            return <ShipmentStatusCard key={card._key} data={card} />

          /* ── SSI / DID Verification ── */
          case 'verify_did':
            return <VerifyDidCard key={card._key} data={card} />

          default:
            return <GenericCard key={card._key} data={card} />
        }
      })}
    </div>
  )
}


/* ================================================================
   Shared card shell — premium SVG tech design matching hero theme
   ================================================================ */

/* ── Animated trace border for action cards ── */
function ActionTraceBorder({ accent }) {
  return (
    <svg
      className="absolute inset-0 w-full h-full pointer-events-none"
      viewBox="0 0 300 200"
      preserveAspectRatio="none"
      fill="none"
    >
      {/* Dim static border */}
      <rect x="1" y="1" width="298" height="198" rx="15" stroke={accent} strokeWidth="0.5" strokeOpacity="0.12" />
      {/* Animated racing trace */}
      <rect
        x="1" y="1" width="298" height="198" rx="15"
        stroke={accent} strokeWidth="1.2" strokeOpacity="0"
        strokeDasharray="80 920"
        className="animate-card-trace"
      />
      {/* Corner accent dots */}
      <circle cx="16" cy="16" r="1.2" fill={accent} opacity="0.2" />
      <circle cx="284" cy="16" r="1.2" fill={accent} opacity="0.2" />
      <circle cx="16" cy="184" r="1" fill={accent} opacity="0.1" />
      <circle cx="284" cy="184" r="1" fill={accent} opacity="0.1" />
    </svg>
  )
}

/* ── Subtle SVG background pattern for action cards ── */
function ActionCardBg({ accent }) {
  return (
    <svg
      className="absolute inset-0 w-full h-full pointer-events-none"
      viewBox="0 0 200 120"
      preserveAspectRatio="xMidYMid slice"
      fill="none"
    >
      {/* Circuit traces */}
      <g stroke={accent} strokeWidth="0.3" opacity="0.06">
        <path d="M0 25h30v15h20" />
        <path d="M160 10h20v20h20" />
        <path d="M50 90h25v-15h15" />
        <path d="M140 100h30v-20" />
        <path d="M10 70h15" />
        <path d="M175 60v25" />
      </g>
      {/* Junction dots */}
      <g fill={accent} opacity="0.08">
        <circle cx="30" cy="25" r="1.5" />
        <circle cx="50" cy="40" r="1" />
        <circle cx="180" cy="10" r="1.5" />
        <circle cx="200" cy="30" r="1" />
        <circle cx="75" cy="90" r="1" />
        <circle cx="90" cy="75" r="1.5" />
        <circle cx="170" cy="100" r="1" />
      </g>
      {/* Faint hex accents */}
      <g stroke={accent} strokeWidth="0.25" fill="none" opacity="0.04">
        <polygon points="120,20 127,24 127,32 120,36 113,32 113,24" />
        <polygon points="145,70 152,74 152,82 145,86 138,82 138,74" />
      </g>
    </svg>
  )
}

function CardShell({ children, icon, title, accent = '#10B981' }) {
  return (
    <div className="group relative rounded-2xl overflow-hidden transition-all duration-300 hover:scale-[1.01] hover:shadow-lg"
         style={{
           background: 'rgba(255,255,255,0.03)',
           backdropFilter: 'blur(16px)',
         }}>
      {/* SVG animated trace border */}
      <ActionTraceBorder accent={accent} />

      {/* SVG background pattern */}
      <ActionCardBg accent={accent} />

      {/* Hover glow */}
      <div
        className="absolute inset-0 opacity-0 group-hover:opacity-100 transition-opacity duration-500 pointer-events-none"
        style={{
          background: `radial-gradient(ellipse at 50% 0%, ${accent}10 0%, transparent 70%)`,
        }}
      />

      {/* Header */}
      <div className="relative z-10 flex items-center gap-2.5 px-4 py-2.5"
           style={{ borderBottom: '1px solid rgba(255,255,255,0.04)' }}>
        <span style={{ color: accent }}>{icon}</span>
        <span className="text-xs font-bold tracking-wide" style={{ color: `${accent}DD` }}>{title}</span>
        {/* Header accent line */}
        <div className="flex-1 h-px" style={{ background: `linear-gradient(to right, ${accent}20, transparent)` }} />
      </div>

      {/* Body */}
      <div className="relative z-10 px-4 py-3">{children}</div>
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
   EventConfirmCard — supply-chain event (commission, shipment, receipt)
   ================================================================ */

function EventConfirmCard({ data, verb = 'Recorded', accent = '#10B981' }) {
  return (
    <CardShell icon={<CheckIcon />} title={verb} accent={accent}>
      <Field label="Batch ID" value={data.batch_id} mono />
      <Field label="Quantity" value={data.quantity_kg ? `${data.quantity_kg} kg` : null} />
      <Field label="Origin" value={data.origin} />
      <Field label="Variety" value={data.variety} />
      <Field label="Destination" value={data.destination} />
      <Field label="Condition" value={data.condition} />
      <Field label="Status" value={data.status} />
      <TxFooter data={data} />
    </CardShell>
  )
}


/* ================================================================
   TransformationCard — roasting / milling / drying
   ================================================================ */

function TransformationCard({ data }) {
  return (
    <CardShell icon={<TransformIcon />} title="Transformation" accent="#F59E0B">
      <Field label="Input Batch" value={data.input_batch_id} mono />
      <Field label="Type" value={data.transformation_type} />
      <Field label="Output Batches" value={data.output_batch_ids?.join(', ')} mono />
      <Field label="Mass Loss" value={data.mass_loss_percent != null ? `${data.mass_loss_percent}%` : null} />
      <TxFooter data={data} />
    </CardShell>
  )
}


/* ================================================================
   PackCard — pack / unpack aggregation
   ================================================================ */

function PackCard({ data, verb = 'Packed' }) {
  return (
    <CardShell icon={<BoxIcon />} title={verb} accent="#8B5CF6">
      <Field label="Container" value={data.container_id} mono />
      {data.batch_ids?.length > 0 && (
        <div className="mt-1">
          <span className="text-[10px] text-white/30 uppercase tracking-wider">Batches ({data.batch_ids.length})</span>
          <div className="flex flex-wrap gap-1 mt-0.5">
            {data.batch_ids.map((id, i) => (
              <span key={i} className="inline-block px-1.5 py-0.5 rounded text-[9px] font-mono bg-violet-500/15 text-violet-300/80">{id}</span>
            ))}
          </div>
        </div>
      )}
      {data.container_token_id && <Field label="Token ID" value={`#${data.container_token_id}`} mono />}
      <TxFooter data={data} />
    </CardShell>
  )
}


/* ================================================================
   SplitCard — batch split into children
   ================================================================ */

function SplitCard({ data }) {
  return (
    <CardShell icon={<SplitIcon />} title="Split Batch" accent="#EC4899">
      <Field label="Parent" value={data.parent_batch_id} mono />
      {data.child_batch_ids?.length > 0 && (
        <div className="mt-1">
          <span className="text-[10px] text-white/30 uppercase tracking-wider">Children ({data.child_batch_ids.length})</span>
          <div className="flex flex-wrap gap-1 mt-0.5">
            {data.child_batch_ids.map((id, i) => (
              <span key={i} className="inline-block px-1.5 py-0.5 rounded text-[9px] font-mono bg-pink-500/15 text-pink-300/80">{id}</span>
            ))}
          </div>
        </div>
      )}
      <TxFooter data={data} />
    </CardShell>
  )
}


/* ================================================================
   KnowledgeCard — search_knowledge results
   ================================================================ */

function KnowledgeCard({ data }) {
  return (
    <CardShell icon={<SearchIcon />} title="Knowledge" accent="#A78BFA">
      {data.source_count != null && (
        <span className="text-[10px] text-white/30">{data.source_count} source(s) found</span>
      )}
      <p className="mt-1 text-xs text-white/60 leading-relaxed whitespace-pre-wrap">
        {data.context || 'No results found.'}
      </p>
    </CardShell>
  )
}


/* ================================================================
   RfqCreatedCard — newly created RFQ
   ================================================================ */

function RfqCreatedCard({ data }) {
  return (
    <CardShell icon={<MarketIcon />} title="RFQ Created" accent="#10B981">
      <Field label="RFQ #" value={data.rfq_number} mono />
      <Field label="Quantity" value={data.quantity_kg ? `${data.quantity_kg} kg` : null} />
      <Field label="Variety" value={data.variety} />
      <Field label="Broadcast" value={data.broadcast_count ? `${data.broadcast_count} cooperative(s)` : null} />
    </CardShell>
  )
}


/* ================================================================
   RfqListCard — browse RFQs
   ================================================================ */

function RfqListCard({ data }) {
  const rfqs = data.rfqs || []
  const [expanded, setExpanded] = useState(false)
  const visible = expanded ? rfqs : rfqs.slice(0, 4)

  return (
    <CardShell icon={<MarketIcon />} title={`RFQs (${data.count || rfqs.length})`} accent="#10B981">
      <div className="space-y-2">
        {visible.map((r, i) => (
          <div key={i} className="px-2 py-1.5 rounded-lg" style={{ background: 'rgba(255,255,255,0.03)' }}>
            <div className="flex justify-between items-center">
              <span className="text-xs text-white/70 font-mono">{r.rfq_number}</span>
              <StatusPill status={r.status} />
            </div>
            <div className="text-[10px] text-white/30 mt-0.5">
              {r.quantity_kg} kg {r.variety ? `• ${r.variety}` : ''} {r.buyer ? `• ${r.buyer}` : ''}
              {r.offer_count ? ` • ${r.offer_count} offer(s)` : ''}
            </div>
          </div>
        ))}
      </div>
      {rfqs.length > 4 && (
        <button onClick={() => setExpanded(v => !v)}
                className="w-full mt-2 text-[10px] text-emerald-400/60 hover:text-emerald-400 transition-colors">
          {expanded ? 'Show less' : `Show all ${rfqs.length}`}
        </button>
      )}
    </CardShell>
  )
}


/* ================================================================
   OfferCard — single offer submitted / accepted
   ================================================================ */

function OfferCard({ data, verb = 'Submitted', accent = '#6366F1' }) {
  return (
    <CardShell icon={<OfferIcon />} title={`Offer ${verb}`} accent={accent}>
      <Field label="Offer #" value={data.offer_number} mono />
      <Field label="RFQ #" value={data.rfq_number} mono />
      <Field label="Acceptance #" value={data.acceptance_number} mono />
      <Field label="Quantity" value={data.quantity_offered_kg ? `${data.quantity_offered_kg} kg` : (data.quantity_accepted_kg ? `${data.quantity_accepted_kg} kg` : null)} />
      <Field label="Price" value={data.price_per_kg ? `$${data.price_per_kg}/kg` : null} />
      <Field label="Cooperative" value={data.cooperative} />
    </CardShell>
  )
}


/* ================================================================
   OfferListCard — list of my offers
   ================================================================ */

function OfferListCard({ data }) {
  const offers = data.offers || []
  const [expanded, setExpanded] = useState(false)
  const visible = expanded ? offers : offers.slice(0, 4)

  return (
    <CardShell icon={<OfferIcon />} title={`My Offers (${data.count || offers.length})`} accent="#6366F1">
      <div className="space-y-2">
        {visible.map((o, i) => (
          <div key={i} className="flex justify-between items-center px-2 py-1.5 rounded-lg"
               style={{ background: 'rgba(255,255,255,0.03)' }}>
            <div className="flex flex-col">
              <span className="text-xs text-white/70 font-mono">{o.offer_number}</span>
              <span className="text-[10px] text-white/30">{o.rfq_number} • {o.quantity_offered_kg} kg • ${o.price_per_kg}/kg</span>
            </div>
            <StatusPill status={o.status} />
          </div>
        ))}
      </div>
      {offers.length > 4 && (
        <button onClick={() => setExpanded(v => !v)}
                className="w-full mt-2 text-[10px] text-indigo-400/60 hover:text-indigo-400 transition-colors">
          {expanded ? 'Show less' : `Show all ${offers.length}`}
        </button>
      )}
    </CardShell>
  )
}


/* ================================================================
   RfqOffersCard — list offers for a specific RFQ (buyer view)
   ================================================================ */

function RfqOffersCard({ data }) {
  const offers = data.offers || []
  const [expanded, setExpanded] = useState(false)
  const visible = expanded ? offers : offers.slice(0, 4)

  return (
    <CardShell icon={<OfferIcon />} title={`Offers for ${data.rfq_number} (${data.count || offers.length})`} accent="#10B981">
      <div className="space-y-2">
        {data.quantity_requested_kg && (
          <Field label="Requested" value={`${data.quantity_requested_kg} kg`} />
        )}
        {data.variety && <Field label="Variety" value={data.variety} />}
        {visible.length > 0 && (
          <div className="mt-2 pt-2" style={{ borderTop: '1px solid rgba(255,255,255,0.04)' }}>
            <span className="text-[10px] text-white/20 uppercase tracking-wider">Offers</span>
          </div>
        )}
        <div className="space-y-2">
          {visible.map((o, i) => (
            <div key={i} className="px-2 py-1.5 rounded-lg" style={{ background: 'rgba(255,255,255,0.03)' }}>
              <div className="flex justify-between items-center">
                <span className="text-xs text-white/70 font-mono">{o.offer_number}</span>
                <StatusPill status={o.status} />
              </div>
              <div className="text-[10px] text-white/30 mt-0.5">
                {o.cooperative_name} • {o.quantity_offered_kg} kg • ${o.price_per_kg}/kg
                {o.total_value_usd && ` • $${o.total_value_usd.toLocaleString()} total`}
              </div>
              {o.delivery_timeline && (
                <div className="text-[9px] text-white/20 mt-0.5">
                  Delivery: {o.delivery_timeline}
                </div>
              )}
            </div>
          ))}
        </div>
      </div>
      {offers.length > 4 && (
        <button onClick={() => setExpanded(v => !v)}
                className="w-full mt-2 text-[10px] text-emerald-400/60 hover:text-emerald-400 transition-colors">
          {expanded ? 'Show less' : `Show all ${offers.length}`}
        </button>
      )}
    </CardShell>
  )
}


/* ================================================================
   ContainerListCard — browse container offerings
   ================================================================ */

function ContainerListCard({ data }) {
  const containers = data.containers || []
  const [expanded, setExpanded] = useState(false)
  const visible = expanded ? containers : containers.slice(0, 3)

  return (
    <CardShell icon={<BoxIcon />} title={`Containers (${data.count || containers.length})`} accent="#8B5CF6">
      <div className="space-y-2">
        {visible.map((c, i) => (
          <div key={i} className="px-2 py-1.5 rounded-lg" style={{ background: 'rgba(255,255,255,0.03)' }}>
            <div className="flex justify-between items-center">
              <span className="text-xs text-white/70 font-mono">{c.container_sscc || `#${c.id}`}</span>
              <StatusPill status={c.status} />
            </div>
            <div className="text-[10px] text-white/30 mt-0.5">
              {c.available_quantity_kg}/{c.total_quantity_kg} kg avail
              {c.price_per_kg ? ` • $${c.price_per_kg}/kg` : ''}
              {c.variety ? ` • ${c.variety}` : ''}
            </div>
          </div>
        ))}
      </div>
      {containers.length > 3 && (
        <button onClick={() => setExpanded(v => !v)}
                className="w-full mt-2 text-[10px] text-violet-400/60 hover:text-violet-400 transition-colors">
          {expanded ? 'Show less' : `Show all ${containers.length}`}
        </button>
      )}
    </CardShell>
  )
}


/* ================================================================
   PurchaseCard — container purchase confirmation
   ================================================================ */

function PurchaseCard({ data }) {
  return (
    <CardShell icon={<CartIcon />} title="Purchase Confirmed" accent="#10B981">
      <Field label="Acceptance #" value={data.acceptance_number} mono />
      <Field label="Container" value={data.container_sscc} mono />
      <Field label="Cooperative" value={data.cooperative} />
      <Field label="Quantity" value={data.quantity_kg ? `${data.quantity_kg} kg` : null} />
      <Field label="Price" value={data.price_per_kg ? `$${data.price_per_kg}/kg` : null} />
      <Field label="Total" value={data.total_amount_usd ? `$${Number(data.total_amount_usd).toLocaleString()}` : null} />
      <Field label="Payment" value={data.payment_status} />
    </CardShell>
  )
}


/* ================================================================
   PoolListCard — browse shared-buying pools
   ================================================================ */

function PoolListCard({ data }) {
  const pools = data.pools || []
  const [expanded, setExpanded] = useState(false)
  const visible = expanded ? pools : pools.slice(0, 3)

  return (
    <CardShell icon={<PoolIcon />} title={`Pools (${data.count || pools.length})`} accent="#0EA5E9">
      <div className="space-y-2">
        {visible.map((p, i) => (
          <div key={i} className="px-2 py-1.5 rounded-lg" style={{ background: 'rgba(255,255,255,0.03)' }}>
            <div className="flex justify-between items-center">
              <span className="text-xs text-white/70">{p.destination_region || p.container_sscc}</span>
              <StatusPill status={p.status} />
            </div>
            <div className="mt-1">
              <ProgressBar pct={p.fill_pct || 0} />
            </div>
            <div className="text-[10px] text-white/30 mt-0.5">
              {p.filled_kg}/{p.fill_target_kg} kg • {p.buyer_count || 0} buyer(s) • ${p.price_per_kg}/kg
            </div>
          </div>
        ))}
      </div>
      {pools.length > 3 && (
        <button onClick={() => setExpanded(v => !v)}
                className="w-full mt-2 text-[10px] text-sky-400/60 hover:text-sky-400 transition-colors">
          {expanded ? 'Show less' : `Show all ${pools.length}`}
        </button>
      )}
    </CardShell>
  )
}


/* ================================================================
   PoolCommitCard — buyer committed to a pool
   ================================================================ */

function PoolCommitCard({ data }) {
  return (
    <CardShell icon={<PoolIcon />} title="Pool Commitment" accent="#0EA5E9">
      <Field label="Commitment #" value={data.commitment_id} mono />
      <Field label="Container" value={data.container_sscc} mono />
      <Field label="Cooperative" value={data.cooperative} />
      <Field label="Quantity" value={data.quantity_kg ? `${data.quantity_kg} kg` : null} />
      <Field label="Price" value={data.price_per_kg ? `$${data.price_per_kg}/kg` : null} />
      <Field label="Total" value={data.total_amount ? `$${Number(data.total_amount).toLocaleString()}` : null} />
      <Field label="Destination" value={[data.destination_region, data.destination_port].filter(Boolean).join(' → ')} />
      {data.pool_fill_pct != null && (
        <div className="mt-1.5">
          <ProgressBar pct={data.pool_fill_pct} label={`Pool ${data.pool_status || ''}`} />
        </div>
      )}
    </CardShell>
  )
}


/* ================================================================
   CommitmentListCard — buyer's pool commitments
   ================================================================ */

function CommitmentListCard({ data }) {
  const items = data.commitments || []
  const [expanded, setExpanded] = useState(false)
  const visible = expanded ? items : items.slice(0, 3)

  return (
    <CardShell icon={<PoolIcon />} title={`My Commitments (${data.count || items.length})`} accent="#0EA5E9">
      <div className="space-y-2">
        {visible.map((c, i) => (
          <div key={i} className="px-2 py-1.5 rounded-lg" style={{ background: 'rgba(255,255,255,0.03)' }}>
            <div className="flex justify-between items-center">
              <span className="text-xs text-white/70 font-mono">#{c.commitment_id}</span>
              <StatusPill status={c.commitment_status || c.pool_status} />
            </div>
            <div className="text-[10px] text-white/30 mt-0.5">
              {c.quantity_kg} kg • ${c.unit_price}/kg → {c.destination_region}
            </div>
          </div>
        ))}
      </div>
      {items.length > 3 && (
        <button onClick={() => setExpanded(v => !v)}
                className="w-full mt-2 text-[10px] text-sky-400/60 hover:text-sky-400 transition-colors">
          {expanded ? 'Show less' : `Show all ${items.length}`}
        </button>
      )}
    </CardShell>
  )
}


/* ================================================================
   EudrComplianceCard — EUDR compliance check
   ================================================================ */

function EudrComplianceCard({ data }) {
  const checks = data.checks || {}
  const results = data.batch_results || []

  return (
    <CardShell
      icon={<ShieldIcon />}
      title="EUDR Compliance"
      accent={data.compliant ? '#10B981' : '#EF4444'}
    >
      <div className="flex items-center gap-2 mb-2">
        <span className={`text-sm font-semibold ${data.compliant ? 'text-emerald-400' : 'text-red-400'}`}>
          {data.compliant ? '✓ Compliant' : '✗ Non-compliant'}
        </span>
        {data.batch_count && <span className="text-[10px] text-white/30">({data.batch_count} batch{data.batch_count > 1 ? 'es' : ''})</span>}
      </div>
      <ComplianceCheck label="GPS Coordinates" ok={checks.gps_coordinates} />
      <ComplianceCheck label="Photo Verified" ok={checks.photo_verification} />
      <ComplianceCheck label="Deforestation Clear" ok={checks.deforestation_clear} />
      {results.length > 0 && (
        <div className="mt-2 pt-2 space-y-1" style={{ borderTop: '1px solid rgba(255,255,255,0.04)' }}>
          {results.map((r, i) => (
            <div key={i} className="flex justify-between items-center text-[10px]">
              <span className="text-white/40 font-mono">{r.batch_id}</span>
              <span className={r.compliant ? 'text-emerald-400' : 'text-red-400'}>
                {r.compliant ? '✓' : '✗'} {r.deforestation_risk || ''}
              </span>
            </div>
          ))}
        </div>
      )}
    </CardShell>
  )
}

function ComplianceCheck({ label, ok }) {
  if (ok === undefined || ok === null) return null
  return (
    <div className="flex justify-between items-center py-0.5">
      <span className="text-[10px] text-white/30">{label}</span>
      <span className={`text-xs ${ok ? 'text-emerald-400' : 'text-red-400'}`}>{ok ? '✓' : '✗'}</span>
    </div>
  )
}


/* ================================================================
   MassBalanceCard — input vs output mass balance
   ================================================================ */

function MassBalanceCard({ data }) {
  return (
    <CardShell
      icon={<ScaleIcon />}
      title="Mass Balance"
      accent={data.valid ? '#10B981' : '#EF4444'}
    >
      <div className="flex items-center gap-2 mb-2">
        <span className={`text-sm font-semibold ${data.valid ? 'text-emerald-400' : 'text-red-400'}`}>
          {data.valid ? '✓ Balanced' : '✗ Imbalanced'}
        </span>
      </div>
      <Field label="Total Input" value={data.total_input_kg ? `${data.total_input_kg} kg` : null} />
      <Field label="Total Output" value={data.total_output_kg ? `${data.total_output_kg} kg` : null} />
      <Field label="Difference" value={data.difference_kg ? `${data.difference_kg} kg` : null} />
    </CardShell>
  )
}


/* ================================================================
   ContainerDppCard — aggregated container DPP
   ================================================================ */

function ContainerDppCard({ data }) {
  return (
    <CardShell icon={<DppIcon />} title="Container DPP" accent="#06B6D4">
      <Field label="Container" value={data.container_id} mono />
      <Field label="Farmers" value={data.num_farmers} />
      <Field label="Contributors" value={data.contributors_count} />
      <Field label="Total Quantity" value={data.total_quantity ? `${data.total_quantity} kg` : null} />
    </CardShell>
  )
}


/* ================================================================
   LineageCard — supply-chain lineage trace
   ================================================================ */

function LineageCard({ data }) {
  return (
    <CardShell icon={<LineageIcon />} title="Supply Chain Lineage" accent="#A78BFA">
      <Field label="Product" value={data.product_id} mono />
      <Field label="Contributors" value={data.contributors_count} />
      <Field label="Total Quantity" value={data.total_quantity ? `${data.total_quantity} kg` : null} />
    </CardShell>
  )
}


/* ================================================================
   ValidateDppCard — DPP validation result
   ================================================================ */

function ValidateDppCard({ data }) {
  const hasErrors = data.errors?.length > 0

  return (
    <CardShell
      icon={<ShieldIcon />}
      title="DPP Validation"
      accent={data.valid ? '#10B981' : '#EF4444'}
    >
      <Field label="Batch" value={data.batch_id} mono />
      <div className="flex items-center gap-2 mt-1">
        <span className={`text-sm font-semibold ${data.valid ? 'text-emerald-400' : 'text-red-400'}`}>
          {data.valid ? '✓ Valid' : '✗ Invalid'}
        </span>
      </div>
      {hasErrors && (
        <div className="mt-2 space-y-0.5">
          {data.errors.map((e, i) => (
            <div key={i} className="text-[10px] text-red-400/70">• {e}</div>
          ))}
        </div>
      )}
    </CardShell>
  )
}


/* ================================================================
   PendingVerificationsCard — batches awaiting verification
   ================================================================ */

function PendingVerificationsCard({ data }) {
  const batches = data.batches || []
  const [expanded, setExpanded] = useState(false)
  const visible = expanded ? batches : batches.slice(0, 4)

  return (
    <CardShell icon={<ClipboardIcon />} title={`Pending (${data.count || batches.length})`} accent="#F59E0B">
      <div className="space-y-2">
        {visible.map((b, i) => (
          <div key={i} className="px-2 py-1.5 rounded-lg" style={{ background: 'rgba(255,255,255,0.03)' }}>
            <span className="text-xs text-white/70 font-mono">{b.batch_id}</span>
            <div className="text-[10px] text-white/30">
              {b.origin} {b.variety ? `• ${b.variety}` : ''} • {b.quantity_kg} kg
              {b.farmer ? ` • ${b.farmer}` : ''}
            </div>
          </div>
        ))}
      </div>
      {batches.length > 4 && (
        <button onClick={() => setExpanded(v => !v)}
                className="w-full mt-2 text-[10px] text-amber-400/60 hover:text-amber-400 transition-colors">
          {expanded ? 'Show less' : `Show all ${batches.length}`}
        </button>
      )}
    </CardShell>
  )
}


/* ================================================================
   VerifyBatchCard — batch verification result
   ================================================================ */

function VerifyBatchCard({ data }) {
  return (
    <CardShell icon={<CheckIcon />} title="Batch Verified" accent="#10B981">
      <Field label="Batch" value={data.batch_id} mono />
      <Field label="Verified Qty" value={data.verified_quantity_kg ? `${data.verified_quantity_kg} kg` : null} />
      <Field label="Quality Notes" value={data.quality_notes} />
      <Field label="Verified By" value={data.verified_by} />
      <Field label="Credential" value={data.credential_issued ? '✓ Issued' : '—'} />
    </CardShell>
  )
}


/* ================================================================
   BlockchainAnchorCard — on-chain anchor status
   ================================================================ */

function BlockchainAnchorCard({ data }) {
  return (
    <CardShell
      icon={<ChainIcon />}
      title="Blockchain Anchor"
      accent={data.anchored ? '#10B981' : '#6B7280'}
    >
      <Field label="Batch" value={data.batch_id} mono />
      <div className="flex items-center gap-2 mt-0.5 mb-1">
        <span className={`text-xs font-semibold ${data.anchored ? 'text-emerald-400' : 'text-white/40'}`}>
          {data.anchored ? '✓ Anchored' : '○ Pending'}
        </span>
      </div>
      <Field label="Event" value={data.event_type} />
      <Field label="Hash" value={data.event_hash ? `${data.event_hash.slice(0, 12)}…` : null} mono />
      <Field label="IPFS" value={data.ipfs_cid ? `${data.ipfs_cid.slice(0, 14)}…` : null} mono />
      <Field label="Submitter" value={data.submitter ? `${data.submitter.slice(0, 8)}…` : null} mono />
      <Field label="Time" value={data.timestamp} />
    </CardShell>
  )
}


/* ================================================================
   TokenInfoCard — ERC-1155 token metadata
   ================================================================ */

function TokenInfoCard({ data }) {
  return (
    <CardShell icon={<TokenIcon />} title="Token Info" accent="#F59E0B">
      <Field label="Token ID" value={data.token_id != null ? `#${data.token_id}` : null} mono />
      <Field label="Found" value={data.found ? '✓ Yes' : '✗ No'} />
      <Field label="Batch" value={data.batch_id} mono />
      <Field label="Quantity" value={data.quantity_kg ? `${data.quantity_kg} kg` : null} />
      <Field label="IPFS" value={data.ipfs_cid ? `${data.ipfs_cid.slice(0, 14)}…` : null} mono />
      <Field label="Aggregated" value={data.is_aggregated ? 'Yes' : 'No'} />
      {data.child_token_ids?.length > 0 && (
        <Field label="Children" value={data.child_token_ids.join(', ')} mono />
      )}
    </CardShell>
  )
}


/* ================================================================
   HashVerifyCard — batch hash integrity check
   ================================================================ */

function HashVerifyCard({ data }) {
  return (
    <CardShell
      icon={<ChainIcon />}
      title="Hash Verification"
      accent={data.verified ? '#10B981' : data.anchored === false ? '#6B7280' : '#EF4444'}
    >
      <Field label="Batch" value={data.batch_id} mono />
      <div className="flex items-center gap-2 mt-0.5 mb-1">
        <span className={`text-xs font-semibold ${
          data.verified ? 'text-emerald-400' :
          data.anchored === false ? 'text-white/40' : 'text-red-400'
        }`}>
          {data.verified ? '✓ Integrity verified' :
           data.anchored === false ? '○ Not anchored' : '✗ Hash mismatch'}
        </span>
      </div>
      {data.hash && <Field label="Hash" value={`${data.hash.slice(0, 14)}…`} mono />}
      {data.current_hash && <Field label="Current" value={`${data.current_hash.slice(0, 14)}…`} mono />}
      {data.on_chain_hash && <Field label="On-chain" value={`${data.on_chain_hash.slice(0, 14)}…`} mono />}
    </CardShell>
  )
}


/* ================================================================
   DonAttestCard — DON deforestation attestation
   ================================================================ */

function DonAttestCard({ data, verb = 'Result' }) {
  const risk = data.risk_level || data.risk_label || data.attestation?.risk_level
  const riskColor =
    risk === 'low' ? 'text-emerald-400' :
    risk === 'medium' ? 'text-amber-400' : 'text-red-400'

  return (
    <CardShell icon={<SatelliteIcon />} title={`DON Attestation — ${verb}`} accent="#06B6D4">
      <Field label="Farm" value={data.farm_id} mono />
      <Field label="Status" value={data.status} />
      {risk && (
        <div className="flex justify-between items-center py-0.5">
          <span className="text-[10px] text-white/30 uppercase tracking-wider">Risk Level</span>
          <span className={`text-xs font-semibold ${riskColor}`}>{risk}</span>
        </div>
      )}
      <Field label="EUDR" value={data.eudr_compliant != null ? (data.eudr_compliant ? '✓ Compliant' : '✗ Non-compliant') : null} />
      <Field label="Tree Loss" value={data.tree_loss_hectares != null ? `${data.tree_loss_hectares} ha` : null} />
      <Field label="GPS" value={data.latitude && data.longitude ? `${data.latitude}, ${data.longitude}` : null} mono />
      {data.tx_hash && <Field label="Tx" value={`${data.tx_hash.slice(0, 12)}…`} mono />}
      <Field label="Mode" value={data.mode} />
    </CardShell>
  )
}


/* ================================================================
   ProvenanceMetricsCard — DON aggregate metrics
   ================================================================ */

function ProvenanceMetricsCard({ data }) {
  return (
    <CardShell icon={<ChartIcon />} title="Provenance Metrics" accent="#06B6D4">
      <Field label="Farmers" value={data.total_farmers} />
      <Field label="Batches" value={data.total_batches} />
      <Field label="Verified" value={data.verified_batches} />
      <Field label="Total Quantity" value={data.total_quantity_kg ? `${Number(data.total_quantity_kg).toLocaleString()} kg` : null} />
      <Field label="EUDR Compliant" value={data.eudr_compliant_percent != null ? `${data.eudr_compliant_percent}%` : null} />
      <Field label="Anchored" value={data.batches_anchored} />
      <Field label="Updated" value={data.last_updated} />
    </CardShell>
  )
}


/* ================================================================
   PaymentCard — settlement / payment status (shared by 4 tools)
   ================================================================ */

function PaymentCard({ data }) {
  const id = data.acceptance_number || (data.commitment_id ? `Commitment #${data.commitment_id}` : null)
  const status = data.payment_status || data.status
  const statusColor =
    status === 'PAID' || status === 'COMPLETED' ? 'text-emerald-400' :
    status === 'PENDING' || status === 'AWAITING_PAYMENT' ? 'text-amber-400' : 'text-white/60'

  return (
    <CardShell icon={<PaymentIcon />} title="Payment" accent="#10B981">
      {id && <Field label="Reference" value={id} mono />}
      <Field label="Cooperative" value={data.cooperative} />
      <Field label="Quantity" value={data.quantity_kg ? `${data.quantity_kg} kg` : null} />
      <Field label="Amount" value={data.total_amount || data.amount ? `$${Number(data.total_amount || data.amount).toLocaleString()}` : null} />
      {status && (
        <div className="flex justify-between items-center py-0.5">
          <span className="text-[10px] text-white/30 uppercase tracking-wider">Status</span>
          <span className={`text-xs font-semibold ${statusColor}`}>{status}</span>
        </div>
      )}
      <ComplianceCheck label="Buyer Confirmed" ok={data.buyer_confirmed} />
      <ComplianceCheck label="Coop Confirmed" ok={data.coop_confirmed} />
      <ComplianceCheck label="Receipt Confirmed" ok={data.receipt_confirmed} />
      {data.delivery_status && <Field label="Delivery" value={data.delivery_status} />}
      {data.settlement_tx && <Field label="Settlement Tx" value={`${data.settlement_tx.slice(0, 12)}…`} mono />}
      {data.coop_payout_tx && <Field label="Payout Tx" value={`${data.coop_payout_tx.slice(0, 12)}…`} mono />}
      {data.tx_hash && <Field label="Tx" value={`${data.tx_hash.slice(0, 12)}…`} mono />}
    </CardShell>
  )
}


/* ================================================================
   FinancingPoolCard — DeFi pool stats
   ================================================================ */

function FinancingPoolCard({ data }) {
  return (
    <CardShell icon={<VaultIcon />} title="Financing Pool" accent="#8B5CF6">
      <Field label="Total Assets" value={data.total_assets_usdc ? `$${Number(data.total_assets_usdc).toLocaleString()}` : null} />
      <Field label="Advanced" value={data.total_advanced_usdc ? `$${Number(data.total_advanced_usdc).toLocaleString()}` : null} />
      <Field label="Available" value={data.available_for_advance_usdc ? `$${Number(data.available_for_advance_usdc).toLocaleString()}` : null} />
      {data.utilisation_pct != null && (
        <div className="mt-1.5">
          <ProgressBar pct={data.utilisation_pct} label="Utilisation" />
        </div>
      )}
      <Field label="Share Price" value={data.share_price_usdc ? `$${data.share_price_usdc}` : null} />
      <Field label="Cumulative Fees" value={data.cumulative_fees_usdc ? `$${Number(data.cumulative_fees_usdc).toLocaleString()}` : null} />
    </CardShell>
  )
}


/* ================================================================
   FinancingAdvanceCard — USDC advance result
   ================================================================ */

function FinancingAdvanceCard({ data }) {
  return (
    <CardShell icon={<VaultIcon />} title="Advance Issued" accent="#10B981">
      <Field label="Acceptance #" value={data.acceptance_number} mono />
      <Field label="Token ID" value={data.token_id != null ? `#${data.token_id}` : null} mono />
      <Field label="Agreed Price" value={data.agreed_price_usdc ? `$${Number(data.agreed_price_usdc).toLocaleString()}` : null} />
      <Field label="Advance" value={data.advance_estimate_usdc ? `$${Number(data.advance_estimate_usdc).toLocaleString()}` : null} />
      {data.tx_hash && <Field label="Tx" value={`${data.tx_hash.slice(0, 12)}…`} mono />}
    </CardShell>
  )
}


/* ================================================================
   TradeFinancingCard — on-chain trade/escrow details
   ================================================================ */

function TradeFinancingCard({ data }) {
  return (
    <CardShell icon={<VaultIcon />} title="Trade Financing" accent="#8B5CF6">
      <Field label="Trade ID" value={data.trade_id != null ? `#${data.trade_id}` : null} mono />
      <Field label="Token ID" value={data.token_id != null ? `#${data.token_id}` : null} mono />
      <Field label="Status" value={data.status} />
      <Field label="Agreed Price" value={data.agreed_price_usdc ? `$${Number(data.agreed_price_usdc).toLocaleString()}` : null} />
      <Field label="Advance" value={data.advance_amount_usdc ? `$${Number(data.advance_amount_usdc).toLocaleString()}` : null} />
      <Field label="Fee" value={data.fee_amount_usdc ? `$${data.fee_amount_usdc} (${data.fee_bps}bps)` : null} />
      <Field label="Seller" value={data.seller ? `${data.seller.slice(0, 8)}…` : null} mono />
      <Field label="Buyer" value={data.buyer ? `${data.buyer.slice(0, 8)}…` : null} mono />
      <Field label="Deadline" value={data.deadline} />
      <Field label="Created" value={data.created_at} />
    </CardShell>
  )
}


/* ================================================================
   DisputePaymentCard — payment dispute raised
   ================================================================ */

function DisputePaymentCard({ data }) {
  return (
    <CardShell icon={<AlertIcon />} title="Payment Dispute" accent="#F59E0B">
      <Field label="Acceptance #" value={data.acceptance_number} mono />
      {data.dispute_reason && (
        <div className="mt-1">
          <span className="text-[10px] text-white/30 uppercase tracking-wider">Reason</span>
          <p className="text-xs text-amber-300/80 mt-0.5 leading-relaxed">{data.dispute_reason}</p>
        </div>
      )}
      <div className="mt-2 pt-2 space-y-0.5" style={{ borderTop: '1px solid rgba(255,255,255,0.04)' }}>
        <span className="text-[10px] text-white/20 uppercase tracking-widest">Evidence on Record</span>
        <ComplianceCheck label="Receipt photo" ok={data.has_receipt} />
        <ComplianceCheck label="Blockchain settlement" ok={data.has_settlement} />
        <ComplianceCheck label="Buyer confirmed" ok={data.buyer_confirmed} />
      </div>
      <div className="mt-2 px-2 py-1.5 rounded-lg" style={{ background: 'rgba(245,158,11,0.06)' }}>
        <span className="text-[10px] text-amber-400/70">An administrator will review and contact both parties.</span>
      </div>
    </CardShell>
  )
}


/* ================================================================
   ShipmentConfirmCard — cooperative confirms coffee shipped
   ================================================================ */

function ShipmentConfirmCard({ data }) {
  return (
    <CardShell icon={<TruckIcon />} title="Shipment Confirmed" accent="#6366F1">
      <Field label="Acceptance #" value={data.acceptance_number} mono />
      <Field label="Quantity" value={data.quantity_kg ? `${Number(data.quantity_kg).toLocaleString()} kg` : null} />
      <Field label="Destination" value={data.delivery_location} />
      <div className="flex justify-between items-center py-0.5 mt-0.5">
        <span className="text-[10px] text-white/30 uppercase tracking-wider">Delivery Status</span>
        <span className="text-xs font-semibold text-indigo-400">SHIPPED →</span>
      </div>
      <div className="mt-2 px-2 py-1.5 rounded-lg" style={{ background: 'rgba(99,102,241,0.06)' }}>
        <span className="text-[10px] text-indigo-300/70">Buyer has been notified. Awaiting delivery confirmation.</span>
      </div>
    </CardShell>
  )
}


/* ================================================================
   DeliveryConfirmCard — buyer confirms coffee delivered
   ================================================================ */

function DeliveryConfirmCard({ data }) {
  return (
    <CardShell icon={<PackageCheckIcon />} title="Delivery Confirmed" accent="#10B981">
      <Field label="Acceptance #" value={data.acceptance_number} mono />
      <Field label="Delivered At" value={data.delivered_at ? data.delivered_at.slice(0, 19).replace('T', ' ') : null} />
      <div className="flex justify-between items-center py-0.5 mt-0.5">
        <span className="text-[10px] text-white/30 uppercase tracking-wider">Delivery Status</span>
        <span className="text-xs font-semibold text-emerald-400">✓ DELIVERED</span>
      </div>
      <div className="mt-2 px-2 py-1.5 rounded-lg" style={{ background: 'rgba(16,185,129,0.06)' }}>
        <span className="text-[10px] text-emerald-300/70">Cooperative notified. Transaction complete! 🎉</span>
      </div>
    </CardShell>
  )
}


/* ================================================================
   Micro-icons (new)
   ================================================================ */

function AlertIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M7 1L1 12h12L7 1z" />
      <path d="M7 5.5v3" />
      <circle cx="7" cy="10" r="0.5" fill="currentColor" />
    </svg>
  )
}

function TruckIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M1 3h8v6H1z" />
      <path d="M9 5h2l2 2v2H9" />
      <circle cx="3" cy="10" r="1" />
      <circle cx="11" cy="10" r="1" />
    </svg>
  )
}

function PackageCheckIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M2 4.5L7 2l5 2.5v5L7 12l-5-2.5z" />
      <path d="M7 7v5M2 4.5L7 7l5-2.5" />
      <path d="M4.5 7l1.5 1.5 3-3" />
    </svg>
  )
}


/* ================================================================
   Shared sub-components
   ================================================================ */

function TxFooter({ data }) {
  if (!data.event_hash && !data.ipfs_cid && !data.blockchain_tx) return null
  return (
    <div className="mt-2 pt-2 space-y-0" style={{ borderTop: '1px solid rgba(255,255,255,0.04)' }}>
      {data.event_hash && <Field label="Event Hash" value={`${data.event_hash.slice(0, 12)}…`} mono />}
      {data.ipfs_cid && <Field label="IPFS" value={`${data.ipfs_cid.slice(0, 14)}…`} mono />}
      {data.blockchain_tx && <Field label="Tx" value={`${data.blockchain_tx.slice(0, 12)}…`} mono />}
    </div>
  )
}

function ProgressBar({ pct, label }) {
  const clamped = Math.min(100, Math.max(0, pct || 0))
  return (
    <div>
      {label && <span className="text-[10px] text-white/30">{label}</span>}
      <div className="w-full h-1.5 rounded-full bg-white/5 mt-0.5 overflow-hidden">
        <div
          className="h-full rounded-full transition-all duration-500"
          style={{
            width: `${clamped}%`,
            background: clamped >= 100 ? '#10B981' : clamped >= 70 ? '#F59E0B' : '#3B82F6',
          }}
        />
      </div>
      <span className="text-[9px] text-white/25 mt-0.5">{clamped.toFixed(0)}%</span>
    </div>
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
   MilestoneCard — ingest_milestone result
   ================================================================ */

const MILESTONE_LABELS = {
  PICKUP:                   'Pickup',
  PORT_ARRIVAL_ORIGIN:      'Port Arrival (Origin)',
  VESSEL_DEPARTURE:         'Vessel Departure',
  TRANSSHIPMENT:            'Transshipment',
  PORT_ARRIVAL_DESTINATION: 'Port Arrival (Destination)',
  CUSTOMS_CLEARED:          'Customs Cleared',
  DELIVERED:                'Delivered',
}

const MILESTONE_ICONS = {
  PICKUP:                   '🚛',
  PORT_ARRIVAL_ORIGIN:      '⚓',
  VESSEL_DEPARTURE:         '🚢',
  TRANSSHIPMENT:            '🔄',
  PORT_ARRIVAL_DESTINATION: '🏗️',
  CUSTOMS_CLEARED:          '✅',
  DELIVERED:                '📦',
}

function MilestoneCard({ data }) {
  const type    = data.milestone_type || ''
  const label   = MILESTONE_LABELS[type] || type.replace(/_/g, ' ')
  const emoji   = MILESTONE_ICONS[type] || '📍'
  const success = data.success !== false

  return (
    <CardShell icon={<ShipIcon />} title={`Milestone: ${label}`} accent="#06B6D4">
      <div className="flex items-center gap-2 mb-2">
        <span className="text-xl">{emoji}</span>
        <span className={`text-sm font-semibold ${success ? 'text-cyan-300' : 'text-red-400'}`}>
          {success ? label : 'Failed'}
        </span>
      </div>
      <Field label="Container" value={data.container_sscc} mono />
      <Field label="Location"  value={data.location} />
      <Field label="Carrier"   value={data.carrier} />
      <Field label="Vessel IMO" value={data.vessel_imo} mono />
      <Field label="Voyage"    value={data.voyage_number} />
      <Field label="Tracking"  value={data.tracking_reference} mono />
      {data.timestamp && (
        <Field label="Time" value={new Date(data.timestamp).toLocaleString()} />
      )}
      {data.epcis_event_hash && (
        <div className="mt-2 pt-2" style={{ borderTop: '1px solid rgba(255,255,255,0.04)' }}>
          <Field label="Event Hash" value={`${data.epcis_event_hash.slice(0, 12)}…`} mono />
          {data.blockchain_tx_hash && (
            <Field label="Blockchain TX" value={`${data.blockchain_tx_hash.slice(0, 14)}…`} mono />
          )}
          {data.ipfs_cid && (
            <Field label="IPFS CID" value={`${data.ipfs_cid.slice(0, 14)}…`} mono />
          )}
        </div>
      )}
    </CardShell>
  )
}


/* ================================================================
   WebhookRegisteredCard — register_webhook_subscription (Agent #12)
   ================================================================ */

function WebhookRegisteredCard({ data }) {
  return (
    <CardShell icon={<WebhookIcon />} title="Webhook Registered" accent="#10B981">
      <Field label="ID"  value={data.id} mono />
      <Field label="URL" value={data.url} />
      {data.events?.length > 0 && (
        <div className="mt-1">
          <span className="text-[10px] text-white/30 uppercase tracking-wider">Events</span>
          <div className="flex flex-wrap gap-1 mt-0.5">
            {data.events.map((e, i) => (
              <span key={i}
                className="inline-block px-1.5 py-0.5 rounded text-[9px] font-mono bg-emerald-500/15 text-emerald-300/80">
                {e}
              </span>
            ))}
          </div>
        </div>
      )}
      {data.description && <Field label="Label" value={data.description} />}
      <p className="mt-2 text-[10px] text-white/30">Save the ID to unregister later.</p>
    </CardShell>
  )
}


/* ================================================================
   WebhookListCard — list_webhook_subscriptions
   ================================================================ */

function WebhookListCard({ data }) {
  const hooks    = data.webhooks || []
  const [expanded, setExpanded] = useState(false)
  const visible  = expanded ? hooks : hooks.slice(0, 4)

  if (!hooks.length) {
    return (
      <CardShell icon={<WebhookIcon />} title="Webhook Subscriptions" accent="#6366F1">
        <p className="text-xs text-white/40 italic">No subscriptions registered.</p>
      </CardShell>
    )
  }

  return (
    <CardShell icon={<WebhookIcon />} title={`Webhooks (${data.count ?? hooks.length})`} accent="#6366F1">
      <div className="space-y-2">
        {visible.map((wh, i) => (
          <div key={i} className="px-2 py-1.5 rounded-lg" style={{ background: 'rgba(255,255,255,0.03)' }}>
            <div className="flex justify-between items-center">
              <span className="text-[10px] font-mono text-white/50">{wh.id}</span>
              <span className={`text-[9px] px-1.5 py-0.5 rounded-full ${
                wh.active ? 'bg-emerald-500/20 text-emerald-300' : 'bg-gray-500/20 text-gray-400'
              }`}>{wh.active ? 'active' : 'inactive'}</span>
            </div>
            <p className="text-[10px] text-white/60 truncate mt-0.5">{wh.url}</p>
            <div className="flex flex-wrap gap-1 mt-0.5">
              {(wh.events || []).map((e, j) => (
                <span key={j} className="text-[8px] px-1 py-0.5 rounded bg-indigo-500/10 text-indigo-300/70 font-mono">{e}</span>
              ))}
            </div>
            <div className="flex gap-3 mt-0.5 text-[9px] text-white/25">
              <span>✅ {wh.delivery_count ?? 0}</span>
              <span>❌ {wh.failure_count ?? 0}</span>
            </div>
          </div>
        ))}
      </div>
      {hooks.length > 4 && (
        <button onClick={() => setExpanded(v => !v)}
                className="w-full mt-2 text-[10px] text-indigo-400/60 hover:text-indigo-400 transition-colors">
          {expanded ? 'Show less' : `Show all ${hooks.length}`}
        </button>
      )}
    </CardShell>
  )
}


/* ================================================================
   WebhookRemovedCard — unregister_webhook_subscription
   ================================================================ */

function WebhookRemovedCard({ data }) {
  const success = data.success !== false && data.found !== false
  return (
    <CardShell icon={<WebhookIcon />} title="Webhook Removed" accent={success ? '#EF4444' : '#6B7280'}>
      {success ? (
        <>
          <div className="flex items-center gap-2 mb-1">
            <span className="text-red-400 text-sm">🗑️</span>
            <span className="text-xs text-white/60">Subscription deleted</span>
          </div>
          <Field label="ID" value={data.id} mono />
          <p className="mt-1 text-[10px] text-white/25">This endpoint will no longer receive events.</p>
        </>
      ) : (
        <p className="text-xs text-white/40 italic">Webhook not found.</p>
      )}
    </CardShell>
  )
}


/* ================================================================
   ShipmentStatusCard — get_shipment_status
   ================================================================ */

const DELIVERY_STATUS_STYLES = {
  PENDING:    { color: '#F59E0B', emoji: '⏳' },
  SHIPPED:    { color: '#06B6D4', emoji: '🚢' },
  IN_TRANSIT: { color: '#06B6D4', emoji: '🚢' },
  DELIVERED:  { color: '#10B981', emoji: '✅' },
  UNKNOWN:    { color: '#6B7280', emoji: '❓' },
}

function ShipmentStatusCard({ data }) {
  const ds       = (data.delivery_status || 'UNKNOWN').toUpperCase()
  const style    = DELIVERY_STATUS_STYLES[ds] || DELIVERY_STATUS_STYLES.UNKNOWN
  const events   = data.events   || []
  const milestones = data.milestones || []
  const [showEvents, setShowEvents] = useState(false)

  return (
    <CardShell icon={<ShipIcon />} title="Shipment Status" accent={style.color}>
      {/* Status hero */}
      <div className="flex items-center gap-2 mb-3 px-2 py-1.5 rounded-lg"
           style={{ background: `${style.color}15` }}>
        <span className="text-xl">{style.emoji}</span>
        <div>
          <p className="text-xs font-bold" style={{ color: style.color }}>{ds}</p>
          <p className="text-[10px] text-white/40 font-mono">{data.container_sscc}</p>
        </div>
      </div>

      <Field label="Variety"  value={data.variety} />
      <Field label="Quantity" value={data.total_quantity_kg ? `${Number(data.total_quantity_kg).toLocaleString()} kg` : null} />

      {/* Milestones */}
      {milestones.length > 0 && (
        <div className="mt-2 pt-2" style={{ borderTop: '1px solid rgba(255,255,255,0.04)' }}>
          <span className="text-[10px] text-white/20 uppercase tracking-widest">
            Milestones ({milestones.length})
          </span>
          <div className="mt-1 space-y-1">
            {milestones.map((m, i) => {
              const mEmoji = MILESTONE_ICONS[m.milestone_type] || '📍'
              const mLabel = MILESTONE_LABELS[m.milestone_type] || (m.milestone_type || '').replace(/_/g, ' ')
              const t = m.event_time ? m.event_time.slice(0, 16).replace('T', ' ') : '—'
              return (
                <div key={i} className="flex items-start gap-1.5">
                  <span className="text-xs mt-0.5">{mEmoji}</span>
                  <div>
                    <span className="text-[10px] text-white/60">{mLabel}</span>
                    <span className="text-[9px] text-white/25 ml-1">{t}</span>
                    {m.carrier && <span className="text-[9px] text-white/25 ml-1">· {m.carrier}</span>}
                    {m.blockchain_tx_hash && <span className="text-[9px] text-cyan-400/40 ml-1">⛓</span>}
                  </div>
                </div>
              )
            })}
          </div>
        </div>
      )}

      {/* Supply chain events (collapsible) */}
      {events.length > 0 && (
        <div className="mt-2 pt-2" style={{ borderTop: '1px solid rgba(255,255,255,0.04)' }}>
          <button
            onClick={() => setShowEvents(v => !v)}
            className="text-[10px] text-white/30 hover:text-white/50 transition-colors"
          >
            {showEvents ? '▾' : '▸'} Supply chain events ({events.length})
          </button>
          {showEvents && (
            <div className="mt-1 space-y-1">
              {events.map((e, i) => {
                const t = e.event_time ? e.event_time.slice(0, 16).replace('T', ' ') : '—'
                const step = e.biz_step || e.event_type || 'event'
                return (
                  <div key={i} className="flex items-center gap-1.5 text-[10px] text-white/40">
                    <span className="w-1.5 h-1.5 rounded-full bg-white/20 shrink-0" />
                    <span>{step}</span>
                    <span className="text-white/20">{t}</span>
                    {e.blockchain_tx_hash && <span className="text-cyan-400/40">⛓</span>}
                  </div>
                )
              })}
            </div>
          )}
        </div>
      )}

      {milestones.length === 0 && events.length === 0 && (
        <p className="mt-1 text-[10px] text-white/25 italic">No events recorded yet.</p>
      )}
    </CardShell>
  )
}


/* ================================================================
   VerifyDidCard — verify_did result
   ================================================================ */

function VerifyDidCard({ data }) {
  const s       = data.summary || {}
  const creds   = data.credentials || []
  const user    = data.user_info || {}
  const ok      = data.success !== false
  const allValid = creds.length > 0 && creds.every(c => c.verified)

  return (
    <CardShell icon={<IdentityIcon />} title="DID Verification" accent="#8B5CF6">
      {/* DID */}
      {data.did && (
        <div className="mb-2 px-2 py-1.5 rounded-lg font-mono text-[10px] text-white/50 break-all"
             style={{ background: 'rgba(139,92,246,0.08)' }}>
          {data.did}
        </div>
      )}

      {/* Identity summary row */}
      <div className="flex items-center gap-2 mb-2">
        <span className={`text-sm ${allValid ? 'text-violet-300' : 'text-amber-400'}`}>
          {allValid ? '✅' : '⚠️'}
        </span>
        <span className="text-xs text-white/60">
          {s.verified_credentials ?? 0}/{s.total_credentials ?? 0} credentials verified
        </span>
        {user.name && (
          <span className="text-[10px] text-white/30 ml-auto">👤 {user.name}</span>
        )}
      </div>

      {/* Stats row */}
      <div className="flex gap-3 mb-2">
        {s.credit_score != null && (
          <div className="flex flex-col items-center px-2 py-1 rounded-lg flex-1"
               style={{ background: 'rgba(139,92,246,0.08)' }}>
            <span className="text-sm font-bold text-violet-300">{s.credit_score}</span>
            <span className="text-[9px] text-white/25 uppercase tracking-wider">Score</span>
          </div>
        )}
        {s.total_batches != null && (
          <div className="flex flex-col items-center px-2 py-1 rounded-lg flex-1"
               style={{ background: 'rgba(139,92,246,0.08)' }}>
            <span className="text-sm font-bold text-white/60">{s.total_batches}</span>
            <span className="text-[9px] text-white/25 uppercase tracking-wider">Batches</span>
          </div>
        )}
        {s.total_volume_kg != null && (
          <div className="flex flex-col items-center px-2 py-1 rounded-lg flex-1"
               style={{ background: 'rgba(139,92,246,0.08)' }}>
            <span className="text-sm font-bold text-white/60">
              {Number(s.total_volume_kg).toLocaleString()}
            </span>
            <span className="text-[9px] text-white/25 uppercase tracking-wider">kg</span>
          </div>
        )}
        {s.days_active != null && (
          <div className="flex flex-col items-center px-2 py-1 rounded-lg flex-1"
               style={{ background: 'rgba(139,92,246,0.08)' }}>
            <span className="text-sm font-bold text-white/60">{s.days_active}</span>
            <span className="text-[9px] text-white/25 uppercase tracking-wider">Days</span>
          </div>
        )}
      </div>

      {/* Credentials list */}
      {creds.length > 0 && (
        <div className="mt-1 pt-2 space-y-1" style={{ borderTop: '1px solid rgba(255,255,255,0.04)' }}>
          <span className="text-[10px] text-white/20 uppercase tracking-widest">Credentials</span>
          {creds.map((c, i) => {
            const badge = c.verified ? '✅' : '❌'
            const types = Array.isArray(c.type)
              ? c.type.filter(t => t !== 'VerifiableCredential').join(', ')
              : String(c.type || 'Unknown')
            return (
              <div key={i} className="flex items-start gap-1.5 text-[11px] text-white/50">
                <span className="shrink-0">{badge}</span>
                <span>{types || 'Credential'}</span>
                {c.issuance_date && (
                  <span className="text-[9px] text-white/20 ml-auto shrink-0">
                    {c.issuance_date.slice(0, 10)}
                  </span>
                )}
              </div>
            )
          })}
        </div>
      )}
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

function CheckIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="7" cy="7" r="5.5" />
      <path d="M4.5 7l2 2 3-4" />
    </svg>
  )
}

function TransformIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round">
      <path d="M2 4h4l2 3-2 3H2" />
      <path d="M8 4h4" />
      <path d="M10 7h2" />
      <path d="M8 10h4" />
    </svg>
  )
}

function BoxIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M2 4.5L7 2l5 2.5v5L7 12l-5-2.5z" />
      <path d="M7 7v5M2 4.5L7 7l5-2.5" />
    </svg>
  )
}

function SplitIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round">
      <path d="M2 7h4" />
      <path d="M6 7l4-3.5" />
      <path d="M6 7l4 3.5" />
      <path d="M6 7l4 0" />
    </svg>
  )
}

function SearchIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round">
      <circle cx="6" cy="6" r="4" />
      <path d="M9 9l3 3" />
    </svg>
  )
}

function MarketIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M1 5l1-3h10l1 3" />
      <rect x="2" y="5" width="10" height="7" rx="1" />
      <path d="M5 5v3a2 2 0 004 0V5" />
    </svg>
  )
}

function OfferIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round">
      <path d="M7 1v5l3 2" />
      <circle cx="7" cy="7" r="5.5" />
    </svg>
  )
}

function CartIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M1 1h2l1.5 7h7" />
      <circle cx="6" cy="11" r="1" />
      <circle cx="10" cy="11" r="1" />
      <path d="M3.5 3H12l-1 5H4.5" />
    </svg>
  )
}

function PoolIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round">
      <ellipse cx="7" cy="4" rx="5" ry="2" />
      <path d="M2 4v6c0 1.1 2.24 2 5 2s5-.9 5-2V4" />
      <path d="M2 7c0 1.1 2.24 2 5 2s5-.9 5-2" />
    </svg>
  )
}

function ShieldIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M7 1L2 3.5v3c0 3.5 2.5 5.5 5 6.5 2.5-1 5-3 5-6.5v-3L7 1z" />
    </svg>
  )
}

function ScaleIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round">
      <path d="M7 2v10M3 12h8" />
      <path d="M2 5l2.5 4h-5zM12 5l-2.5 4h5z" />
      <path d="M3 5h8" />
    </svg>
  )
}

function ClipboardIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" strokeLinejoin="round">
      <rect x="3" y="2" width="8" height="10" rx="1" />
      <path d="M5 1h4v2H5z" />
      <path d="M5 6h4M5 8.5h2.5" />
    </svg>
  )
}

function ChainIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round">
      <rect x="1" y="3" width="5" height="3.5" rx="1" />
      <rect x="8" y="7.5" width="5" height="3.5" rx="1" />
      <path d="M6 5h2M6 9h2" />
      <path d="M8 5v2a2 2 0 01-2 2" />
    </svg>
  )
}

function TokenIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round">
      <circle cx="7" cy="7" r="5.5" />
      <path d="M5 5.5h4M7 5.5v4" />
      <path d="M5.5 8h3" />
    </svg>
  )
}

function SatelliteIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round">
      <circle cx="3.5" cy="10.5" r="1.5" />
      <path d="M3.5 7.5a3 3 0 013 3" />
      <path d="M3.5 4.5a6 6 0 016 6" />
      <path d="M8 2l4 4M9.5 4.5L8.5 5.5" />
    </svg>
  )
}

function ChartIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round">
      <path d="M2 12V6M5 12V4M8 12V8M11 12V2" />
    </svg>
  )
}

function PaymentIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" strokeLinejoin="round">
      <rect x="1" y="3" width="12" height="8" rx="1.5" />
      <path d="M1 6h12" />
      <path d="M4 9h3" />
    </svg>
  )
}

function VaultIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" strokeLinejoin="round">
      <rect x="1.5" y="2" width="11" height="10" rx="1.5" />
      <circle cx="7" cy="7" r="2.5" />
      <path d="M7 5v4M5.5 6l3 2" />
    </svg>
  )
}

function LineageIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round">
      <circle cx="3" cy="3" r="1.5" />
      <circle cx="11" cy="7" r="1.5" />
      <circle cx="3" cy="11" r="1.5" />
      <path d="M4.5 3.5L9.5 6.5M4.5 10.5L9.5 7.5" />
    </svg>
  )
}

function ShipIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M1 9.5l1.5-5h9L13 9.5" />
      <path d="M4.5 4.5V2.5h5v2" />
      <path d="M1 9.5c1 1.5 3 1.5 4 0s3-.5 4 0 3-1 3-1" />
      <path d="M3 12h8" />
    </svg>
  )
}

function WebhookIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="7" cy="7" r="2" />
      <path d="M7 1v2M7 11v2M1 7h2M11 7h2" />
      <path d="M3 3l1.4 1.4M9.6 9.6L11 11M11 3l-1.4 1.4M4.4 9.6L3 11" />
    </svg>
  )
}

function IdentityIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="7" cy="5" r="2.5" />
      <path d="M2 12c0-2.76 2.24-5 5-5s5 2.24 5 5" />
      <path d="M9.5 2.5l1 1-1 1" strokeWidth="1" />
    </svg>
  )
}
