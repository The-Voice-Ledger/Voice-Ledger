/**
 * Rich response cards rendered inside assistant chat bubbles
 * based on response_type from the agent.
 */

import { LuCircleCheck, LuCircleX, LuCheck, LuX, LuPackage, LuSprout, LuLink, LuUsers, LuShip } from 'react-icons/lu'

// ── RFQ List ──────────────────────────────────────────────────────────
export function RFQListCard({ data }) {
  const rfqs = data?.rfqs || data?.results || (Array.isArray(data) ? data : [])
  if (!rfqs.length) return <p className="text-sm text-stone-500 italic">No open RFQs found.</p>

  return (
    <div className="space-y-2 mt-2">
      {rfqs.map((r, i) => (
        <div key={r.id || i} className="rounded-lg border border-stone-200 bg-stone-50 p-3 text-sm">
          <div className="flex justify-between">
            <span className="font-semibold text-stone-900">
              {r.coffee_type || r.origin || 'Coffee'}
            </span>
            <span className="text-xs text-stone-500">{r.status || 'open'}</span>
          </div>
          <div className="text-stone-600 mt-1">
            {r.quantity_kg && <span>{r.quantity_kg} kg</span>}
            {r.grade && <span className="ml-2">Grade {r.grade}</span>}
            {r.max_price_usd && <span className="ml-2">≤ ${r.max_price_usd}/kg</span>}
          </div>
          {r.delivery_by && (
            <div className="text-xs text-stone-400 mt-1">Deliver by {r.delivery_by}</div>
          )}
        </div>
      ))}
    </div>
  )
}

// ── EUDR Compliance ───────────────────────────────────────────────────
export function EUDRComplianceCard({ data }) {
  const compliant = data?.compliant ?? data?.is_compliant
  const checks = data?.checks || data?.details || {}

  return (
    <div className="mt-2 rounded-lg border p-3 text-sm"
      style={{ borderColor: compliant ? '#258c25' : '#dc2626', background: compliant ? '#f0faf0' : '#fef2f2' }}>
      <div className="flex items-center gap-2 font-semibold" style={{ color: compliant ? '#258c25' : '#dc2626' }}>
        {compliant ? <LuCircleCheck className="w-4 h-4" /> : <LuCircleX className="w-4 h-4" />} {compliant ? 'EUDR Compliant' : 'Not Compliant'}
      </div>
      {Object.keys(checks).length > 0 && (
        <ul className="mt-2 space-y-1 text-stone-700">
          {Object.entries(checks).map(([k, v]) => (
            <li key={k} className="flex gap-2">
              <span>{v ? <LuCheck className="w-3 h-3 inline" /> : <LuX className="w-3 h-3 inline" />}</span>
              <span className="capitalize">{k.replaceAll('_', ' ')}</span>
            </li>
          ))}
        </ul>
      )}
      {data?.deforestation_risk != null && (
        <div className="mt-1 text-xs text-stone-500">
          Deforestation risk: {(data.deforestation_risk * 100).toFixed(1)}%
        </div>
      )}
    </div>
  )
}

// ── Batch List ────────────────────────────────────────────────────────
export function BatchListCard({ data }) {
  const batches = data?.batches || data?.results || (Array.isArray(data) ? data : [])
  if (!batches.length) return <p className="text-sm text-stone-500 italic">No batches found.</p>

  return (
    <div className="space-y-2 mt-2">
      {batches.map((b, i) => (
        <div key={b.batch_id || b.id || i} className="rounded-lg border border-stone-200 bg-white p-3 text-sm">
          <div className="font-semibold text-stone-800 truncate flex items-center gap-1.5">
            <LuPackage className="w-4 h-4 shrink-0" /> {b.batch_id || b.id}
          </div>
          <div className="text-stone-600 mt-1 flex flex-wrap gap-x-3 gap-y-0.5">
            {b.origin && <span>{b.origin}</span>}
            {b.quantity_kg && <span>{b.quantity_kg} kg</span>}
            {b.grade && <span>G{b.grade}</span>}
            {b.status && <span className="text-xs bg-stone-100 rounded px-1.5">{b.status}</span>}
          </div>
        </div>
      ))}
    </div>
  )
}

