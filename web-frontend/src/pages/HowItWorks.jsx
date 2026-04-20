/**
 * About — "Every cherry has a story. Every step has proof."
 *
 * A hybrid of:
 *  • Concept C: First-person coffee-cherry narrative that morphs through
 *    lifecycle stages (cherry → bean → dried → bagged → container → cup)
 *  • Concept B: Living system-blueprint diagram whose nodes illuminate
 *    as each chapter scrolls into view
 *
 * Pure CSS/SVG animations — no Framer Motion or GSAP.
 */

import { useState, useEffect, useRef, useCallback, useMemo } from 'react'
import { Link } from 'react-router-dom'
import ConstellationBg from '../components/svg/ConstellationBg'
import { HexGrid, CircuitTrace, GlowOrb } from '../components/svg/SvgDecorations'

/* ═════════════════════════════════════════════════════════════════════
   DATA
   ═════════════════════════════════════════════════════════════════════ */

const CHAPTERS = [
  {
    id: 'harvest',
    stage: 0,
    title: 'Harvest',
    accent: '#c08e42',
    accentGlow: 'rgba(192,142,66,0.35)',
    narrative:
      'I was picked in Sidama, at 1,800 meters above sea level. Farmer Abebe spoke my details into his phone: my variety, my weight, my origin. His voice became my birth certificate.',
    tech: [
      { label: 'Voice AI', desc: 'Bilingual ASR, English & Amharic' },
      { label: 'Telegram Bot', desc: '37-tool agentic AI assistant' },
      { label: 'AI Agent', desc: 'GPT-4o with function calling' },
    ],
    nodes: ['voice', 'telegram', 'agent'],
  },
  {
    id: 'verification',
    stage: 1,
    title: 'Verification',
    accent: '#258c25',
    accentGlow: 'rgba(37,140,37,0.3)',
    narrative:
      'A cooperative manager cupped me, scored me, and signed a digital credential. No paper. No stamps. A cryptographic proof that I am what they say I am.',
    tech: [
      { label: 'SSI / DIDs', desc: 'W3C Decentralized Identifiers' },
      { label: 'Verifiable Credentials', desc: 'Cooperative-signed batch attestations' },
      { label: 'Role-based Access', desc: '5 user roles, trust hierarchy' },
    ],
    nodes: ['ssi', 'credentials'],
  },
  {
    id: 'traceability',
    stage: 2,
    title: 'Traceability',
    accent: '#3b82f6',
    accentGlow: 'rgba(59,130,246,0.3)',
    narrative:
      'Every hand that touched me, every process I went through (washed, dried, hulled) became an EPCIS event. Each event was hashed, pinned to IPFS, and anchored on Base.',
    tech: [
      { label: 'EPCIS 2.0', desc: 'GS1 supply-chain event standard' },
      { label: 'Blockchain', desc: 'SHA-256 hash anchoring on Base Sepolia' },
      { label: 'IPFS', desc: 'Immutable off-chain storage via Pinata' },
    ],
    nodes: ['epcis', 'blockchain', 'ipfs'],
  },
  {
    id: 'compliance',
    stage: 3,
    title: 'Compliance',
    accent: '#f59e0b',
    accentGlow: 'rgba(245,158,11,0.3)',
    narrative:
      'Satellites looked down at the exact coordinates where I grew. A Chainlink DON attested: no deforestation. I carry my EUDR compliance on-chain. Immutable, auditable, permanent.',
    tech: [
      { label: 'EUDR', desc: 'EU Deforestation Regulation 2023/1115' },
      { label: 'Chainlink CRE', desc: 'DON-attested satellite verification' },
      { label: 'GFW API', desc: 'Global Forest Watch deforestation data' },
    ],
    nodes: ['eudr', 'chainlink'],
  },
  {
    id: 'trade',
    stage: 4,
    title: 'Trade',
    accent: '#8b5cf6',
    accentGlow: 'rgba(139,92,246,0.3)',
    narrative:
      'A buyer in Amsterdam found me on the marketplace. A smart contract held the payment in escrow. A DeFi pool advanced the cooperative\'s funds before I even shipped.',
    tech: [
      { label: 'Marketplace', desc: 'RFQ-based trading with voice commands' },
      { label: 'Smart Contracts', desc: 'Escrow, settlement, fee distribution' },
      { label: 'DeFi Pools', desc: 'ERC-4626 receivables financing' },
    ],
    nodes: ['marketplace', 'contracts', 'defi'],
  },
  {
    id: 'delivery',
    stage: 5,
    title: 'Delivery',
    accent: '#06b6d4',
    accentGlow: 'rgba(6,182,212,0.3)',
    narrative:
      'At the destination, a single scan reveals everything: my origin, my journey, my credentials, my blockchain proof. I am the world\'s most transparent cup of coffee.',
    tech: [
      { label: 'Digital Product Passport', desc: 'Full farm-to-cup traceability' },
      { label: 'QR Verification', desc: 'Public DPP resolution endpoint' },
      { label: 'LiveKit Voice', desc: 'Real-time voice queries on the web' },
    ],
    nodes: ['dpp', 'qr', 'livekit'],
  },
]

