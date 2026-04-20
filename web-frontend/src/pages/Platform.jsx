/**
 * Platform — "The trust layer for commodity commerce."
 *
 * Public-facing business model page showing:
 *  - The Closed Loop
 *  - Three Sides of the Platform (Origin, Logistics, Capital)
 *  - The Cash Cycle (Day 0 to Day 55)
 *  - Three Financing Channels
 *  - The Physical Oracle (Shipping Agent)
 *  - Competitive Position / Integration Moat
 *  - CTA
 *
 * Same visual language as HowItWorks: dark theme, SVG animations,
 * scroll-driven reveals, ConstellationBg, HexGrid, CircuitTrace.
 * Pure CSS/SVG animations.
 */

import React, { useState, useEffect, useRef, useMemo } from 'react'
import { Link } from 'react-router-dom'
import ConstellationBg from '../components/svg/ConstellationBg'
import { HexGrid, CircuitTrace, GlowOrb } from '../components/svg/SvgDecorations'

/* ═════════════════════════════════════════════════════════════════════
   HOOKS
   ═════════════════════════════════════════════════════════════════════ */

function useReveal(ref, threshold = 0.2) {
  const [revealed, setRevealed] = useState(false)
  useEffect(() => {
    if (!ref.current) return
    const obs = new IntersectionObserver(
      ([e]) => { if (e.isIntersecting) { setRevealed(true); obs.disconnect() } },
      { threshold },
    )
    obs.observe(ref.current)
    return () => obs.disconnect()
  }, [ref, threshold])
  return revealed
}

function useCountUp(target, active, duration = 1200) {
  const [val, setVal] = useState(0)
  useEffect(() => {
    if (!active) return
    let start = null
    const step = (ts) => {
      if (!start) start = ts
      const p = Math.min((ts - start) / duration, 1)
      setVal(Math.round(p * target))
      if (p < 1) requestAnimationFrame(step)
    }
    requestAnimationFrame(step)
  }, [active, target, duration])
  return val
}

/* ═════════════════════════════════════════════════════════════════════
   DATA
   ═════════════════════════════════════════════════════════════════════ */

const THREE_SIDES = [
  {
    id: 'origin',
    title: 'Origin',
    subtitle: 'Farmers, Cooperatives, Exporters',
    accent: '#c08e42',
    accentGlow: 'rgba(192,142,66,0.25)',
    icon: (
      <svg viewBox="0 0 48 48" fill="none" className="w-full h-full">
        <circle cx="24" cy="20" r="8" stroke="currentColor" strokeWidth="1.5" opacity="0.7">
          <animate attributeName="r" values="8;9;8" dur="3s" repeatCount="indefinite" />
        </circle>
        <path d="M24 28v6" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
        <path d="M18 34c0-3.3 2.7-6 6-6s6 2.7 6 6" stroke="currentColor" strokeWidth="1.5" fill="none" />
        <path d="M12 40h24" stroke="currentColor" strokeWidth="1" opacity="0.3" strokeLinecap="round" />
        <path d="M20 12l4-6 4 6" stroke="currentColor" strokeWidth="1" opacity="0.5" fill="none" />
      </svg>
    ),
    problem: 'Farmers wait 75-120 days for payment. Cooperatives take predatory bridge loans at 15-30% annually. EUDR documentation assembled manually over weeks.',
    solution: [
      'Payment on Day 14, not Day 90',
      'EUDR compliance built into every batch automatically',
      'Direct marketplace access to EU buyers',
      'Voice-first interface via Telegram - no apps, no forms, no literacy barrier',
    ],
  },
  {
    id: 'logistics',
    title: 'Logistics',
    subtitle: 'The Shipping Agent',
    accent: '#06b6d4',
    accentGlow: 'rgba(6,182,212,0.25)',
    icon: (
      <svg viewBox="0 0 48 48" fill="none" className="w-full h-full">
        <rect x="8" y="18" width="28" height="16" rx="2" stroke="currentColor" strokeWidth="1.5" opacity="0.7" />
        {[0,1,2].map(i => (
          <line key={i} x1={15 + i * 7} y1="18" x2={15 + i * 7} y2="34" stroke="currentColor" strokeWidth="0.5" opacity="0.3" />
        ))}
        <rect x="8" y="34" width="4" height="3" rx="1" fill="currentColor" opacity="0.4" />
        <rect x="32" y="34" width="4" height="3" rx="1" fill="currentColor" opacity="0.4" />
        <path d="M36 26h6l4 4v4h-10" stroke="currentColor" strokeWidth="1.5" fill="none" opacity="0.7" />
        <circle cx="14" cy="38" r="2" stroke="currentColor" strokeWidth="1" opacity="0.5" fill="none">
          <animate attributeName="r" values="2;2.5;2" dur="2s" repeatCount="indefinite" />
        </circle>
        <circle cx="38" cy="38" r="2" stroke="currentColor" strokeWidth="1" opacity="0.5" fill="none">
          <animate attributeName="r" values="2;2.5;2" dur="2s" begin="0.5s" repeatCount="indefinite" />
        </circle>
        <path d="M20 12l4-4 4 4" stroke="currentColor" strokeWidth="1" opacity="0.4" fill="none" />
        <line x1="24" y1="8" x2="24" y2="18" stroke="currentColor" strokeWidth="0.5" opacity="0.2" strokeDasharray="2 2" />
      </svg>
    ),
    problem: 'Customs clearance requires hours of manual documentation. EUDR data assembled from emails and spreadsheets. Port holds from incomplete paperwork.',
    solution: [
      'EUDR-ready customs data via API before container arrives',
      '2-5 day reduction in port dwell time',
      'Physical oracle role: custody confirmations trigger financing',
      'All platform volume flows through a single shipping partner',
    ],
  },
  {
    id: 'capital',
    title: 'Capital',
    subtitle: 'Liquidity Providers, Banks, DeFi Pools',
    accent: '#8b5cf6',
    accentGlow: 'rgba(139,92,246,0.25)',
    icon: (
      <svg viewBox="0 0 48 48" fill="none" className="w-full h-full">
        <circle cx="24" cy="24" r="14" stroke="currentColor" strokeWidth="1.5" opacity="0.5" />
        <circle cx="24" cy="24" r="10" stroke="currentColor" strokeWidth="0.5" opacity="0.3" strokeDasharray="3 3">
          <animateTransform attributeName="transform" type="rotate" values="0 24 24;360 24 24" dur="20s" repeatCount="indefinite" />
        </circle>
        <path d="M20 20v8l8-4z" fill="currentColor" opacity="0.3" />
        <text x="24" y="27" textAnchor="middle" fontSize="10" fill="currentColor" fontFamily="var(--font-mono)" opacity="0.8">$</text>
        <circle cx="24" cy="8" r="1.5" fill="currentColor" opacity="0.4">
          <animate attributeName="cy" values="8;10;8" dur="2.5s" repeatCount="indefinite" />
        </circle>
        <line x1="24" y1="10" x2="24" y2="14" stroke="currentColor" strokeWidth="0.5" opacity="0.3" />
      </svg>
    ),
    problem: 'Trade finance requires weeks of manual due diligence per deal. Collateral is paper warehouse receipts and bills of lading. No independent verification.',
    solution: [
      'Cryptographically complete collateral: GPS, satellite, oracle, blockchain',
      'Physical custody control via shipping agent throughout transit',
      'Short duration: 30-40 day cycles, not 12-month loans',
      'EUDR compliance eliminates customs rejection risk entirely',
    ],
  },
]

