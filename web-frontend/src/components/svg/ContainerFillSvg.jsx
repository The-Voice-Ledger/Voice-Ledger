/**
 * ContainerFillSvg — an SVG container/box that fills from bottom to top
 * with a gentle wave effect.  Replaces the plain `<div>` progress bar
 * in the Marketplace pool cards.
 *
 * Usage:
 *   <ContainerFillSvg pct={65} />
 */

function fillColor(pct) {
  if (pct >= 80) return { wave: '#22c55e', bg: '#dcfce7' }  // green
  if (pct >= 50) return { wave: '#eab308', bg: '#fef9c3' }  // yellow
  return { wave: '#3b82f6', bg: '#dbeafe' }                  // blue
}

export default function ContainerFillSvg({ pct = 0, height = 48 }) {
  const p = Math.max(0, Math.min(pct, 100))
  const { wave, bg } = fillColor(p)

  // The box is 60 wide, `height` tall in viewBox coords
  const viewW = 60
  const viewH = height
  const fillH = (p / 100) * (viewH - 6) // max fill minus top margin
  const waveY = viewH - 3 - fillH        // top of liquid

  return (
    <div className="w-full" style={{ height }} title={`${pct}% filled`}>
      <svg viewBox={`0 0 ${viewW} ${viewH}`} className="w-full h-full" preserveAspectRatio="none" aria-hidden="true">
        {/* Container outline */}
        <rect x="1" y="1" width={viewW - 2} height={viewH - 2} rx="3" fill={bg} stroke="#d6d3d1" strokeWidth="1" />

        {/* Liquid fill */}
        {p > 0 && (
          <g clipPath="url(#cfClip)">
            {/* Wave path */}
            <path
              d={`
                M 0 ${waveY}
                Q ${viewW * 0.25} ${waveY - 3} ${viewW * 0.5} ${waveY}
                Q ${viewW * 0.75} ${waveY + 3} ${viewW} ${waveY}
                L ${viewW} ${viewH}
                L 0 ${viewH}
                Z
              `}
              fill={wave}
              opacity="0.6"
              className="cf-wave"
            />
            {/* Second wave for depth */}
            <path
              d={`
                M 0 ${waveY + 1.5}
                Q ${viewW * 0.3} ${waveY + 4} ${viewW * 0.55} ${waveY + 1}
                Q ${viewW * 0.8} ${waveY - 2} ${viewW} ${waveY + 1.5}
                L ${viewW} ${viewH}
                L 0 ${viewH}
                Z
              `}
              fill={wave}
              opacity="0.35"
              className="cf-wave cf-wave-2"
            />
          </g>
        )}

        {/* Clip to container shape */}
        <defs>
          <clipPath id="cfClip">
            <rect x="2" y="2" width={viewW - 4} height={viewH - 4} rx="2" />
          </clipPath>
        </defs>
      </svg>

      <style>{`
        .cf-wave {
          animation: cfWobble 3s ease-in-out infinite;
        }
        .cf-wave-2 {
          animation-delay: 0.8s;
          animation-direction: reverse;
        }
        @keyframes cfWobble {
          0%, 100% { transform: translateX(0); }
          50%      { transform: translateX(3px); }
        }
      `}</style>
    </div>
  )
}