/* Blueprint nodes — positioned within a 700×400 viewBox */
const BP_NODES = [
  // Interfaces (top row)
  { id: 'telegram',    x: 100, y: 55,  label: 'Telegram',    abbr: 'TG' },
  { id: 'voice',       x: 240, y: 40,  label: 'Voice AI',    abbr: 'VA' },
  { id: 'agent',       x: 350, y: 80,  label: 'AI Agent',    abbr: 'AI' },
  { id: 'livekit',     x: 470, y: 40,  label: 'LiveKit',     abbr: 'LK' },
  // Identity layer
  { id: 'ssi',         x: 80,  y: 160, label: 'SSI / DIDs',  abbr: 'ID' },
  { id: 'credentials', x: 200, y: 180, label: 'Credentials', abbr: 'VC' },
  // Data layer
  { id: 'epcis',       x: 350, y: 200, label: 'EPCIS',       abbr: 'EP' },
  { id: 'blockchain',  x: 500, y: 170, label: 'Blockchain',  abbr: 'BC' },
  { id: 'ipfs',        x: 620, y: 140, label: 'IPFS',        abbr: 'IP' },
  // Compliance layer
  { id: 'eudr',        x: 120, y: 290, label: 'EUDR',        abbr: 'EU' },
  { id: 'chainlink',   x: 260, y: 310, label: 'Chainlink',   abbr: 'CL' },
  // Commerce layer
  { id: 'marketplace', x: 420, y: 310, label: 'Marketplace',  abbr: 'MK' },
  { id: 'contracts',   x: 540, y: 290, label: 'Contracts',    abbr: 'SC' },
  { id: 'defi',        x: 620, y: 330, label: 'DeFi',         abbr: 'FI' },
  // Output layer
  { id: 'dpp',         x: 350, y: 370, label: 'DPP',          abbr: 'DP' },
  { id: 'qr',          x: 480, y: 380, label: 'QR Codes',     abbr: 'QR' },
]

const BP_EDGES = [
  ['telegram', 'agent'], ['voice', 'agent'], ['livekit', 'agent'],
  ['agent', 'epcis'], ['agent', 'ssi'], ['agent', 'marketplace'],
  ['ssi', 'credentials'], ['credentials', 'epcis'],
  ['epcis', 'blockchain'], ['blockchain', 'ipfs'],
  ['epcis', 'eudr'], ['eudr', 'chainlink'],
  ['chainlink', 'blockchain'],
  ['marketplace', 'contracts'], ['contracts', 'defi'],
  ['contracts', 'blockchain'],
  ['epcis', 'dpp'], ['blockchain', 'dpp'], ['dpp', 'qr'],
  ['credentials', 'dpp'],
]

const STATS = [
  { label: 'Agent tools',       value: 37 },
  { label: 'Smart contracts',   value: 7 },
  { label: 'User interfaces',   value: 5 },
  { label: 'User roles',        value: 5 },
  { label: 'Languages',         value: 2 },
  { label: 'GS1 standards',     value: 3 },
]

/* ═════════════════════════════════════════════════════════════════════
   HOOKS
   ═════════════════════════════════════════════════════════════════════ */

/** Track which chapter sections are in the viewport */
function useVisibleSections(refs) {
  const [visible, setVisible] = useState(new Set())

  useEffect(() => {
    const obs = new IntersectionObserver(
      (entries) => {
        setVisible((prev) => {
          const next = new Set(prev)
          entries.forEach((e) => {
            if (e.isIntersecting) next.add(e.target.dataset.chapter)
            else next.delete(e.target.dataset.chapter)
          })
          return next
        })
      },
      { threshold: 0.35 },
    )
    refs.current.forEach((el) => el && obs.observe(el))
    return () => obs.disconnect()
  }, [refs])

  return visible
}

/** Scroll-reveal: returns true once the element enters the viewport */
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

/** Animate a number counting up from 0 */
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
   SVG ILLUSTRATIONS — Coffee cherry lifecycle
   ═════════════════════════════════════════════════════════════════════ */