const TIMELINE_STEPS = [
  { day: '0', label: 'Harvest', desc: 'Farmer speaks to AI agent. Commission event recorded with GPS, quantity, variety.', accent: '#c08e42' },
  { day: '1-7', label: 'Verification', desc: 'Cooperative grades, verifies, and mints an ERC-1155 token for each batch.', accent: '#258c25' },
  { day: '7-10', label: 'Marketplace', desc: 'Listed on marketplace or matched to buyer RFQ. Price agreed, quantity locked.', accent: '#3b82f6' },
  { day: '10-14', label: 'Container', desc: 'Batches aggregated, deforestation check run, DPP generated, handed to shipping agent.', accent: '#f59e0b' },
  { day: '14', label: 'Financing', desc: 'Shipping agent confirms custody. Advance issued. Seller paid immediately.', accent: '#8b5cf6', highlight: true },
  { day: '14-45', label: 'Transit', desc: 'Container moves from Djibouti through Suez to EU port. All parties track in real time.', accent: '#06b6d4' },
  { day: '35-50', label: 'Customs', desc: 'Customs cleared at EU port using DPP data. EUDR due diligence filed automatically.', accent: '#10b981' },
  { day: '45-55', label: 'Settlement', desc: 'Buyer confirms receipt. Full payment collected. Token released. On-chain settlement.', accent: '#ec4899' },
]

const FINANCING_CHANNELS = [
  {
    id: 'lp',
    title: 'Private Capital',
    subtitle: 'Impact investors, commodity funds, family offices',
    phase: 'Phase 1',
    speed: 'Same day',
    accent: '#c08e42',
    icon: (
      <svg viewBox="0 0 32 32" fill="none" stroke="currentColor" strokeWidth="1.5" className="w-full h-full">
        <circle cx="16" cy="12" r="6" opacity="0.7" />
        <path d="M8 26c0-4.4 3.6-8 8-8s8 3.6 8 8" opacity="0.5" />
      </svg>
    ),
  },
  {
    id: 'bank',
    title: 'Bank Facility',
    subtitle: 'Trade finance banks, receivables purchase',
    phase: 'Phase 2',
    speed: '24-48 hours',
    accent: '#3b82f6',
    icon: (
      <svg viewBox="0 0 32 32" fill="none" stroke="currentColor" strokeWidth="1.5" className="w-full h-full">
        <path d="M4 14h24" opacity="0.5" />
        <path d="M16 4l12 10H4z" opacity="0.7" fill="none" />
        <line x1="8" y1="14" x2="8" y2="24" opacity="0.5" />
        <line x1="14" y1="14" x2="14" y2="24" opacity="0.5" />
        <line x1="20" y1="14" x2="20" y2="24" opacity="0.5" />
        <line x1="26" y1="14" x2="26" y2="24" opacity="0.5" />
        <rect x="4" y="24" width="24" height="3" rx="0.5" opacity="0.4" />
      </svg>
    ),
  },
  {
    id: 'onchain',
    title: 'On-Chain Pool',
    subtitle: 'DeFi LPs via ERC-4626 vault on Base',
    phase: 'Phase 3',
    speed: 'Instant',
    accent: '#8b5cf6',
    icon: (
      <svg viewBox="0 0 32 32" fill="none" stroke="currentColor" strokeWidth="1.5" className="w-full h-full">
        <rect x="6" y="8" width="20" height="16" rx="3" opacity="0.5" />
        <path d="M6 14h20" opacity="0.3" />
        <circle cx="16" cy="20" r="3" opacity="0.7">
          <animate attributeName="r" values="3;3.5;3" dur="2s" repeatCount="indefinite" />
        </circle>
        <path d="M13.5 20l1.5 1.5 3-3" strokeWidth="1" opacity="0.6" />
      </svg>
    ),
  },
]

const MOAT_LAYERS = [
  { label: 'Farmer Relationships', desc: '1,000+ registered farmers with DIDs, GPS-verified plots, production history', icon: 'FR' },
  { label: 'Data Depth', desc: 'Years of production data, quality records, compliance history, voice recordings', icon: 'DD' },
  { label: 'Shipping Exclusivity', desc: 'Contractual logistics partnership. Physical oracle confirmations are the trust anchor.', icon: 'SE' },
  { label: 'Track Record', desc: 'Every completed container builds the case for the next LP. Default rates, cycle times, yield.', icon: 'TR' },
  { label: 'Blockchain Permanence', desc: 'On-chain records cannot be erased or replicated. Provenance anchors live on Base forever.', icon: 'BP' },
  { label: 'EUDR First-Mover', desc: 'GPS and compliance data collected from Day 1. Competitors are scrambling to backfill.', icon: 'EU' },
]

