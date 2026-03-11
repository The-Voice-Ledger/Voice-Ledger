/**
 * Decorative SVG background for inner-page headers.
 *
 * A subtle, abstract illustration that sits behind the page title.
 * Each variant maps to a page domain (marketplace, compliance, tracking,
 * financing, rfqs).  Pure SVG + CSS — no JS runtime.
 *
 * Usage:
 *   <PageHeroBg variant="compliance" />
 */

const VARIANTS = {
  /* ── Marketplace: overlapping circles like a Venn diagram ─── */
  marketplace: (
    <g opacity="0.55">
      <circle cx="140" cy="60" r="50" fill="none" stroke="currentColor" strokeWidth="0.7" className="phb-orbit" />
      <circle cx="180" cy="55" r="38" fill="none" stroke="currentColor" strokeWidth="0.5" className="phb-orbit" style={{ animationDelay: '1.5s' }} />
      <circle cx="160" cy="80" r="28" fill="none" stroke="currentColor" strokeWidth="0.5" className="phb-orbit" style={{ animationDelay: '3s' }} />
      {/* Handshake paths */}
      <path d="M145 58 Q155 48 165 58" fill="none" stroke="currentColor" strokeWidth="0.8" strokeLinecap="round" className="phb-draw" />
      <path d="M155 58 Q165 48 175 58" fill="none" stroke="currentColor" strokeWidth="0.8" strokeLinecap="round" className="phb-draw" style={{ animationDelay: '0.6s' }} />
      {/* Small dots */}
      <circle cx="120" cy="45" r="1.5" fill="currentColor" className="phb-dot" />
      <circle cx="200" cy="70" r="1.5" fill="currentColor" className="phb-dot" style={{ animationDelay: '1s' }} />
      <circle cx="135" cy="90" r="1" fill="currentColor" className="phb-dot" style={{ animationDelay: '2s' }} />
    </g>
  ),

  /* ── Compliance: shield with check mark + radiating arcs ──── */
  compliance: (
    <g opacity="0.55">
      {/* Shield outline */}
      <path
        d="M160 30 L190 45 L190 75 Q190 100 160 110 Q130 100 130 75 L130 45 Z"
        fill="none" stroke="currentColor" strokeWidth="0.8"
        className="phb-draw"
      />
      {/* Inner check */}
      <path
        d="M148 68 L157 77 L174 56"
        fill="none" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" strokeLinejoin="round"
        className="phb-draw" style={{ animationDelay: '0.8s' }}
      />
      {/* Radiating arcs */}
      <path d="M120 70 Q110 50 125 35" fill="none" stroke="currentColor" strokeWidth="0.5" strokeLinecap="round" className="phb-orbit" />
      <path d="M200 70 Q210 50 195 35" fill="none" stroke="currentColor" strokeWidth="0.5" strokeLinecap="round" className="phb-orbit" style={{ animationDelay: '1.2s' }} />
      <path d="M130 110 Q120 120 115 108" fill="none" stroke="currentColor" strokeWidth="0.4" strokeLinecap="round" className="phb-orbit" style={{ animationDelay: '2.4s' }} />
      {/* Dots */}
      <circle cx="115" cy="42" r="1.5" fill="currentColor" className="phb-dot" />
      <circle cx="205" cy="42" r="1.5" fill="currentColor" className="phb-dot" style={{ animationDelay: '0.8s' }} />
      <circle cx="160" cy="118" r="1" fill="currentColor" className="phb-dot" style={{ animationDelay: '1.6s' }} />
    </g>
  ),

  /* ── Tracking: route line with waypoints ─────────────────── */
  tracking: (
    <g opacity="0.55">
      {/* Route path */}
      <path
        d="M80 80 Q120 30 160 65 Q200 100 240 50"
        fill="none" stroke="currentColor" strokeWidth="0.8" strokeDasharray="4 3"
        className="phb-draw"
      />
      {/* Waypoint circles */}
      <circle cx="80" cy="80" r="4" fill="none" stroke="currentColor" strokeWidth="0.7" className="phb-orbit" />
      <circle cx="160" cy="65" r="4" fill="none" stroke="currentColor" strokeWidth="0.7" className="phb-orbit" style={{ animationDelay: '0.8s' }} />
      <circle cx="240" cy="50" r="4" fill="none" stroke="currentColor" strokeWidth="0.7" className="phb-orbit" style={{ animationDelay: '1.6s' }} />
      {/* Dot centers */}
      <circle cx="80" cy="80" r="1.5" fill="currentColor" className="phb-dot" />
      <circle cx="160" cy="65" r="1.5" fill="currentColor" className="phb-dot" style={{ animationDelay: '0.8s' }} />
      <circle cx="240" cy="50" r="1.5" fill="currentColor" className="phb-dot" style={{ animationDelay: '1.6s' }} />
      {/* Ship silhouette at midpoint */}
      <path d="M155 52 L160 45 L165 52" fill="none" stroke="currentColor" strokeWidth="0.6" strokeLinecap="round" className="phb-draw" style={{ animationDelay: '1.2s' }} />
    </g>
  ),

  /* ── Financing: vault / column + upward graph ────────────── */
  financing: (
    <g opacity="0.55">
      {/* Column/pillar */}
      <rect x="148" y="40" width="24" height="65" rx="2" fill="none" stroke="currentColor" strokeWidth="0.7" className="phb-draw" />
      <path d="M145 40 L160 32 L175 40" fill="none" stroke="currentColor" strokeWidth="0.8" strokeLinejoin="round" className="phb-draw" style={{ animationDelay: '0.3s' }} />
      <line x1="148" y1="105" x2="172" y2="105" stroke="currentColor" strokeWidth="0.8" className="phb-draw" />
      {/* Graph line rising */}
      <polyline
        points="105,95 125,82 145,88 165,65 185,70 205,48 225,38"
        fill="none" stroke="currentColor" strokeWidth="0.7" strokeLinecap="round" strokeLinejoin="round"
        className="phb-draw" style={{ animationDelay: '0.6s' }}
      />
      {/* Graph dots */}
      {[
        [105, 95], [125, 82], [145, 88], [165, 65], [185, 70], [205, 48], [225, 38],
      ].map(([x, y], i) => (
        <circle key={i} cx={x} cy={y} r="1.5" fill="currentColor" className="phb-dot" style={{ animationDelay: `${0.6 + i * 0.15}s` }} />
      ))}
    </g>
  ),

  /* ── RFQs: document with lines ───────────────────────────── */
  rfqs: (
    <g opacity="0.55">
      {/* Document shape */}
      <path
        d="M140 30 L185 30 L195 42 L195 110 L125 110 L125 30 Z"
        fill="none" stroke="currentColor" strokeWidth="0.7"
        className="phb-draw"
      />
      {/* Folded corner */}
      <path d="M185 30 L185 42 L195 42" fill="none" stroke="currentColor" strokeWidth="0.6" className="phb-draw" style={{ animationDelay: '0.4s' }} />
      {/* Text lines */}
      {[50, 62, 74, 86, 98].map((y, i) => (
        <line key={i} x1="135" y1={y} x2={175 - i * 5} y2={y} stroke="currentColor" strokeWidth="0.5" strokeLinecap="round" className="phb-draw" style={{ animationDelay: `${0.6 + i * 0.12}s` }} />
      ))}
      {/* Check marks on first two lines */}
      <path d="M130 48 L133 52 L138 46" fill="none" stroke="currentColor" strokeWidth="0.7" strokeLinecap="round" strokeLinejoin="round" className="phb-draw" style={{ animationDelay: '1.2s' }} />
      <path d="M130 60 L133 64 L138 58" fill="none" stroke="currentColor" strokeWidth="0.7" strokeLinecap="round" strokeLinejoin="round" className="phb-draw" style={{ animationDelay: '1.4s' }} />
    </g>
  ),
}