function CherryIllustration({ stage, accent }) {
  /* Each stage is a hand-crafted minimal SVG. viewBox 0 0 160 160. */
  const stages = [
    /* 0 — Cherry on branch */
    <g key="cherry">
      <path d="M80 20 Q85 10 95 12 Q100 14 95 24" fill="#258c25" opacity="0.7" />
      <line x1="80" y1="20" x2="80" y2="50" stroke="#4a3520" strokeWidth="2" />
      <ellipse cx="72" cy="72" rx="24" ry="28" fill="#dc2626" opacity="0.9">
        <animate attributeName="ry" values="28;30;28" dur="3s" repeatCount="indefinite" />
      </ellipse>
      <ellipse cx="88" cy="72" rx="24" ry="28" fill="#b91c1c" opacity="0.85">
        <animate attributeName="ry" values="28;30;28" dur="3s" begin="0.3s" repeatCount="indefinite" />
      </ellipse>
      <ellipse cx="67" cy="62" rx="6" ry="4" fill="white" opacity="0.15" />
      <text x="80" y="125" textAnchor="middle" fill={accent} fontSize="10" fontFamily="var(--font-mono)" opacity="0.6">CHERRY</text>
    </g>,
    /* 1 — Green coffee bean */
    <g key="bean">
      <ellipse cx="80" cy="72" rx="30" ry="22" fill="#65a30d" opacity="0.85">
        <animate attributeName="rx" values="30;32;30" dur="4s" repeatCount="indefinite" />
      </ellipse>
      <path d="M80 50 Q78 72 80 94" fill="none" stroke="#3f6212" strokeWidth="1.5" strokeLinecap="round" />
      <ellipse cx="72" cy="65" rx="8" ry="5" fill="white" opacity="0.1" />
      <text x="80" y="125" textAnchor="middle" fill={accent} fontSize="10" fontFamily="var(--font-mono)" opacity="0.6">GREEN BEAN</text>
    </g>,
    /* 2 — Dried/parchment bean */
    <g key="dried">
      <ellipse cx="80" cy="72" rx="28" ry="20" fill="#c08e42" opacity="0.8" />
      <path d="M80 52 Q77 72 80 92" fill="none" stroke="#92630e" strokeWidth="1.5" strokeLinecap="round" />
      {[0, 1, 2, 3].map((i) => (
        <circle key={i} cx={68 + i * 8} cy={72 + (i % 2 ? -3 : 3)} r="1.5" fill="#7c5a1e" opacity="0.4" />
      ))}
      <text x="80" y="125" textAnchor="middle" fill={accent} fontSize="10" fontFamily="var(--font-mono)" opacity="0.6">PARCHMENT</text>
    </g>,
    /* 3 — Bagged (burlap sack) */
    <g key="bagged">
      <path d="M55 50 L50 100 Q65 110 80 112 Q95 110 110 100 L105 50 Q95 45 80 44 Q65 45 55 50Z" fill="#a67428" opacity="0.75" />
      <path d="M62 48 Q80 40 98 48" fill="none" stroke="#7c5a1e" strokeWidth="2" strokeLinecap="round" />
      <line x1="80" y1="38" x2="80" y2="44" stroke="#7c5a1e" strokeWidth="2" />
      <ellipse cx="80" cy="80" rx="12" ry="8" fill="none" stroke="#5c3d10" strokeWidth="1" opacity="0.4" />
      <path d="M80 72 Q78 80 80 88" fill="none" stroke="#5c3d10" strokeWidth="0.8" opacity="0.4" />
      <text x="80" y="130" textAnchor="middle" fill={accent} fontSize="10" fontFamily="var(--font-mono)" opacity="0.6">BAGGED</text>
    </g>,
    /* 4 — Shipping container */
    <g key="container">
      <rect x="40" y="50" width="100" height="55" rx="3" fill="#6d28d9" opacity="0.2" stroke="#8b5cf6" strokeWidth="1" />
      <rect x="42" y="52" width="96" height="51" rx="2" fill="none" stroke="#8b5cf6" strokeWidth="0.5" opacity="0.4" />
      {[0, 1, 2, 3].map((i) => (
        <line key={i} x1={58 + i * 24} y1="52" x2={58 + i * 24} y2="103" stroke="#8b5cf6" strokeWidth="0.5" opacity="0.3" />
      ))}
      <rect x="40" y="105" width="10" height="8" rx="1" fill="#7c3aed" opacity="0.5" />
      <rect x="130" y="105" width="10" height="8" rx="1" fill="#7c3aed" opacity="0.5" />
      <text x="90" y="82" textAnchor="middle" fill="#c4b5fd" fontSize="9" fontFamily="var(--font-mono)" opacity="0.8">COFFEE</text>
      <text x="80" y="130" textAnchor="middle" fill={accent} fontSize="10" fontFamily="var(--font-mono)" opacity="0.6">SHIPPED</text>
    </g>,
    /* 5 — Coffee cup */
    <g key="cup">
      <path d="M55 60 L60 105 Q70 115 80 116 Q90 115 100 105 L105 60Z" fill="#164e63" opacity="0.7" />
      <ellipse cx="80" cy="60" rx="25" ry="8" fill="#155e75" opacity="0.8" />
      <ellipse cx="80" cy="60" rx="20" ry="5" fill="#083344" opacity="0.5" />
      <path d="M105 70 Q120 72 118 85 Q116 98 105 95" fill="none" stroke="#06b6d4" strokeWidth="1.5" opacity="0.5" />
      {/* Steam wisps */}
      <path d="M72 48 Q70 38 74 30" fill="none" stroke="white" strokeWidth="1" opacity="0.2">
        <animate attributeName="d" values="M72 48 Q70 38 74 30;M72 48 Q68 35 75 28;M72 48 Q70 38 74 30" dur="3s" repeatCount="indefinite" />
      </path>
      <path d="M80 46 Q82 34 78 26" fill="none" stroke="white" strokeWidth="1" opacity="0.15">
        <animate attributeName="d" values="M80 46 Q82 34 78 26;M80 46 Q84 32 77 24;M80 46 Q82 34 78 26" dur="3.5s" repeatCount="indefinite" />
      </path>
      <path d="M88 48 Q90 36 86 28" fill="none" stroke="white" strokeWidth="1" opacity="0.2">
        <animate attributeName="d" values="M88 48 Q90 36 86 28;M88 48 Q92 34 85 26;M88 48 Q90 36 86 28" dur="4s" repeatCount="indefinite" />
      </path>
      <text x="80" y="135" textAnchor="middle" fill={accent} fontSize="10" fontFamily="var(--font-mono)" opacity="0.6">DELIVERED</text>
    </g>,
  ]
  return (
    <svg viewBox="0 0 160 160" className="w-40 h-40 md:w-52 md:h-52 shrink-0 drop-shadow-lg ab-cherry-morph">
      {stages[stage]}
    </svg>
  )
}