const INTEGRATION_COMPARISON = [
  { capability: 'Traceability', point: 'Sourcemap, FarmForce', vl: true },
  { capability: 'Trade Finance', point: 'Cargill, Macquarie', vl: true },
  { capability: 'Customs Compliance', point: 'Preferred by Nature', vl: true },
  { capability: 'Shipping & Logistics', point: 'Freight forwarders', vl: true },
  { capability: 'Marketplace', point: 'Commodity exchanges', vl: true },
  { capability: 'Blockchain Provenance', point: 'Track-and-trace startups', vl: true },
  { capability: 'All Six Integrated', point: '', vl: true, highlight: true },
]

/* ═════════════════════════════════════════════════════════════════════
   SVG ILLUSTRATIONS
   ═════════════════════════════════════════════════════════════════════ */

function ClosedLoopDiagram({ revealed }) {
  const nodes = [
    { x: 200, y: 30,  label: 'Farmer',     abbr: 'FM', accent: '#c08e42' },
    { x: 370, y: 90,  label: 'Cooperative', abbr: 'CO', accent: '#258c25' },
    { x: 420, y: 220, label: 'Marketplace', abbr: 'MK', accent: '#3b82f6' },
    { x: 320, y: 330, label: 'LP Advance',  abbr: 'LP', accent: '#8b5cf6' },
    { x: 140, y: 330, label: 'Ship Agent',  abbr: 'SA', accent: '#06b6d4' },
    { x: 40,  y: 220, label: 'Customs',     abbr: 'EU', accent: '#10b981' },
    { x: 90,  y: 90,  label: 'Buyer',       abbr: 'BY', accent: '#f59e0b' },
  ]
  const edges = [[0,1],[1,2],[2,3],[3,4],[4,5],[5,6],[6,0]]

  return (
    <svg viewBox="-10 -10 480 380" className="w-full max-w-md mx-auto" style={{ overflow: 'visible' }}>
      <defs>
        <filter id="cl-glow">
          <feGaussianBlur stdDeviation="6" result="blur" />
          <feMerge><feMergeNode in="blur" /><feMergeNode in="SourceGraphic" /></feMerge>
        </filter>
        <marker id="cl-arrow" viewBox="0 0 10 8" refX="9" refY="4" markerWidth="6" markerHeight="5" orient="auto-start-reverse">
          <path d="M0 0L10 4L0 8z" fill="#10B981" opacity="0.5" />
        </marker>
      </defs>

      {/* Edges with arrows */}
      {edges.map(([a,b], i) => {
        const na = nodes[a], nb = nodes[b]
        return (
          <g key={`e${i}`}>
            <line
              x1={na.x} y1={na.y} x2={nb.x} y2={nb.y}
              stroke="#10B981" strokeWidth="1" opacity={revealed ? 0.3 : 0.05}
              markerEnd="url(#cl-arrow)"
              className={revealed ? 'pl-edge-active' : ''}
              style={{ animationDelay: `${i * 0.2}s` }}
            />
            {revealed && (
              <circle r="2.5" fill="#10B981" opacity="0.7">
                <animateMotion dur={`${3 + (i % 2)}s`} repeatCount="indefinite" path={`M${na.x},${na.y} L${nb.x},${nb.y}`} />
              </circle>
            )}
          </g>
        )
      })}

      {/* Center label */}
      <text x="230" y="185" textAnchor="middle" fontSize="9" fill="white" opacity="0.15" fontFamily="var(--font-mono)" letterSpacing="2">
        CLOSED LOOP
      </text>

      {/* Nodes */}
      {nodes.map((node, i) => (
        <g key={node.abbr}>
          {revealed && (
            <circle cx={node.x} cy={node.y} r="28" fill="none" stroke={node.accent} strokeWidth="0.6" opacity="0.2" filter="url(#cl-glow)">
              <animate attributeName="r" values="28;32;28" dur="3s" begin={`${i * 0.3}s`} repeatCount="indefinite" />
            </circle>
          )}
          <circle cx={node.x} cy={node.y} r="22" fill={`${node.accent}15`} stroke={node.accent} strokeWidth={revealed ? 1 : 0.5} opacity={revealed ? 1 : 0.3} />
          <text x={node.x} y={node.y + 1} textAnchor="middle" dominantBaseline="middle" fontSize="10" fontFamily="var(--font-mono)" fontWeight="600" fill={node.accent} opacity="0.9">
            {node.abbr}
          </text>
          <text x={node.x} y={node.y + 36} textAnchor="middle" fontSize="8" fill="white" opacity={revealed ? 0.5 : 0.2} fontFamily="var(--font-sans)">
            {node.label}
          </text>
        </g>
      ))}
    </svg>
  )
}

/* ── Physical Oracle Diagram ──────────────────────────────────── */

