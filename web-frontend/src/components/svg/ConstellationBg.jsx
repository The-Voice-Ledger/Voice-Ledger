/**
 * ConstellationBg — a subtle animated "tech network" constellation
 * pattern rendered as SVG behind hero content.
 *
 * Small dots connected by faint lines that slowly drift.
 * Rendered at very low opacity so it never competes with text.
 * Pure SVG + CSS, no canvas, no JS runtime.
 *
 * Usage:
 *   <ConstellationBg />   (renders inside a position:relative parent)
 */

/* ── Static node positions (hand-tuned for visual balance) ────── */
const NODES = [
  { x: 80,  y: 40 },
  { x: 200, y: 25 },
  { x: 350, y: 60 },
  { x: 500, y: 30 },
  { x: 650, y: 55 },
  { x: 780, y: 35 },
  { x: 130, y: 90 },
  { x: 280, y: 100 },
  { x: 420, y: 85 },
  { x: 580, y: 95 },
  { x: 720, y: 80 },
  { x: 50,  y: 130 },
  { x: 180, y: 145 },
  { x: 460, y: 140 },
  { x: 620, y: 130 },
  { x: 800, y: 120 },
]

/* Edges: pairs of node indices to connect */
const EDGES = [
  [0, 1], [1, 2], [2, 3], [3, 4], [4, 5],
  [0, 6], [6, 7], [7, 8], [8, 9], [9, 10],
  [1, 7], [3, 8], [5, 10],
  [6, 11], [11, 12], [12, 13], [13, 14], [14, 15],
  [7, 12], [9, 14],
  [2, 8], [4, 9],
]

export default function ConstellationBg() {
  return (
    <div className="absolute inset-0 overflow-hidden pointer-events-none" aria-hidden="true">
      <svg
        viewBox="0 0 860 170"
        preserveAspectRatio="xMidYMid slice"
        className="w-full h-full opacity-[0.06]"
      >
        {/* Edges */}
        {EDGES.map(([a, b], i) => (
          <line
            key={`e${i}`}
            x1={NODES[a].x} y1={NODES[a].y}
            x2={NODES[b].x} y2={NODES[b].y}
            stroke="white"
            strokeWidth="0.8"
            className="cn-edge"
            style={{ animationDelay: `${i * 0.3}s` }}
          />
        ))}

        {/* Nodes */}
        {NODES.map((n, i) => (
          <g key={`n${i}`}>
            <circle
              cx={n.x} cy={n.y} r="2"
              fill="white"
              className="cn-node"
              style={{ animationDelay: `${i * 0.4}s` }}
            />
            {/* Outer glow ring on some nodes */}
            {i % 3 === 0 && (
              <circle
                cx={n.x} cy={n.y} r="5"
                fill="none" stroke="white" strokeWidth="0.5"
                className="cn-glow"
                style={{ animationDelay: `${i * 0.5}s` }}
              />
            )}
          </g>
        ))}
      </svg>

      <style>{`
        .cn-edge {
          opacity: 0.5;
          animation: cnEdgePulse 8s ease-in-out infinite;
        }
        @keyframes cnEdgePulse {
          0%, 100% { opacity: 0.3; }
          50%      { opacity: 0.7; }
        }

        .cn-node {
          animation: cnNodeDrift 10s ease-in-out infinite;
        }
        @keyframes cnNodeDrift {
          0%, 100% { transform: translate(0, 0); }
          33%      { transform: translate(2px, -1.5px); }
          66%      { transform: translate(-1.5px, 2px); }
        }

        .cn-glow {
          opacity: 0;
          animation: cnGlow 4s ease-in-out infinite;
        }
        @keyframes cnGlow {
          0%, 100% { opacity: 0; r: 4; }
          50%      { opacity: 0.5; r: 7; }
        }
      `}</style>
    </div>
  )
}