/* ═════════════════════════════════════════════════════════════════════
   SYSTEM BLUEPRINT
   ═════════════════════════════════════════════════════════════════════ */

function BlueprintDiagram({ activeNodes, interactive = false }) {
  const [hovered, setHovered] = useState(null)
  const nodeMap = useMemo(() => Object.fromEntries(BP_NODES.map((n) => [n.id, n])), [])
  const allActive = activeNodes === 'all'

  return (
    <svg viewBox="0 -50 700 480" className="w-full max-w-2xl mx-auto" style={{ overflow: 'visible', filter: 'drop-shadow(0 0 30px rgba(16,185,129,0.06))' }}>
      <defs>
        <filter id="bp-glow">
          <feGaussianBlur stdDeviation="4" result="blur" />
          <feMerge><feMergeNode in="blur" /><feMergeNode in="SourceGraphic" /></feMerge>
        </filter>
      </defs>

      {/* Edges */}
      {BP_EDGES.map(([a, b], i) => {
        const na = nodeMap[a], nb = nodeMap[b]
        if (!na || !nb) return null
        const isActive = allActive || (activeNodes.has(a) && activeNodes.has(b))
        const isHoverEdge = interactive && (hovered === a || hovered === b)
        return (
          <line
            key={`e${i}`}
            x1={na.x} y1={na.y} x2={nb.x} y2={nb.y}
            stroke={isActive || isHoverEdge ? '#10B981' : '#44403c'}
            strokeWidth={isActive || isHoverEdge ? 1.2 : 0.6}
            opacity={isActive ? 0.6 : isHoverEdge ? 0.5 : 0.15}
            strokeDasharray={isActive ? 'none' : '4 6'}
            className={isActive ? 'ab-edge-active' : ''}
            style={isActive ? { animationDelay: `${i * 0.15}s` } : {}}
          />
        )
      })}

      {/* Data-pulse dots on active edges */}
      {BP_EDGES.map(([a, b], i) => {
        const na = nodeMap[a], nb = nodeMap[b]
        if (!na || !nb) return null
        const isActive = allActive || (activeNodes.has(a) && activeNodes.has(b))
        if (!isActive) return null
        return (
          <circle key={`p${i}`} r="2" fill="#10B981" opacity="0.8">
            <animateMotion
              dur={`${2 + (i % 3)}s`}
              repeatCount="indefinite"
              path={`M${na.x},${na.y} L${nb.x},${nb.y}`}
            />
          </circle>
        )
      })}

      {/* Nodes */}
      {BP_NODES.map((node) => {
        const isActive = allActive || activeNodes.has(node.id)
        const isHover = interactive && hovered === node.id
        return (
          <g
            key={node.id}
            onMouseEnter={interactive ? () => setHovered(node.id) : undefined}
            onMouseLeave={interactive ? () => setHovered(null) : undefined}
            style={{ cursor: interactive ? 'pointer' : 'default' }}
          >
            {/* Glow ring */}
            {(isActive || isHover) && (
              <circle cx={node.x} cy={node.y} r="24" fill="none" stroke="#10B981" strokeWidth="0.8" opacity="0.3" filter="url(#bp-glow)">
                <animate attributeName="r" values="24;28;24" dur="2.5s" repeatCount="indefinite" />
                <animate attributeName="opacity" values="0.3;0.1;0.3" dur="2.5s" repeatCount="indefinite" />
              </circle>
            )}
            {/* Node circle */}
            <circle
              cx={node.x} cy={node.y} r="18"
              fill={isActive || isHover ? 'rgba(16,185,129,0.15)' : 'rgba(68,64,60,0.2)'}
              stroke={isActive || isHover ? '#10B981' : '#57534e'}
              strokeWidth={isActive || isHover ? 1.2 : 0.6}
            />
            {/* Abbreviation */}
            <text
              x={node.x} y={node.y + 1}
              textAnchor="middle" dominantBaseline="middle"
              fontSize="9" fontFamily="var(--font-mono)" fontWeight="600"
              fill={isActive || isHover ? '#a7f3d0' : '#78716c'}
            >
              {node.abbr}
            </text>
            {/* Label below */}
            <text
              x={node.x} y={node.y + 32}
              textAnchor="middle" fontSize="8" fontFamily="var(--font-sans)"
              fill={isActive || isHover ? '#d6f0d6' : '#57534e'}
              opacity={isActive || isHover ? 0.8 : 0.4}
            >
              {node.label}
            </text>
            {/* Tooltip on hover — below node if near top */}
            {interactive && isHover && (
              <foreignObject
                x={node.x - 60}
                y={node.y < 120 ? node.y + 38 : node.y - 60}
                width="120"
                height="30"
              >
                <div className="bg-stone-800 text-emerald-300 text-[9px] text-center py-1 px-2 rounded-md border border-emerald-500/20 font-mono">
                  {node.label}
                </div>
              </foreignObject>
            )}
          </g>
        )
      })}
    </svg>
  )
}