function OracleDiagram({ revealed }) {
  const confirmations = [
    { y: 40,  label: 'Custody Receipt', trigger: 'LP advance eligibility', accent: '#06b6d4' },
    { y: 120, label: 'Customs Clearance', trigger: 'EU market entry confirmed', accent: '#10b981' },
    { y: 200, label: 'Delivery Confirmation', trigger: 'Settlement trigger', accent: '#f59e0b' },
  ]

  return (
    <svg viewBox="0 0 400 260" className="w-full max-w-sm mx-auto" style={{ overflow: 'visible' }}>
      <defs>
        <filter id="or-glow">
          <feGaussianBlur stdDeviation="4" result="blur" />
          <feMerge><feMergeNode in="blur" /><feMergeNode in="SourceGraphic" /></feMerge>
        </filter>
      </defs>

      {/* Central spine */}
      <line x1="80" y1="20" x2="80" y2="240" stroke="white" strokeWidth="0.5" opacity="0.1" />

      {/* Shipping agent label */}
      <text x="80" y="12" textAnchor="middle" fontSize="8" fill="white" opacity="0.3" fontFamily="var(--font-mono)" letterSpacing="1.5">
        SHIPPING AGENT
      </text>

      {confirmations.map((c, i) => (
        <g key={i}>
          {/* Dot on spine */}
          <circle cx="80" cy={c.y} r={revealed ? 6 : 3} fill={`${c.accent}30`} stroke={c.accent} strokeWidth="1" opacity={revealed ? 1 : 0.3}>
            {revealed && <animate attributeName="r" values="6;8;6" dur="2.5s" begin={`${i * 0.4}s`} repeatCount="indefinite" />}
          </circle>

          {/* Connection line */}
          <line x1="86" y1={c.y} x2="150" y2={c.y} stroke={c.accent} strokeWidth="0.8" opacity={revealed ? 0.4 : 0.1} strokeDasharray={revealed ? 'none' : '3 4'} />

          {/* Label card */}
          <rect x="150" y={c.y - 18} width="230" height="36" rx="6" fill={`${c.accent}08`} stroke={c.accent} strokeWidth="0.5" opacity={revealed ? 0.6 : 0.15} />
          <text x="165" y={c.y - 3} fontSize="10" fontWeight="600" fill="white" opacity={revealed ? 0.8 : 0.3} fontFamily="var(--font-sans)">
            {c.label}
          </text>
          <text x="165" y={c.y + 11} fontSize="8" fill={c.accent} opacity={revealed ? 0.7 : 0.2} fontFamily="var(--font-mono)">
            {c.trigger}
          </text>

          {/* Pulse on confirmation dot */}
          {revealed && (
            <circle cx="80" cy={c.y} r="12" fill="none" stroke={c.accent} strokeWidth="0.5" opacity="0" filter="url(#or-glow)">
              <animate attributeName="r" values="6;18;6" dur="3s" begin={`${i * 0.8}s`} repeatCount="indefinite" />
              <animate attributeName="opacity" values="0.4;0;0.4" dur="3s" begin={`${i * 0.8}s`} repeatCount="indefinite" />
            </circle>
          )}
        </g>
      ))}
    </svg>
  )
}

/* ═════════════════════════════════════════════════════════════════════
   SECTIONS
   ═════════════════════════════════════════════════════════════════════ */

function HeroSection() {
  const ref = useRef(null)
  const revealed = useReveal(ref, 0.1)
  return (
    <section
      ref={ref}
      className="relative min-h-[85vh] flex flex-col items-center justify-center text-center px-6 overflow-hidden"
      style={{ background: 'linear-gradient(135deg, #1c1917 0%, #292524 40%, #1c1917 100%)' }}
    >
      <ConstellationBg />
      <HexGrid className="absolute inset-0 text-white" />
      <div className="absolute -top-24 -left-24 w-96 h-96 rounded-full bg-purple-900/15 blur-3xl animate-float-slow" />
      <div className="absolute top-1/3 -right-32 w-80 h-80 rounded-full bg-cyan-700/10 blur-3xl animate-float-slower" />
      <div className="absolute -bottom-16 left-1/3 w-72 h-72 rounded-full bg-amber-400/8 blur-3xl animate-float-slow" style={{ animationDelay: '3s' }} />

      <div className={`relative z-10 max-w-2xl transition-all duration-1000 ${revealed ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-8'}`}>
        <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-white/5 border border-white/10 mb-8">
          <span className="w-2 h-2 rounded-full bg-violet-400 animate-pulse-dot" />
          <span className="text-[11px] text-white/50 font-mono tracking-wider">The Platform</span>
        </div>

        <h1 className="text-4xl md:text-6xl font-bold font-display leading-tight">
          <span className="text-white/90">The trust layer for </span>
          <span className="text-gradient-animated">commodity commerce.</span>
        </h1>
        <h2 className="mt-3 text-xl md:text-2xl font-display text-white/50">
          Verified data. Tokenized assets. Integrated financing.
        </h2>
        <p className="mt-6 text-sm md:text-base text-white/35 max-w-lg mx-auto leading-relaxed">
          The Voice Ledger connects origin, logistics, and capital into a single closed loop. Every participant is better off. Every transaction is verifiable.
        </p>
      </div>

      <div className="absolute bottom-8 left-1/2 -translate-x-1/2 flex flex-col items-center gap-2 animate-bounce">
        <span className="text-[10px] text-white/20 tracking-widest uppercase font-mono">Scroll</span>
        <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="white" strokeWidth="1.5" strokeLinecap="round" opacity="0.2">
          <path d="M4 6l4 4 4-4" />
        </svg>
      </div>
    </section>
  )
}

/* ── Closed Loop Section ────────────────────────────────────────── */

function ClosedLoopSection() {
  const ref = useRef(null)
  const revealed = useReveal(ref, 0.15)
  return (
    <section
      ref={ref}
      className="relative py-24 px-6 overflow-hidden"
      style={{ background: 'linear-gradient(180deg, #1c1917 0%, #0c0a09 50%, #1c1917 100%)' }}
    >
      <div className="absolute inset-0 opacity-[0.03]"><ConstellationBg /></div>

      <div className={`relative z-10 max-w-5xl mx-auto transition-all duration-1000 ${revealed ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-8'}`}>
        <div className="text-center mb-16">
          <span className="text-[11px] text-emerald-400/50 font-mono tracking-widest uppercase">The Model</span>
          <h2 className="mt-2 text-3xl md:text-4xl font-display font-bold text-white/90">
            The Closed Loop
          </h2>
          <p className="mt-3 text-sm text-white/35 max-w-md mx-auto">
            Every arrow is a verified data event. Every transition generates platform value.
          </p>
        </div>

        <ClosedLoopDiagram revealed={revealed} />

        <div className="mt-16 grid md:grid-cols-3 gap-6 max-w-3xl mx-auto">
          {[
            { label: 'Data Events', value: 'Every step recorded', accent: '#10b981' },
            { label: 'Blockchain Anchored', value: 'Immutable, auditable', accent: '#8b5cf6' },
            { label: 'Value Captured', value: 'At every transition', accent: '#c08e42' },
          ].map((item, i) => (
            <div key={i} className="text-center">
              <div className="text-xs font-mono tracking-wider uppercase mb-1" style={{ color: `${item.accent}90` }}>{item.label}</div>
              <div className="text-sm text-white/50">{item.value}</div>
            </div>
          ))}
        </div>
      </div>
    </section>
  )
}

