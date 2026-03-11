/**
 * AnimatedTimeline — draws an SVG line between milestones with
 * a stroke-dashoffset reveal animation, and pulses the current step.
 *
 * Drop-in replacement for the static CSS `border-left` approach.
 * Render this as the left "rail" inside the existing timeline layout.
 *
 * Usage:
 *   <AnimatedTimeline count={allEvents.length} currentIndex={lastCompletedIndex} />
 *
 * The component renders an absolutely-positioned SVG rail that aligns
 * with the existing pl-8 / -left-8 icon layout in Tracking.jsx.
 */

export default function AnimatedTimeline({ count = 0, currentIndex = -1 }) {
  if (count < 2) return null

  const stepH = 56        // approx px between event centers (matches space-y-6 + icon size)
  const totalH = (count - 1) * stepH
  const completedH = currentIndex >= 0 ? Math.min(currentIndex, count - 1) * stepH : 0

  return (
    <div
      className="absolute left-3.5 top-2 pointer-events-none"
      style={{ height: totalH + 4 }}
      aria-hidden="true"
    >
      <svg
        width="2"
        height={totalH + 4}
        viewBox={`0 0 2 ${totalH + 4}`}
        className="overflow-visible"
      >
        {/* Background dashed line */}
        <line
          x1="1" y1="0" x2="1" y2={totalH}
          stroke="#d6d3d1"
          strokeWidth="1.5"
          strokeDasharray="4 3"
        />

        {/* Animated solid completed line */}
        {completedH > 0 && (
          <line
            x1="1" y1="0" x2="1" y2={completedH}
            stroke="#22c55e"
            strokeWidth="2"
            strokeLinecap="round"
            className="at-completed"
            style={{ '--at-len': completedH }}
          />
        )}

        {/* Pulsing dot at current position */}
        {currentIndex >= 0 && (
          <g transform={`translate(1, ${currentIndex * stepH})`}>
            <circle r="5" fill="#22c55e" opacity="0.2" className="at-pulse" />
            <circle r="3" fill="#22c55e" opacity="0.5" className="at-pulse" style={{ animationDelay: '0.3s' }} />
          </g>
        )}
      </svg>

      <style>{`
        .at-completed {
          stroke-dasharray: var(--at-len);
          stroke-dashoffset: var(--at-len);
          animation: atDraw 1.2s ease-out 0.3s forwards;
        }
        @keyframes atDraw {
          to { stroke-dashoffset: 0; }
        }
        .at-pulse {
          transform-origin: center;
          animation: atPulse 2s ease-in-out infinite;
        }
        @keyframes atPulse {
          0%, 100% { r: 4; opacity: 0.3; }
          50%      { r: 7; opacity: 0; }
        }
      `}</style>
    </div>
  )
}