/* ═════════════════════════════════════════════════════════════════════
   STAT COUNTER
   ═════════════════════════════════════════════════════════════════════ */

function StatBox({ label, value, active }) {
  const count = useCountUp(value, active)
  return (
    <div className="flex flex-col items-center gap-1">
      <span className="text-3xl md:text-4xl font-bold font-mono text-white/90">{count}</span>
      <span className="text-[11px] text-white/40 tracking-wider uppercase">{label}</span>
    </div>
  )
}

/* ═════════════════════════════════════════════════════════════════════
   PAGE SECTIONS
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
      {/* Ambient layers */}
      <ConstellationBg />
      <HexGrid className="absolute inset-0 text-white" />
      <div className="absolute -top-24 -left-24 w-96 h-96 rounded-full bg-coffee-800/15 blur-3xl animate-float-slow" />
      <div className="absolute top-1/3 -right-32 w-80 h-80 rounded-full bg-forest-700/10 blur-3xl animate-float-slower" />
      <div className="absolute -bottom-16 left-1/3 w-72 h-72 rounded-full bg-amber-400/8 blur-3xl animate-float-slow" style={{ animationDelay: '3s' }} />

      {/* Dim blueprint hint */}
      <div className="absolute inset-0 flex items-center justify-center opacity-[0.04] pointer-events-none">
        <BlueprintDiagram activeNodes={new Set()} />
      </div>

      {/* Content */}
      <div className={`relative z-10 max-w-2xl transition-all duration-1000 ${revealed ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-8'}`}>
        <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-white/5 border border-white/10 mb-8">
          <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse-dot" />
          <span className="text-[11px] text-white/50 font-mono tracking-wider">How It Works</span>
        </div>

        <h1 className="text-4xl md:text-6xl font-bold font-display leading-tight">
          <span className="text-white/90">Every cherry has </span>
          <span className="text-gradient-animated">a story.</span>
        </h1>
        <h2 className="mt-3 text-2xl md:text-3xl font-display text-white/50">
          Every step has proof.
        </h2>
        <p className="mt-6 text-sm md:text-base text-white/35 max-w-lg mx-auto leading-relaxed">
          Follow a single coffee cherry from the highlands of Ethiopia to a cup in Amsterdam.
          At every stage, see the technology that makes the journey trustworthy.
        </p>
      </div>

      {/* Scroll hint */}
      <div className="absolute bottom-8 left-1/2 -translate-x-1/2 flex flex-col items-center gap-2 animate-bounce">
        <span className="text-[10px] text-white/20 tracking-widest uppercase font-mono">Scroll</span>
        <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="white" strokeWidth="1.5" strokeLinecap="round" opacity="0.2">
          <path d="M4 6l4 4 4-4" />
        </svg>
      </div>
    </section>
  )
}

