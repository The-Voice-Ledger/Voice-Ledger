/**
 * Subtle background decorations for light / white pages.
 *
 *  TopographicBg   Ultra-faint topo contour lines that drift slowly upward.
 *                  Applied globally behind all light pages via App shell.
 *
 *  DotGrid         Evenly-spaced dot pattern evoking ledger / graph paper.
 *                  Used behind the Landing features section.
 */

/* ── TopographicBg ───────────────────────────────────────────────── */

const TOPO_PATHS = [
  // Organic, flowing contour lines at varying vertical offsets
  'M0 120 Q80 90 160 110 T320 95 T480 115 T640 100 T800 90 T960 108 T1120 95 T1280 112',
  'M0 200 Q100 175 200 190 T400 170 T600 195 T800 178 T1000 192 T1200 175 T1280 188',
  'M0 300 Q120 270 240 285 T480 260 T720 290 T960 268 T1200 282 T1280 270',
  'M0 400 Q90 375 180 390 T360 368 T540 395 T720 372 T900 388 T1080 370 T1280 385',
  'M0 510 Q110 485 220 500 T440 478 T660 505 T880 482 T1100 498 T1280 488',
  'M0 620 Q130 595 260 610 T520 590 T780 615 T1040 592 T1280 608',
  'M0 730 Q100 705 200 720 T400 698 T600 725 T800 702 T1000 718 T1280 710',
]

export function TopographicBg({ className = '' }) {
  return (
    <div
      className={`pointer-events-none select-none overflow-hidden ${className}`}
      aria-hidden="true"
    >
      <svg
        className="w-full h-full animate-topo-drift"
        viewBox="0 0 1280 800"
        preserveAspectRatio="xMidYMid slice"
        fill="none"
      >
        {TOPO_PATHS.map((d, i) => (
          <path
            key={i}
            d={d}
            stroke="currentColor"
            strokeWidth="1.2"
            opacity={0.06 + (i % 3) * 0.01}   /* 0.06 – 0.08 range */
            strokeLinecap="round"
          />
        ))}
      </svg>
    </div>
  )
}

/* ── DotGrid ─────────────────────────────────────────────────────── */

export function DotGrid({ className = '' }) {
  return (
    <svg
      className={`pointer-events-none select-none ${className}`}
      width="100%"
      height="100%"
      preserveAspectRatio="none"
      aria-hidden="true"
    >
      <defs>
        <pattern
          id="dot-grid"
          width="24"
          height="24"
          patternUnits="userSpaceOnUse"
        >
          <circle cx="12" cy="12" r="1" fill="currentColor" opacity="0.18" />
        </pattern>
      </defs>
      <rect width="100%" height="100%" fill="url(#dot-grid)" />
    </svg>
  )
}