/* ── Three Sides Section ────────────────────────────────────────── */

function ThreeSidesSection() {
  const ref = useRef(null)
  const revealed = useReveal(ref, 0.1)
  const [activeTab, setActiveTab] = useState(0)
  const side = THREE_SIDES[activeTab]

  return (
    <section
      ref={ref}
      className="relative py-24 px-6 overflow-hidden"
      style={{ background: 'linear-gradient(135deg, #1c1917 0%, #292524 50%, #1c1917 100%)' }}
    >
      <div
        className="absolute w-96 h-96 rounded-full blur-3xl pointer-events-none animate-float-slow transition-colors duration-700"
        style={{ backgroundColor: side.accentGlow, top: '10%', right: '-8rem' }}
      />

      <div className={`relative z-10 max-w-5xl mx-auto transition-all duration-1000 ${revealed ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-8'}`}>
        <div className="text-center mb-12">
          <span className="text-[11px] text-amber-400/50 font-mono tracking-widest uppercase">Three Sides</span>
          <h2 className="mt-2 text-3xl md:text-4xl font-display font-bold text-white/90">
            What Each Side Gets
          </h2>
        </div>

        {/* Tab buttons */}
        <div className="flex justify-center gap-3 mb-12">
          {THREE_SIDES.map((s, i) => (
            <button
              key={s.id}
              onClick={() => setActiveTab(i)}
              className={`px-5 py-2.5 rounded-xl text-sm font-medium transition-all duration-300 ${
                activeTab === i
                  ? 'text-white shadow-lg scale-105'
                  : 'bg-white/5 text-white/40 hover:text-white/60 hover:bg-white/8'
              }`}
              style={activeTab === i ? { backgroundColor: `${s.accent}25`, border: `1px solid ${s.accent}40`, color: s.accent } : { border: '1px solid transparent' }}
            >
              {s.title}
            </button>
          ))}
        </div>

        {/* Content card */}
        <div
          className="grid md:grid-cols-2 gap-10 items-start rounded-2xl p-8 md:p-10 transition-all duration-500"
          style={{
            background: `radial-gradient(ellipse at top left, ${side.accent}08, transparent 60%)`,
            border: `1px solid ${side.accent}15`,
          }}
        >
          {/* Left: icon + problem */}
          <div>
            <div className="flex items-center gap-4 mb-6">
              <div className="w-14 h-14 rounded-xl flex items-center justify-center" style={{ backgroundColor: `${side.accent}15`, color: side.accent }}>
                {side.icon}
              </div>
              <div>
                <h3 className="text-xl font-display font-bold text-white/90">{side.title}</h3>
                <p className="text-xs text-white/40">{side.subtitle}</p>
              </div>
            </div>

            <div className="rounded-lg p-4 mb-6" style={{ backgroundColor: 'rgba(239,68,68,0.06)', border: '1px solid rgba(239,68,68,0.1)' }}>
              <div className="flex items-center gap-2 mb-2">
                <svg viewBox="0 0 16 16" fill="none" stroke="#ef4444" strokeWidth="1.5" className="w-4 h-4" opacity="0.6">
                  <circle cx="8" cy="8" r="6" />
                  <line x1="8" y1="5" x2="8" y2="8.5" />
                  <circle cx="8" cy="10.5" r="0.5" fill="#ef4444" />
                </svg>
                <span className="text-xs font-semibold text-red-400/70 uppercase tracking-wider">The Problem Today</span>
              </div>
              <p className="text-sm text-white/40 leading-relaxed">{side.problem}</p>
            </div>
          </div>

          {/* Right: solution bullets */}
          <div>
            <div className="flex items-center gap-2 mb-4">
              <svg viewBox="0 0 16 16" fill="none" stroke={side.accent} strokeWidth="1.5" className="w-4 h-4" opacity="0.6">
                <path d="M3 8l3 3 7-7" />
              </svg>
              <span className="text-xs font-semibold uppercase tracking-wider" style={{ color: `${side.accent}90` }}>What The Voice Ledger Delivers</span>
            </div>
            <div className="space-y-4">
              {side.solution.map((s, i) => (
                <div key={i} className="flex items-start gap-3 pl-side-item" style={{ animationDelay: `${i * 0.1}s` }}>
                  <div className="mt-1.5 w-2 h-2 rounded-full shrink-0" style={{ backgroundColor: side.accent }} />
                  <span className="text-sm text-white/60 leading-relaxed">{s}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </section>
  )
}

/* ── Cash Cycle Timeline Section ────────────────────────────────── */

function TimelineSection() {
  const ref = useRef(null)
  const revealed = useReveal(ref, 0.1)

  return (
    <section
      ref={ref}
      className="relative py-24 px-6 overflow-hidden"
      style={{ background: 'linear-gradient(180deg, #1c1917 0%, #0c0a09 50%, #1c1917 100%)' }}
    >
      <div className="absolute inset-0 opacity-[0.02]"><HexGrid className="w-full h-full text-white" /></div>

      <div className={`relative z-10 max-w-4xl mx-auto transition-all duration-1000 ${revealed ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-8'}`}>
        <div className="text-center mb-16">
          <span className="text-[11px] text-cyan-400/50 font-mono tracking-widest uppercase">End to End</span>
          <h2 className="mt-2 text-3xl md:text-4xl font-display font-bold text-white/90">
            The Cash Cycle
          </h2>
          <p className="mt-3 text-sm text-white/35 max-w-md mx-auto">
            From harvest to settlement in 55 days. The farmer is paid on Day 14, not Day 90.
          </p>
        </div>

        {/* Timeline */}
        <div className="relative">
          {/* Vertical line */}
          <div className="absolute left-6 md:left-8 top-0 bottom-0 w-px bg-gradient-to-b from-transparent via-white/10 to-transparent" />

          <div className="space-y-1">
            {TIMELINE_STEPS.map((step, i) => (
              <div
                key={i}
                className={`relative flex items-start gap-6 md:gap-8 py-4 pl-timeline-step ${revealed ? 'pl-fade-in' : 'opacity-0'}`}
                style={{ animationDelay: `${i * 0.1}s` }}
              >
                {/* Day marker */}
                <div className="relative z-10 shrink-0">
                  <div
                    className={`w-12 h-12 md:w-16 md:h-16 rounded-xl flex flex-col items-center justify-center ${step.highlight ? 'ring-2 ring-offset-2 ring-offset-stone-950' : ''}`}
                    style={{
                      backgroundColor: `${step.accent}15`,
                      border: `1px solid ${step.accent}30`,
                      boxShadow: step.highlight ? `0 0 20px ${step.accent}30` : 'none',
                      ...(step.highlight ? { ringColor: step.accent } : {}),
                    }}
                  >
                    <span className="text-[9px] font-mono uppercase tracking-wider" style={{ color: `${step.accent}80` }}>Day</span>
                    <span className="text-sm font-bold font-mono" style={{ color: step.accent }}>{step.day}</span>
                  </div>
                  {/* Connector dot */}
                  <div
                    className="absolute -left-[15px] md:-left-[13px] top-1/2 -translate-y-1/2 w-2.5 h-2.5 rounded-full border-2"
                    style={{ borderColor: step.accent, backgroundColor: revealed ? step.accent : 'transparent' }}
                  />
                </div>

                {/* Content */}
                <div className="pt-1 md:pt-3 flex-1 min-w-0">
                  <h4 className="text-base font-semibold text-white/80 font-display">{step.label}</h4>
                  <p className="mt-1 text-sm text-white/35 leading-relaxed">{step.desc}</p>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Comparison bar */}
        <div className="mt-16 rounded-2xl p-6 md:p-8" style={{ background: 'rgba(255,255,255,0.02)', border: '1px solid rgba(255,255,255,0.06)' }}>
          <div className="grid md:grid-cols-2 gap-8">
            <div className="text-center">
              <div className="text-xs font-mono text-red-400/50 uppercase tracking-wider mb-2">Traditional</div>
              <div className="text-2xl font-bold text-red-400/70 font-mono">Day 60-120</div>
              <div className="text-xs text-white/25 mt-1">Seller receives payment</div>
              <div className="mt-3 text-sm text-white/30">3-8% financing cost (Letter of Credit)</div>
            </div>
            <div className="text-center">
              <div className="text-xs font-mono text-emerald-400/50 uppercase tracking-wider mb-2">The Voice Ledger</div>
              <div className="text-2xl font-bold text-emerald-400/70 font-mono">Day 14</div>
              <div className="text-xs text-white/25 mt-1">Seller receives payment</div>
              <div className="mt-3 text-sm text-white/30">Fraction of traditional financing cost</div>
            </div>
          </div>
        </div>
      </div>
    </section>
  )
}

/* ── Financing Channels Section ─────────────────────────────────── */

function FinancingSection() {
  const ref = useRef(null)
  const revealed = useReveal(ref, 0.15)

  return (
    <section
      ref={ref}
      className="relative py-24 px-6 overflow-hidden"
      style={{ background: 'linear-gradient(135deg, #1c1917 0%, #292524 50%, #1c1917 100%)' }}
    >
      <CircuitTrace className="absolute inset-0 w-full h-full text-white" />

      <div className={`relative z-10 max-w-5xl mx-auto transition-all duration-1000 ${revealed ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-8'}`}>
        <div className="text-center mb-16">
          <span className="text-[11px] text-violet-400/50 font-mono tracking-widest uppercase">Capital Infrastructure</span>
          <h2 className="mt-2 text-3xl md:text-4xl font-display font-bold text-white/90">
            Three Financing Channels
          </h2>
          <p className="mt-3 text-sm text-white/35 max-w-lg mx-auto">
            The platform orchestrates across all three based on trade profile, available capacity, and cost optimization.
          </p>
        </div>

        <div className="grid md:grid-cols-3 gap-6">
          {FINANCING_CHANNELS.map((ch, i) => (
            <div
              key={ch.id}
              className="group relative rounded-2xl p-6 transition-all duration-300 hover:scale-[1.02] pl-card-pop"
              style={{
                background: `radial-gradient(ellipse at top, ${ch.accent}06, transparent 70%)`,
                border: `1px solid ${ch.accent}15`,
                animationDelay: `${i * 0.15}s`,
              }}
            >
              {/* Hover glow */}
              <div
                className="absolute inset-0 rounded-2xl opacity-0 group-hover:opacity-100 transition-opacity duration-500 pointer-events-none"
                style={{ background: `radial-gradient(circle at 50% 20%, ${ch.accent}12, transparent 70%)` }}
              />

              <div className="relative z-10">
                {/* Phase badge */}
                <div className="flex items-center justify-between mb-4">
                  <div className="w-10 h-10 rounded-lg flex items-center justify-center" style={{ backgroundColor: `${ch.accent}15`, color: ch.accent }}>
                    {ch.icon}
                  </div>
                  <span
                    className="text-[10px] font-mono tracking-wider px-2 py-0.5 rounded-full"
                    style={{ backgroundColor: `${ch.accent}10`, color: `${ch.accent}90`, border: `1px solid ${ch.accent}20` }}
                  >
                    {ch.phase}
                  </span>
                </div>

                <h3 className="text-lg font-display font-bold text-white/85 mb-1">{ch.title}</h3>
                <p className="text-xs text-white/35 leading-relaxed mb-4">{ch.subtitle}</p>

                <div className="flex items-center gap-2 pt-3 border-t" style={{ borderColor: `${ch.accent}10` }}>
                  <svg viewBox="0 0 16 16" fill="none" stroke={ch.accent} strokeWidth="1.5" className="w-3.5 h-3.5" opacity="0.5">
                    <circle cx="8" cy="8" r="6" />
                    <path d="M8 5v3l2 1.5" />
                  </svg>
                  <span className="text-xs font-mono" style={{ color: `${ch.accent}70` }}>{ch.speed}</span>
                </div>
              </div>
            </div>
          ))}
        </div>

        {/* Orchestration note */}
        <div className="mt-10 text-center">
          <div className="inline-flex items-center gap-3 px-5 py-3 rounded-xl bg-white/[0.03] border border-white/[0.06]">
            <svg viewBox="0 0 20 20" fill="none" stroke="#10b981" strokeWidth="1.2" className="w-5 h-5" opacity="0.5">
              <path d="M10 2v16M2 10h16" strokeLinecap="round" />
              <circle cx="10" cy="10" r="8" />
            </svg>
            <span className="text-xs text-white/40">All three channels operate simultaneously on the same platform</span>
          </div>
        </div>
      </div>
    </section>
  )
}

/* ── Physical Oracle Section ───────────────────────────────────── */

function OracleSection() {
  const ref = useRef(null)
  const revealed = useReveal(ref, 0.15)

  return (
    <section
      ref={ref}
      className="relative py-24 px-6 overflow-hidden"
      style={{ background: 'linear-gradient(180deg, #1c1917 0%, #0c0a09 50%, #1c1917 100%)' }}
    >
      <GlowOrb className="absolute top-1/4 left-1/4 w-[400px] h-[400px]" color="#06b6d4" />

      <div className={`relative z-10 max-w-5xl mx-auto transition-all duration-1000 ${revealed ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-8'}`}>
        <div className="grid md:grid-cols-2 gap-12 items-center">
          <div>
            <span className="text-[11px] text-cyan-400/50 font-mono tracking-widest uppercase">The Physical Oracle</span>
            <h2 className="mt-2 text-3xl md:text-4xl font-display font-bold text-white/90">
              More Than Logistics
            </h2>
            <p className="mt-4 text-sm text-white/35 leading-relaxed">
              The shipping agent is the physical oracle in The Voice Ledger model. Their confirmations are the real-world events that trigger financial flows. Without trusted physical custody control, the financing model does not work.
            </p>

            <div className="mt-8 space-y-4">
              {[
                { label: 'Weight verification', desc: 'Container weight matches token metadata within 2% tolerance' },
                { label: 'SSCC match', desc: 'Physical container identifier matches on-chain token' },
                { label: 'Condition check', desc: 'Goods in expected condition, no damage, no substitution' },
                { label: 'Documentation', desc: 'Export docs, phytosanitary certificate validated at pickup' },
              ].map((v, i) => (
                <div key={i} className="flex items-start gap-3">
                  <div className="mt-1 w-2 h-2 rounded-full bg-cyan-500 shrink-0" />
                  <div>
                    <span className="text-sm font-semibold text-white/70">{v.label}</span>
                    <span className="text-xs text-white/30 ml-2">{v.desc}</span>
                  </div>
                </div>
              ))}
            </div>
          </div>

          <OracleDiagram revealed={revealed} />
        </div>
      </div>
    </section>
  )
}

/* ── Integration Moat Section ──────────────────────────────────── */

function MoatSection() {
  const ref = useRef(null)
  const revealed = useReveal(ref, 0.15)

  return (
    <section
      ref={ref}
      className="relative py-24 px-6 overflow-hidden"
      style={{ background: 'linear-gradient(135deg, #1c1917 0%, #292524 50%, #1c1917 100%)' }}
    >
      <div className="absolute inset-0 opacity-[0.02]"><HexGrid className="w-full h-full text-white" /></div>

      <div className={`relative z-10 max-w-5xl mx-auto transition-all duration-1000 ${revealed ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-8'}`}>
        <div className="text-center mb-16">
          <span className="text-[11px] text-amber-400/50 font-mono tracking-widest uppercase">Competitive Position</span>
          <h2 className="mt-2 text-3xl md:text-4xl font-display font-bold text-white/90">
            The Integration Moat
          </h2>
          <p className="mt-3 text-sm text-white/35 max-w-lg mx-auto">
            Point solutions exist for each piece. None offer the integrated platform.
          </p>
        </div>

        {/* Integration comparison table */}
        <div className="rounded-2xl overflow-hidden mb-12" style={{ border: '1px solid rgba(255,255,255,0.06)' }}>
          <div className="grid grid-cols-3 gap-px bg-white/[0.03]">
            {/* Header */}
            <div className="px-4 py-3 bg-stone-900/80 text-xs font-mono text-white/30 uppercase tracking-wider">Capability</div>
            <div className="px-4 py-3 bg-stone-900/80 text-xs font-mono text-white/30 uppercase tracking-wider">Point Solutions</div>
            <div className="px-4 py-3 bg-stone-900/80 text-xs font-mono text-white/30 uppercase tracking-wider text-center">The Voice Ledger</div>

            {/* Rows */}
            {INTEGRATION_COMPARISON.map((row, i) => (
              <React.Fragment key={i}>
                <div className={`px-4 py-3 text-sm ${row.highlight ? 'text-emerald-400/80 font-semibold' : 'text-white/60'}`}
                     style={{ background: row.highlight ? 'rgba(16,185,129,0.05)' : i % 2 === 0 ? 'rgba(255,255,255,0.01)' : 'transparent' }}>
                  {row.capability}
                </div>
                <div className={`px-4 py-3 text-xs ${row.highlight ? 'text-white/30' : 'text-white/25'}`}
                     style={{ background: row.highlight ? 'rgba(16,185,129,0.05)' : i % 2 === 0 ? 'rgba(255,255,255,0.01)' : 'transparent' }}>
                  {row.point || '-'}
                </div>
                <div className="px-4 py-3 flex justify-center"
                     style={{ background: row.highlight ? 'rgba(16,185,129,0.05)' : i % 2 === 0 ? 'rgba(255,255,255,0.01)' : 'transparent' }}>
                  <svg viewBox="0 0 20 20" className="w-5 h-5" fill="none" stroke={row.highlight ? '#10b981' : '#10b981'} strokeWidth="2" opacity={row.highlight ? 0.9 : 0.5}>
                    <path d="M5 10l3 3 7-7" strokeLinecap="round" strokeLinejoin="round" />
                  </svg>
                </div>
              </React.Fragment>
            ))}
          </div>
        </div>

        {/* Defensibility layers */}
        <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {MOAT_LAYERS.map((layer, i) => (
            <div
              key={i}
              className="group rounded-xl p-4 transition-all duration-300 hover:scale-[1.01] pl-card-pop"
              style={{
                background: 'rgba(255,255,255,0.02)',
                border: '1px solid rgba(255,255,255,0.05)',
                animationDelay: `${i * 0.08}s`,
              }}
            >
              <div className="flex items-center gap-3 mb-2">
                <div className="w-8 h-8 rounded-lg flex items-center justify-center bg-amber-500/10 border border-amber-500/15">
                  <span className="text-[10px] font-mono font-bold text-amber-400/70">{layer.icon}</span>
                </div>
                <span className="text-sm font-semibold text-white/75">{layer.label}</span>
              </div>
              <p className="text-xs text-white/30 leading-relaxed">{layer.desc}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  )
}

/* ── Stats / Numbers Section ────────────────────────────────────── */

function StatsSection() {
  const ref = useRef(null)
  const revealed = useReveal(ref, 0.2)

  const stats = [
    { label: 'Smart contracts', value: 7 },
    { label: 'Financing channels', value: 3 },
    { label: 'Supply chain events tracked', value: 12 },
    { label: 'EUDR Article 9 fields', value: 11 },
    { label: 'GS1 standards', value: 3 },
    { label: 'User roles', value: 5 },
  ]

  return (
    <section
      ref={ref}
      className="relative py-20 px-6"
      style={{ background: 'linear-gradient(180deg, #1c1917, #0c0a09)' }}
    >
      <div className={`relative z-10 max-w-4xl mx-auto text-center transition-all duration-1000 ${revealed ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-8'}`}>
        <span className="text-[11px] text-violet-400/50 font-mono tracking-widest uppercase">By The Numbers</span>
        <div className="mt-8 grid grid-cols-3 md:grid-cols-6 gap-8">
          {stats.map((s, i) => (
            <StatBox key={i} label={s.label} value={s.value} active={revealed} />
          ))}
        </div>
      </div>
    </section>
  )
}

function StatBox({ label, value, active }) {
  const count = useCountUp(value, active)
  return (
    <div className="flex flex-col items-center gap-1">
      <span className="text-3xl md:text-4xl font-bold font-mono text-white/90">{count}</span>
      <span className="text-[11px] text-white/40 tracking-wider uppercase">{label}</span>
    </div>
  )
}

/* ── CTA Section ────────────────────────────────────────────────── */

function CTASection() {
  const ref = useRef(null)
  const revealed = useReveal(ref, 0.2)

  return (
    <section
      ref={ref}
      className="relative py-24 px-6 overflow-hidden"
      style={{ background: 'linear-gradient(135deg, #14532d 0%, #166534 50%, #14532d 100%)' }}
    >
      <HexGrid className="absolute inset-0 text-white" />
      <CircuitTrace className="absolute inset-0 w-full h-full text-white" />
      <GlowOrb className="absolute top-0 right-1/4 w-[300px] h-[300px]" color="#ffffff" />

      <div className={`relative z-10 max-w-2xl mx-auto text-center transition-all duration-1000 ${revealed ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-8'}`}>
        <h2 className="text-3xl md:text-4xl font-display font-bold text-white/95">
          Everyone is better off.
        </h2>
        <p className="mt-4 text-sm text-white/50 max-w-lg mx-auto leading-relaxed">
          The farmer gets paid in 14 days instead of 90. The cooperative avoids predatory loans. The exporter's compliance is built in. The shipping agent gets guaranteed volume. The buyer gets verified, delivered coffee. The capital provider gets transparent, asset-backed yield.
        </p>
        <div className="mt-8 flex flex-col sm:flex-row items-center justify-center gap-4">
          <Link
            to="/how-it-works"
            className="px-8 py-3 rounded-xl bg-white text-stone-900 font-semibold text-sm hover:bg-white/90 hover:scale-105 active:scale-95 transition-all shadow-lg shadow-black/20"
          >
            See How It Works
          </Link>
          <Link
            to="/assistant"
            className="px-8 py-3 rounded-xl bg-white/10 text-white/80 font-semibold text-sm border border-white/15 hover:bg-white/15 hover:scale-105 active:scale-95 transition-all"
          >
            Try the Assistant
          </Link>
        </div>
      </div>
    </section>
  )
}

/* ═════════════════════════════════════════════════════════════════════
   PAGE
   ═════════════════════════════════════════════════════════════════════ */

export default function Platform() {
  return (
    <div className="bg-stone-950 text-white">
      <style>{`
        /* ── Fade in ─────────────────────────────── */
        .pl-fade-in { animation: plFadeIn 0.7s ease both; }
        @keyframes plFadeIn {
          from { opacity: 0; transform: translateY(20px); }
          to   { opacity: 1; transform: translateY(0); }
        }

        /* ── Card pop ────────────────────────────── */
        .pl-card-pop { animation: plCardPop 0.6s ease both; }
        @keyframes plCardPop {
          from { opacity: 0; transform: translateY(16px) scale(0.97); }
          to   { opacity: 1; transform: translateY(0) scale(1); }
        }

        /* ── Side item slide ─────────────────────── */
        .pl-side-item { animation: plSlideIn 0.5s ease both; }
        @keyframes plSlideIn {
          from { opacity: 0; transform: translateX(-12px); }
          to   { opacity: 1; transform: translateX(0); }
        }

        /* ── Timeline step ───────────────────────── */
        .pl-timeline-step { animation: plFadeIn 0.6s ease both; }

        /* ── Edge pulse ──────────────────────────── */
        .pl-edge-active { animation: plEdgePulse 2s ease-in-out infinite; }
        @keyframes plEdgePulse {
          0%, 100% { opacity: 0.2; }
          50%      { opacity: 0.5; }
        }
      `}</style>

      <HeroSection />
      <ClosedLoopSection />
      <ThreeSidesSection />
      <TimelineSection />
      <FinancingSection />
      <OracleSection />
      <MoatSection />
      <StatsSection />
      <CTASection />
    </div>
  )
}
