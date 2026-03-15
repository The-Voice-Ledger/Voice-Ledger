/**
 * SvgDecorations — reusable decorative background components.
 *
 *  HexGrid       Repeating hexagonal tile pattern (blockchain / honeycomb feel)
 *  CircuitTrace  Horizontal circuit-board traces with junction dots
 *  GlowOrb       Blurred radial-gradient light bloom
 *
 * All three are intended as absolute-positioned background layers
 * beneath relative-positioned content.
 */

/* ── HexGrid ─────────────────────────────────────────────────────── */

export function HexGrid({ className = '' }) {
  return (
    <svg
      className={className}
      width="100%"
      height="100%"
      preserveAspectRatio="none"
      aria-hidden="true"
    >
      <defs>
        <pattern
          id="hex-grid"
          width="56"
          height="100"
          patternUnits="userSpaceOnUse"
          patternTransform="scale(0.8)"
        >
          <path
            d="M28 66L0 50V16L28 0l28 16v34L28 66z
               M28 100L0 84V66l28 16 28-16v18L28 100z"
            fill="none"
            stroke="currentColor"
            strokeWidth="0.8"
            opacity="0.025"
          />
        </pattern>
      </defs>
      <rect width="100%" height="100%" fill="url(#hex-grid)" />
    </svg>
  )
}

/* ── CircuitTrace ────────────────────────────────────────────────── */

export function CircuitTrace({ className = '' }) {
  return (
    <svg
      className={className}
      viewBox="0 0 400 200"
      preserveAspectRatio="none"
      aria-hidden="true"
    >
      {/* Horizontal traces with perpendicular stubs */}
      <g fill="none" stroke="currentColor" strokeWidth="1.2" opacity="0.10">
        {/* Trace 1 */}
        <path d="M0 40 H120 V60 H200 V40 H400" />
        {/* Trace 2 */}
        <path d="M0 100 H80 V80 H160 V100 H280 V120 H400" />
        {/* Trace 3 */}
        <path d="M0 160 H60 V140 H180 V160 H320 V140 H400" />
        {/* Trace 4 (shorter) */}
        <path d="M100 20 V60 H160" />
      </g>
      {/* Junction dots */}
      <g fill="currentColor">
        <circle cx="120" cy="40" r="4" opacity="0.20" />
        <circle cx="200" cy="40" r="2.5" opacity="0.15" />
        <circle cx="80"  cy="100" r="4" opacity="0.20" />
        <circle cx="160" cy="100" r="2.5" opacity="0.15" />
        <circle cx="280" cy="100" r="4" opacity="0.20" />
        <circle cx="60"  cy="160" r="2.5" opacity="0.15" />
        <circle cx="180" cy="160" r="4" opacity="0.20" />
        <circle cx="320" cy="160" r="2.5" opacity="0.15" />
        <circle cx="100" cy="20" r="2.5" opacity="0.15" />
        <circle cx="160" cy="60" r="2.5" opacity="0.15" />
      </g>
    </svg>
  )
}

/* ── GlowOrb ─────────────────────────────────────────────────────── */

export function GlowOrb({ className = '', color = '#ffffff' }) {
  return (
    <div
      className={`pointer-events-none ${className}`}
      aria-hidden="true"
      style={{
        background: `radial-gradient(circle, ${color}30 0%, ${color}10 40%, transparent 70%)`,
        filter: 'blur(60px)',
        borderRadius: '50%',
      }}
    />
  )
}
