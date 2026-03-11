/**
 * ComplianceShield — SVG shield badge for compliance levels.
 *
 * Replaces the plain coloured pill with a shield icon whose fill
 * colour and optional shimmer reflect the compliance tier.
 *
 * Usage:
 *   <ComplianceShield level="Gold" />
 *   <ComplianceShield level="Non-Compliant" />
 */

const SHIELD_THEMES = {
  Gold: {
    fill: '#fbbf24',   // amber-400
    stroke: '#d97706', // amber-600
    text: '#92400e',   // amber-800
    shimmer: true,
  },
  Silver: {
    fill: '#d1d5db',   // gray-300
    stroke: '#9ca3af', // gray-400
    text: '#374151',   // gray-700
    shimmer: false,
  },
  Bronze: {
    fill: '#d4a574',   // warm bronze
    stroke: '#b47b46',
    text: '#78350f',
    shimmer: false,
  },
  'Non-Compliant': {
    fill: '#fca5a5',   // red-300
    stroke: '#ef4444', // red-500
    text: '#991b1b',   // red-800
    shimmer: false,
    slash: true,
  },
  Unknown: {
    fill: '#e7e5e4',   // stone-200
    stroke: '#a8a29e', // stone-400
    text: '#57534e',   // stone-600
    shimmer: false,
  },
}

export default function ComplianceShield({ level, size = 'md' }) {
  const theme = SHIELD_THEMES[level] || SHIELD_THEMES.Unknown
  const displayLevel = level || 'Unknown'
  const isSmall = size === 'sm'
  const h = isSmall ? 20 : 26

  return (
    <span
      className="inline-flex items-center gap-1.5"
      title={`Compliance level: ${displayLevel}`}
    >
      <svg
        viewBox="0 0 24 28"
        style={{ width: h * 0.857, height: h }}
        aria-hidden="true"
        className={theme.shimmer ? 'cs-shimmer' : ''}
      >
        {/* Shield path */}
        <path
          d="M12 1 L22 6 L22 14 Q22 23 12 27 Q2 23 2 14 L2 6 Z"
          fill={theme.fill}
          stroke={theme.stroke}
          strokeWidth="1.2"
        />

        {/* Check for compliant levels */}
        {!theme.slash && (
          <polyline
            points="8,14 11,17 16,11"
            fill="none"
            stroke={theme.stroke}
            strokeWidth="1.8"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        )}

        {/* Slash for non-compliant */}
        {theme.slash && (
          <g>
            <line x1="8" y1="10" x2="16" y2="18" stroke={theme.stroke} strokeWidth="1.8" strokeLinecap="round" />
            <line x1="16" y1="10" x2="8" y2="18" stroke={theme.stroke} strokeWidth="1.8" strokeLinecap="round" />
          </g>
        )}
      </svg>

      <span
        className={`font-semibold ${isSmall ? 'text-[10px]' : 'text-xs'}`}
        style={{ color: theme.text }}
      >
        {displayLevel}
      </span>

      <style>{`
        .cs-shimmer {
          animation: csShimmer 3s ease-in-out infinite;
        }
        @keyframes csShimmer {
          0%, 100% { filter: brightness(1); }
          50%      { filter: brightness(1.15); }
        }
      `}</style>
    </span>
  )
}