/* ── Chapter Section ────────────────────────────────────────────── */

function ChapterSection({ chapter, index, chapterRefs, visibleSet }) {
  const ref = useRef(null)
  const revealed = useReveal(ref, 0.15)
  const isEven = index % 2 === 0
  const isVisible = visibleSet.has(chapter.id)

  /* Collect all nodes active up to this chapter */
  const cumulativeNodes = useMemo(() => {
    const set = new Set()
    for (let i = 0; i <= index; i++) {
      CHAPTERS[i].nodes.forEach((n) => set.add(n))
    }
    return set
  }, [index])

  return (
    <section
      ref={(el) => { ref.current = el; if (chapterRefs.current) chapterRefs.current[index] = el }}
      data-chapter={chapter.id}
      className="relative min-h-[80vh] flex items-center overflow-hidden"
      style={{ background: index % 2 === 0
        ? 'linear-gradient(135deg, #1c1917 0%, #1c1917 100%)'
        : 'linear-gradient(135deg, #1c1917 0%, #292524 50%, #1c1917 100%)',
      }}
    >
      {/* Accent glow orb */}
      <div
        className="absolute w-72 h-72 rounded-full blur-3xl pointer-events-none animate-float-slow"
        style={{
          backgroundColor: chapter.accentGlow,
          top: '20%',
          [isEven ? 'left' : 'right']: '-8rem',
        }}
      />

      {/* Thread line (vertical connector) */}
      <div className="absolute left-6 md:left-12 top-0 bottom-0 w-px bg-gradient-to-b from-transparent via-white/10 to-transparent" />
      <div
        className="absolute left-5 md:left-11 top-1/2 -translate-y-1/2 w-3 h-3 rounded-full border-2 transition-all duration-700"
        style={{
          borderColor: isVisible ? chapter.accent : '#57534e',
          backgroundColor: isVisible ? chapter.accent : 'transparent',
          boxShadow: isVisible ? `0 0 12px ${chapter.accentGlow}` : 'none',
        }}
      />

      {/* Two-column content */}
      <div className={`relative z-10 w-full max-w-6xl mx-auto px-8 md:px-16 py-16 grid md:grid-cols-2 gap-12 items-center ${revealed ? 'ab-fade-in' : 'opacity-0'}`}>
        {/* Illustration side */}
        <div className={`flex flex-col items-center gap-6 ${isEven ? 'md:order-1' : 'md:order-2'}`}>
          <CherryIllustration stage={chapter.stage} accent={chapter.accent} />
          {/* Mini blueprint showing cumulative active nodes */}
          <div className="w-full max-w-xs opacity-60">
            <BlueprintDiagram activeNodes={isVisible ? cumulativeNodes : new Set()} />
          </div>
        </div>

        {/* Text side */}
        <div className={`${isEven ? 'md:order-2' : 'md:order-1'}`}>
          {/* Chapter number + title */}
          <div className="flex items-center gap-3 mb-4">
            <span
              className="w-8 h-8 rounded-lg flex items-center justify-center text-xs font-bold font-mono"
              style={{ backgroundColor: `${chapter.accent}20`, color: chapter.accent }}
            >
              {String(index + 1).padStart(2, '0')}
            </span>
            <h3 className="text-2xl md:text-3xl font-display font-bold text-white/90">{chapter.title}</h3>
          </div>

          {/* Narrative */}
          <blockquote className="text-base md:text-lg text-white/55 leading-relaxed italic border-l-2 pl-4 mb-8" style={{ borderColor: `${chapter.accent}40` }}>
            "{chapter.narrative}"
          </blockquote>

          {/* Tech badges */}
          <div className="space-y-3">
            {chapter.tech.map((t, ti) => (
              <div
                key={ti}
                className="flex items-start gap-3 ab-tech-badge"
                style={{ animationDelay: `${ti * 0.15}s` }}
              >
                <div
                  className="mt-1 w-2 h-2 rounded-full shrink-0"
                  style={{ backgroundColor: chapter.accent }}
                />
                <div>
                  <span className="text-sm font-semibold text-white/75">{t.label}</span>
                  <span className="text-xs text-white/30 ml-2">{t.desc}</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </section>
  )
}

/* ── Full Interactive Blueprint ─────────────────────────────────── */

function BlueprintFullSection() {
  const ref = useRef(null)
  const revealed = useReveal(ref, 0.15)
  return (
    <section
      ref={ref}
      className="relative py-24 px-6 overflow-hidden"
      style={{ background: 'linear-gradient(180deg, #1c1917 0%, #0c0a09 50%, #1c1917 100%)' }}
    >
      <div className="absolute inset-0 opacity-[0.03]">
        <ConstellationBg />
      </div>

      <div className={`relative z-10 max-w-4xl mx-auto text-center transition-all duration-1000 ${revealed ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-8'}`}>
        <span className="text-[11px] text-emerald-400/50 font-mono tracking-widest uppercase">System Architecture</span>
        <h2 className="mt-2 text-3xl md:text-4xl font-display font-bold text-white/90">
          The Living Blueprint
        </h2>
        <p className="mt-3 text-sm text-white/35 max-w-md mx-auto">
          Every node is a running system. Every line carries data.
          Hover to explore how they connect.
        </p>

        <div className="mt-12">
          <BlueprintDiagram activeNodes="all" interactive />
        </div>
      </div>
    </section>
  )
}

/* ── Interface Showcase ─────────────────────────────────────────── */

const INTERFACES = [
  {
    name: 'Telegram Bot',
    desc: '37 voice-activated tools. Speak in English or Amharic. Every response as text + voice note.',
    icon: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" className="w-6 h-6">
        <path d="M21 5L2 12.5l7 1.5M21 5l-7 13.5-5-6.5M21 5l-12 8" />
      </svg>
    ),
    accent: '#3b82f6',
  },
  {
    name: 'Web Voice Agent',
    desc: 'Real-time conversation powered by LiveKit. Visual action cards for data queries and passports.',
    icon: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" className="w-6 h-6">
        <rect x="9" y="2" width="6" height="11" rx="3" />
        <path d="M5 10a7 7 0 0014 0" />
        <line x1="12" y1="19" x2="12" y2="23" />
      </svg>
    ),
    accent: '#06b6d4',
  },
  {
    name: 'Mini Apps',
    desc: 'Five embedded web apps inside Telegram: batches, marketplace, traceability, profile, admin.',
    icon: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" className="w-6 h-6">
        <rect x="3" y="3" width="7" height="7" rx="1.5" />
        <rect x="14" y="3" width="7" height="7" rx="1.5" />
        <rect x="3" y="14" width="7" height="7" rx="1.5" />
        <rect x="14" y="14" width="7" height="7" rx="1.5" />
      </svg>
    ),
    accent: '#8b5cf6',
  },
  {
    name: 'DPP Viewer',
    desc: 'Full Digital Product Passport rendered from QR scan. Origin, compliance, blockchain proof.',
    icon: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" className="w-6 h-6">
        <rect x="4" y="2" width="16" height="20" rx="2" />
        <path d="M8 6h8M8 10h8M8 14h5" />
      </svg>
    ),
    accent: '#10b981',
  },
  {
    name: 'Web Dashboard',
    desc: 'Marketplace, compliance checker, financing pools, shipment tracking. All in one SPA.',
    icon: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" className="w-6 h-6">
        <rect x="3" y="3" width="18" height="18" rx="2" />
        <line x1="3" y1="9" x2="21" y2="9" />
        <line x1="9" y1="9" x2="9" y2="21" />
      </svg>
    ),
    accent: '#f59e0b',
  },
]