export default function PageHeroBg({ variant = 'compliance' }) {
  const content = VARIANTS[variant] || VARIANTS.compliance

  return (
    <div className="absolute right-0 top-0 h-full w-48 sm:w-64 pointer-events-none overflow-hidden opacity-[0.12]" aria-hidden="true">
      <svg
        viewBox="0 0 320 130"
        className="w-full h-full text-stone-900"
        preserveAspectRatio="xMidYMid meet"
      >
        {content}
      </svg>

      <style>{`
        /* Draw-in animation for paths */
        .phb-draw {
          stroke-dasharray: 300;
          stroke-dashoffset: 300;
          animation: phbDrawIn 2s ease-out forwards;
        }
        @keyframes phbDrawIn {
          to { stroke-dashoffset: 0; }
        }

        /* Gentle orbit pulse for circles/arcs */
        .phb-orbit {
          animation: phbOrbit 6s ease-in-out infinite;
        }
        @keyframes phbOrbit {
          0%, 100% { opacity: 0.6; transform-origin: center; }
          50%      { opacity: 1; }
        }

        /* Dot fade in */
        .phb-dot {
          opacity: 0;
          animation: phbDotIn 0.5s ease-out forwards;
        }
        @keyframes phbDotIn {
          to { opacity: 0.7; }
        }
      `}</style>
    </div>
  )
}