// ── DPP (Digital Product Passport) ────────────────────────────────────
export function DPPCard({ data }) {
  const dpp = data?.dpp || data
  if (!dpp) return null

  return (
    <div className="mt-2 rounded-lg border border-forest-200 bg-forest-50 p-3 text-sm space-y-1">
      <div className="font-semibold text-forest-700 flex items-center gap-1.5"><LuSprout className="w-4 h-4" /> Digital Product Passport</div>
      {dpp.batch_id && <div><span className="text-stone-500">Batch:</span> {dpp.batch_id}</div>}
      {dpp.origin && <div><span className="text-stone-500">Origin:</span> {dpp.origin}</div>}
      {dpp.variety && <div><span className="text-stone-500">Variety:</span> {dpp.variety}</div>}
      {dpp.processing && <div><span className="text-stone-500">Processing:</span> {dpp.processing}</div>}
      {dpp.certifications?.length > 0 && (
        <div>
          <span className="text-stone-500">Certs:</span>{' '}
          {dpp.certifications.join(', ')}
        </div>
      )}
      {dpp.qr_url && (
        <a href={dpp.qr_url} target="_blank" rel="noreferrer"
          className="inline-block mt-1 text-forest-600 underline text-xs">
          View QR Code →
        </a>
      )}
    </div>
  )
}