function InterfaceSection() {
  const ref = useRef(null)
  const revealed = useReveal(ref, 0.15)
  return (
    <section
      ref={ref}
      className="relative py-24 px-6 overflow-hidden"
      style={{ background: 'linear-gradient(180deg, #1c1917 0%, #292524 50%, #1c1917 100%)' }}
    >
      <div className={`relative z-10 max-w-5xl mx-auto transition-all duration-1000 ${revealed ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-8'}`}>
        <div className="text-center mb-12">
          <span className="text-[11px] text-cyan-400/50 font-mono tracking-widest uppercase">5 Interfaces</span>
          <h2 className="mt-2 text-3xl md:text-4xl font-display font-bold text-white/90">
            Speak to the supply chain
          </h2>
          <p className="mt-3 text-sm text-white/35 max-w-md mx-auto">
            Every user has their preferred way in. Every interface speaks the same truth.
          </p>
        </div>

        <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {INTERFACES.map((iface, i) => (
            <div
              key={i}
              className="group relative rounded-2xl p-5 transition-all duration-300 hover:scale-[1.02] ab-interface-card"
              style={{
                background: 'rgba(255,255,255,0.03)',
                border: '1px solid rgba(255,255,255,0.06)',
                animationDelay: `${i * 0.1}s`,
              }}
            >
              <div
                className="absolute inset-0 rounded-2xl opacity-0 group-hover:opacity-100 transition-opacity duration-500 pointer-events-none"
                style={{ background: `radial-gradient(circle at 30% 30%, ${iface.accent}10, transparent 70%)` }}
              />
              <div className="relative z-10">
                <div className="flex items-center gap-3 mb-3">
                  <div
                    className="w-9 h-9 rounded-lg flex items-center justify-center"
                    style={{ backgroundColor: `${iface.accent}15`, color: iface.accent }}
                  >
                    {iface.icon}
                  </div>
                  <span className="text-sm font-semibold text-white/80">{iface.name}</span>
                </div>
                <p className="text-xs text-white/35 leading-relaxed">{iface.desc}</p>
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  )
}

/* ── Numbers Section ────────────────────────────────────────────── */

function NumbersSection() {
  const ref = useRef(null)
  const revealed = useReveal(ref, 0.2)
  return (
    <section
      ref={ref}
      className="relative py-20 px-6"
      style={{ background: 'linear-gradient(180deg, #1c1917, #0c0a09)' }}
    >
      <div className={`relative z-10 max-w-4xl mx-auto text-center transition-all duration-1000 ${revealed ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-8'}`}>
        <span className="text-[11px] text-amber-400/50 font-mono tracking-widest uppercase">By The Numbers</span>
        <div className="mt-8 grid grid-cols-3 md:grid-cols-6 gap-8">
          {STATS.map((s, i) => (
            <StatBox key={i} label={s.label} value={s.value} active={revealed} />
          ))}
        </div>
      </div>
    </section>
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
          Start with your voice
        </h2>
        <p className="mt-4 text-sm text-white/50 max-w-md mx-auto leading-relaxed">
          Whether you're a farmer in Sidama or a buyer in Amsterdam, the interface is the same. Speak, and the ledger listens.
        </p>
        <div className="mt-8 flex flex-col sm:flex-row items-center justify-center gap-4">
          <Link
            to="/assistant"
            className="px-8 py-3 rounded-xl bg-white text-stone-900 font-semibold text-sm hover:bg-white/90 hover:scale-105 active:scale-95 transition-all shadow-lg shadow-black/20"
          >
            Try the Voice Agent
          </Link>
          <a
            href="https://t.me/voice_ledger_bot"
            target="_blank"
            rel="noopener"
            className="px-8 py-3 rounded-xl bg-white/10 text-white/80 font-semibold text-sm border border-white/15 hover:bg-white/15 hover:scale-105 active:scale-95 transition-all"
          >
            Open Telegram Bot
          </a>
        </div>
      </div>
    </section>
  )
}

/* ═════════════════════════════════════════════════════════════════════
   PAGE
   ═════════════════════════════════════════════════════════════════════ */

export default function HowItWorks() {
  const chapterRefs = useRef([])
  const visibleSet = useVisibleSections(chapterRefs)

  return (
    <div className="bg-stone-950 text-white">
      {/* Inline keyframes */}
      <style>{`
        /* ── Cherry morph cross-fade ─────────────────── */
        .ab-cherry-morph g { animation: abFadeIn 0.8s ease both; }

        /* ── Chapter fade-in ─────────────────────────── */
        .ab-fade-in { animation: abFadeIn 0.9s ease both; }

        @keyframes abFadeIn {
          from { opacity: 0; transform: translateY(24px); }
          to   { opacity: 1; transform: translateY(0); }
        }

        /* ── Tech badge staggered entry ──────────────── */
        .ab-tech-badge {
          animation: abSlideIn 0.5s ease both;
        }
        @keyframes abSlideIn {
          from { opacity: 0; transform: translateX(-12px); }
          to   { opacity: 1; transform: translateX(0); }
        }

        /* ── Blueprint edge pulse ────────────────────── */
        .ab-edge-active {
          animation: abEdgePulse 2s ease-in-out infinite;
        }
        @keyframes abEdgePulse {
          0%, 100% { opacity: 0.4; }
          50%      { opacity: 0.7; }
        }

        /* ── Interface card entry ────────────────────── */
        .ab-interface-card {
          animation: abCardPop 0.6s ease both;
        }
        @keyframes abCardPop {
          from { opacity: 0; transform: translateY(16px) scale(0.97); }
          to   { opacity: 1; transform: translateY(0) scale(1); }
        }

        /* ── Progress thread glow ────────────────────── */
        .ab-thread-dot {
          box-shadow: 0 0 8px 2px currentColor;
        }
      `}</style>

      <HeroSection />

      {CHAPTERS.map((ch, i) => (
        <ChapterSection
          key={ch.id}
          chapter={ch}
          index={i}
          chapterRefs={chapterRefs}
          visibleSet={visibleSet}
        />
      ))}

      <BlueprintFullSection />
      <InterfaceSection />
      <NumbersSection />
      <CTASection />
    </div>
  )
}
