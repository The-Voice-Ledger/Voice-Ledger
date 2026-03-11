/**
 * Blockchain verification pulse indicator.
 *
 * Three concentric rings pulse outward from a central check mark,
 * giving a "live network broadcast" feel.  Pure CSS animation.
 *
 * Usage:
 *   <BlockchainPulse />               // default 20px
 *   <BlockchainPulse size={16} />     // smaller inline variant
 */

export default function BlockchainPulse({ size = 20, className = '' }) {
  const s = size
  const half = s / 2
  const r1 = half * 0.35
  const r2 = half * 0.58
  const r3 = half * 0.82

  return (
    <span className={`inline-flex items-center justify-center shrink-0 ${className}`} style={{ width: s, height: s }} title="On-chain verified">
      <svg viewBox={`0 0 ${s} ${s}`} className="w-full h-full" aria-hidden="true">
        {/* Pulsing rings */}
        <circle cx={half} cy={half} r={r3} fill="none" stroke="#22c55e" strokeWidth="0.6" opacity="0" className="bp-ring bp-ring-3" />
        <circle cx={half} cy={half} r={r2} fill="none" stroke="#22c55e" strokeWidth="0.7" opacity="0" className="bp-ring bp-ring-2" />
        <circle cx={half} cy={half} r={r1} fill="none" stroke="#22c55e" strokeWidth="0.8" opacity="0" className="bp-ring bp-ring-1" />

        {/* Center check */}
        <circle cx={half} cy={half} r={half * 0.22} fill="#22c55e" opacity="0.9" />
        <polyline
          points={`${half - s * 0.06},${half} ${half - s * 0.01},${half + s * 0.05} ${half + s * 0.07},${half - s * 0.04}`}
          fill="none"
          stroke="white"
          strokeWidth={s * 0.06}
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      </svg>

      <style>{`
        .bp-ring {
          transform-origin: center;
          animation: bpPulse 2.4s ease-out infinite;
        }
        .bp-ring-1 { animation-delay: 0s; }
        .bp-ring-2 { animation-delay: 0.4s; }
        .bp-ring-3 { animation-delay: 0.8s; }
        @keyframes bpPulse {
          0%  { opacity: 0.7; transform: scale(0.7); }
          60% { opacity: 0; transform: scale(1.2); }
          100% { opacity: 0; transform: scale(1.2); }
        }
      `}</style>
    </span>
  )
}