// ── Blockchain Status ─────────────────────────────────────────────────
export function BlockchainCard({ data }) {
  const anchored = data?.anchored ?? data?.on_chain ?? data?.verified
  return (
    <div className="mt-2 rounded-lg border border-stone-200 bg-white p-3 text-sm space-y-1">
      <div className="font-semibold text-stone-800 flex items-center gap-1.5">
        <LuLink className="w-4 h-4" /> Blockchain {anchored ? 'Anchored' : 'Not Anchored'}
      </div>
      {data?.tx_hash && (
        <div className="truncate">
          <span className="text-stone-500">TX:</span>{' '}
          <code className="text-xs">{data.tx_hash}</code>
        </div>
      )}
      {data?.token_id && <div><span className="text-stone-500">Token:</span> #{data.token_id}</div>}
      {data?.network && <div className="text-xs text-stone-400">{data.network}</div>}
    </div>
  )
}

// ── Verification List ─────────────────────────────────────────────────
export function VerificationListCard({ data }) {
  const items = data?.verifications || data?.batches || data?.results || (Array.isArray(data) ? data : [])
  if (!items.length) return <p className="text-sm text-stone-500 italic">No pending verifications.</p>

  return (
    <div className="space-y-2 mt-2">
      {items.map((v, i) => (
        <div key={v.batch_id || v.id || i} className="rounded-lg border border-yellow-200 bg-yellow-50 p-3 text-sm">
          <div className="flex justify-between">
            <span className="font-semibold text-yellow-800 flex items-center gap-1.5">
              <LuPackage className="w-4 h-4 shrink-0" /> {v.batch_id || v.id}
            </span>
            <span className="text-xs text-yellow-600">{v.status || 'Pending'}</span>
          </div>
          <div className="text-stone-600 mt-1 flex flex-wrap gap-x-3 gap-y-0.5">
            {v.origin && <span>{v.origin}</span>}
            {v.quantity_kg && <span>{v.quantity_kg} kg</span>}
            {v.variety && <span>{v.variety}</span>}
          </div>
        </div>
      ))}
    </div>
  )
}

// ── Container List ────────────────────────────────────────────────────
export function ContainerCard({ data }) {
  const containers = data?.containers || data?.results || (Array.isArray(data) ? data : [])
  // Single purchase result
  if (data?.acceptance_number) {
    return (
      <div className="mt-2 rounded-lg border border-forest-200 bg-forest-50 p-3 text-sm space-y-1">
        <div className="font-semibold text-forest-700 flex items-center gap-1.5">
          <LuPackage className="w-4 h-4" /> Purchase Confirmed
        </div>
        <div><span className="text-stone-500">Acceptance:</span> {data.acceptance_number}</div>
        <div><span className="text-stone-500">Container:</span> {data.container_sscc}</div>
        <div><span className="text-stone-500">Quantity:</span> {data.quantity_kg} kg</div>
        <div><span className="text-stone-500">Total:</span> ${data.total_amount_usd?.toLocaleString()}</div>
        <div><span className="text-stone-500">Payment:</span> {data.payment_status}</div>
      </div>
    )
  }
  if (!containers.length) return <p className="text-sm text-stone-500 italic">No containers found.</p>
  return (
    <div className="space-y-2 mt-2">
      {containers.map((c, i) => (
        <div key={c.id || i} className="rounded-lg border border-stone-200 bg-stone-50 p-3 text-sm">
          <div className="flex justify-between">
            <span className="font-semibold text-stone-900">
              {c.variety || 'Coffee'} {c.grade ? `(${c.grade})` : ''}
            </span>
            <span className="text-xs text-stone-500">{c.status}</span>
          </div>
          <div className="text-stone-600 mt-1 flex flex-wrap gap-x-3 gap-y-0.5">
            <span>{c.available_quantity_kg} kg avail</span>
            <span>${c.price_per_kg}/kg</span>
            {c.cooperative && <span className="text-xs">{c.cooperative}</span>}
          </div>
          {c.container_sscc && (
            <div className="text-xs text-stone-400 mt-1 truncate">SSCC: {c.container_sscc}</div>
          )}
          {c.delivery_location && (
            <div className="text-xs text-stone-400">Delivery: {c.delivery_location}</div>
          )}
        </div>
      ))}
    </div>
  )
}

// ── Offer List ────────────────────────────────────────────────────────
export function OfferListCard({ data }) {
  const offers = data?.offers || data?.results || (Array.isArray(data) ? data : [])
  if (!offers.length) return <p className="text-sm text-stone-500 italic">No offers found.</p>

  return (
    <div className="space-y-2 mt-2">
      {offers.map((o, i) => (
        <div key={o.id || i} className="rounded-lg border border-stone-200 bg-stone-50 p-3 text-sm">
          <div className="flex justify-between">
            <span className="font-semibold text-stone-900">
              {o.coffee_type || o.origin || 'Coffee'} — {o.quantity_kg ? `${o.quantity_kg} kg` : ''}
            </span>
            <span className={`text-xs ${o.status === 'accepted' ? 'text-green-600' : 'text-stone-500'}`}>{o.status || 'pending'}</span>
          </div>
          <div className="text-stone-600 mt-1">
            {o.price_per_kg && <span>${o.price_per_kg}/kg</span>}
            {o.total_usd && <span className="ml-2">Total: ${o.total_usd}</span>}
          </div>
          {o.delivery_by && (
            <div className="text-xs text-stone-400 mt-1">Deliver by {o.delivery_by}</div>
          )}
        </div>
      ))}
    </div>
  )
}

// ── Pool List ─────────────────────────────────────────────────────────
export function PoolListCard({ data }) {
  const pools = data?.pools || data?.results || (Array.isArray(data) ? data : [])
  if (!pools.length) return <p className="text-sm text-stone-500 italic">No active pools found.</p>

  return (
    <div className="space-y-2 mt-2">
      {pools.map((p, i) => {
        const pct = p.fill_pct ?? (p.filled_kg && p.fill_target_kg
          ? Math.round((p.filled_kg / p.fill_target_kg) * 100) : 0)
        return (
          <div key={p.id || i} className="rounded-lg border border-stone-200 bg-white p-3 text-sm">
            <div className="flex justify-between items-start">
              <div>
                <span className="font-semibold text-stone-900 flex items-center gap-1.5">
                  <LuShip className="w-4 h-4 shrink-0" />
                  {p.cooperative_name || p.cooperative || 'Pool'}
                </span>
                <span className="text-xs text-stone-500 font-mono">{p.container_sscc || ''}</span>
              </div>
              <span className={`text-xs font-medium rounded-full px-2 py-0.5 ${
                p.status === 'FILLING' ? 'bg-blue-100 text-blue-700'
                  : p.status === 'CONFIRMED' ? 'bg-green-100 text-green-700'
                  : 'bg-stone-100 text-stone-600'
              }`}>{p.status}</span>
            </div>
            <div className="text-stone-600 mt-1.5 flex flex-wrap gap-x-3 gap-y-0.5 text-xs">
              {p.variety && <span>{p.variety}</span>}
              {p.grade && <span>G{p.grade}</span>}
              {p.price_per_kg && <span>${p.price_per_kg}/kg</span>}
              {p.destination_region && <span>{p.destination_region}</span>}
            </div>
            {/* Fill bar */}
            <div className="mt-2">
              <div className="flex justify-between text-[10px] text-stone-400 mb-0.5">
                <span>{p.filled_kg?.toLocaleString() || 0} / {p.fill_target_kg?.toLocaleString() || '?'} kg</span>
                <span className="font-semibold text-stone-600">{pct}%</span>
              </div>
              <div className="w-full bg-stone-100 rounded-full h-1.5 overflow-hidden">
                <div
                  className={`h-full rounded-full ${pct >= 80 ? 'bg-green-500' : pct >= 50 ? 'bg-yellow-500' : 'bg-blue-500'}`}
                  style={{ width: `${Math.min(pct, 100)}%` }}
                />
              </div>
            </div>
            <div className="flex items-center gap-3 text-[10px] text-stone-400 mt-1.5">
              <span className="flex items-center gap-0.5"><LuUsers className="w-3 h-3" /> {p.buyer_count ?? 0} buyers</span>
              {p.remaining_kg != null && <span>{p.remaining_kg.toLocaleString()} kg remaining</span>}
            </div>
          </div>
        )
      })}
    </div>
  )
}

// ── Pool Commitment Confirmation ──────────────────────────────────────
export function CommitConfirmCard({ data }) {
  return (
    <div className="mt-2 rounded-lg border border-green-200 bg-green-50 p-3 text-sm space-y-1">
      <div className="font-semibold text-green-700 flex items-center gap-1.5">
        <LuCircleCheck className="w-4 h-4" /> Commitment Confirmed
      </div>
      {data?.commitment_id && <div><span className="text-stone-500">ID:</span> #{data.commitment_id}</div>}
      {data?.quantity_kg && <div><span className="text-stone-500">Quantity:</span> {data.quantity_kg} kg</div>}
      {data?.estimated_total_usd && (
        <div><span className="text-stone-500">Total:</span> ${Number(data.estimated_total_usd).toLocaleString()}</div>
      )}
      {data?.pool_fill_pct != null && (
        <div><span className="text-stone-500">Pool fill:</span> {data.pool_fill_pct}%</div>
      )}
      {data?.status && <div><span className="text-stone-500">Status:</span> {data.status}</div>}
    </div>
  )
}

// ── Commitment List ───────────────────────────────────────────────────
export function CommitmentListCard({ data }) {
  const items = data?.commitments || data?.results || (Array.isArray(data) ? data : [])
  if (!items.length) return <p className="text-sm text-stone-500 italic">No commitments found.</p>

  return (
    <div className="space-y-2 mt-2">
      {items.map((c, i) => (
        <div key={c.id || i} className="rounded-lg border border-stone-200 bg-white p-3 text-sm">
          <div className="flex justify-between">
            <span className="font-semibold text-stone-900">
              {c.cooperative_name || c.cooperative || 'Pool'} — {c.quantity_kg} kg
            </span>
            <span className={`text-xs font-medium ${
              c.status === 'CONFIRMED' ? 'text-green-600' : 'text-stone-500'
            }`}>{c.status}</span>
          </div>
          <div className="text-xs text-stone-500 mt-1 flex flex-wrap gap-x-3">
            {c.variety && <span>{c.variety}</span>}
            {c.estimated_total_usd && <span>Total: ${Number(c.estimated_total_usd).toLocaleString()}</span>}
            {c.delivery_country && <span>To: {c.delivery_country}</span>}
          </div>
        </div>
      ))}
    </div>
  )
}

// ── Payment Confirmation Card ─────────────────────────────────────────
export function PaymentConfirmCard({ data }) {
  return (
    <div className="rounded-lg bg-green-50 border border-green-200 p-4 text-sm space-y-1">
      <div className="flex items-center gap-2 font-semibold text-green-700">
        <LuCircleCheck className="w-4 h-4" /> Payment Confirmed
      </div>
      {data?.commitment_id && <div><span className="text-stone-500">Commitment:</span> #{data.commitment_id}</div>}
      {data?.acceptance_number && <div><span className="text-stone-500">Acceptance:</span> {data.acceptance_number}</div>}
      {data?.amount != null && <div><span className="text-stone-500">Amount:</span> ${Number(data.amount).toLocaleString()}</div>}
      {data?.status && <div><span className="text-stone-500">Status:</span> {data.status || data.payment_status}</div>}
      {data?.settlement_tx && (
        <div className="mt-2 text-xs text-stone-600">
          <LuLink className="inline w-3 h-3 mr-1" />
          <span className="font-mono">{data.settlement_tx.slice(0, 20)}…</span>
        </div>
      )}
    </div>
  )
}

// ── Payment Status Card ───────────────────────────────────────────────
export function PaymentStatusCard({ data }) {
  const ok = v => v ? '✅' : '⏳'
  return (
    <div className="rounded-lg border border-stone-200 bg-white p-4 text-sm space-y-1">
      <div className="font-semibold text-stone-800">
        {data?.commitment_id ? `Commitment #${data.commitment_id}` : data?.acceptance_number || 'Payment'}
      </div>
      {data?.total_amount != null && (
        <div><span className="text-stone-500">Amount:</span> ${Number(data.total_amount).toLocaleString()}</div>
      )}
      <div><span className="text-stone-500">Status:</span> {data?.status || data?.payment_status}</div>
      <div><span className="text-stone-500">Buyer confirmed:</span> {ok(data?.buyer_confirmed)}</div>
      <div><span className="text-stone-500">Coop confirmed:</span> {ok(data?.coop_confirmed)}</div>
      {data?.settlement_tx && (
        <div className="text-xs text-stone-600 mt-1">
          <LuLink className="inline w-3 h-3 mr-1" />
          Buyer TX: <span className="font-mono">{data.settlement_tx.slice(0, 20)}…</span>
        </div>
      )}
      {data?.coop_payout_tx && (
        <div className="text-xs text-stone-600">
          <LuLink className="inline w-3 h-3 mr-1" />
          Coop payout TX: <span className="font-mono">{data.coop_payout_tx.slice(0, 20)}…</span>
        </div>
      )}
      {data?.cooperative && (
        <div className="text-xs text-stone-400 mt-1">Cooperative: {data.cooperative}</div>
      )}
    </div>
  )
}

// ── Cooperative Payout Card ───────────────────────────────────────────
export function CoopPayoutCard({ data }) {
  return (
    <div className="rounded-lg bg-blue-50 border border-blue-200 p-4 text-sm space-y-1">
      <div className="flex items-center gap-2 font-semibold text-blue-700">
        <LuShip className="w-4 h-4" /> Cooperative Payout Recorded
      </div>
      {data?.cooperative && <div><span className="text-stone-500">Cooperative:</span> {data.cooperative}</div>}
      {data?.amount != null && <div><span className="text-stone-500">Amount:</span> ${Number(data.amount).toLocaleString()}</div>}
      {data?.tx_hash && (
        <div className="mt-1 text-xs text-stone-600">
          <LuLink className="inline w-3 h-3 mr-1" />
          <span className="font-mono">{data.tx_hash.slice(0, 20)}…</span>
        </div>
      )}
      {data?.block_number && (
        <div className="text-xs text-stone-500">Block: {data.block_number}</div>
      )}
    </div>
  )
}

// ── Generic card renderer ─────────────────────────────────────────────
export function ResponseCard({ responseType, data }) {
  if (!data || Object.keys(data).length === 0) return null

  switch (responseType) {
    case 'rfq_list':
    case 'rfq_created':
      return <RFQListCard data={data} />
    case 'offer_submitted':
    case 'offer_accepted':
    case 'offer_list':
      return <OfferListCard data={data} />
    case 'eudr_compliance':
    case 'mass_balance':
      return <EUDRComplianceCard data={data} />
    case 'batch_list':
      return <BatchListCard data={data} />
    case 'dpp':
    case 'dpp_validation':
    case 'lineage':
      return <DPPCard data={data} />
    case 'blockchain_status':
      return <BlockchainCard data={data} />
    case 'container_list':
    case 'container_purchase':
      return <ContainerCard data={data} />
    case 'verification_list':
      return <VerificationListCard data={data} />
    case 'pool_list':
      return <PoolListCard data={data} />
    case 'pool_commitment':
      return <CommitConfirmCard data={data} />
    case 'commitment_list':
      return <CommitmentListCard data={data} />
    case 'payment_confirmation':
    case 'payment_receipt':
      return <PaymentConfirmCard data={data} />
    case 'payment_status':
      return <PaymentStatusCard data={data} />
    case 'coop_payout':
      return <CoopPayoutCard data={data} />
    default:
      return null
  }
}
