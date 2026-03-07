/**
 * Animated SVG supply-chain journey map.
 *
 * 6 nodes connected by a curved path with a travelling bean dot.
 * Each node lights up sequentially; a tech label fades in below it.
 * Pure CSS animations - zero JS runtime, zero external deps.
 */

import { useTranslation } from 'react-i18next'

/* ── Node data ──────────────────────────────────────────────────── */

const NODES = [
  { id: 'farm',    cx: 60,  label: 'sc_farm',    tech: 'sc_farm_tech',    icon: 'M12 22c-4.97 0-9-2.69-9-6V8m18 8v8c0 3.31-4.03 6-9 6M3 8c0-3.31 4.03-6 9-6s9 2.69 9 6-4.03 6-9 6S3 11.31 3 8z' },
  { id: 'process', cx: 220, label: 'sc_process',  tech: 'sc_process_tech', icon: 'M21 16V8a2 2 0 00-1-1.73l-7-4a2 2 0 00-2 0l-7 4A2 2 0 003 8v8a2 2 0 001 1.73l7 4a2 2 0 002 0l7-4A2 2 0 0021 16z' },
  { id: 'export',  cx: 380, label: 'sc_export',   tech: 'sc_export_tech',  icon: 'M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8l-6-6zM14 2v6h6M9 15l3-3 3 3' },
  { id: 'ship',    cx: 540, label: 'sc_ship',     tech: 'sc_ship_tech',    icon: 'M2 21l.6-3H5l2-9h13l1 5H8.4M5 18h14M7 21a1 1 0 100-2 1 1 0 000 2zM17 21a1 1 0 100-2 1 1 0 000 2z' },
  { id: 'import',  cx: 700, label: 'sc_import',   tech: 'sc_import_tech',  icon: 'M9 11l3 3 3-3M12 2v12M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1' },
  { id: 'buyer',   cx: 860, label: 'sc_buyer',    tech: 'sc_buyer_tech',   icon: 'M17 21v-2a4 4 0 00-4-4H5a4 4 0 00-4 4v2M9 7a4 4 0 100-8 4 4 0 000 8zM23 21v-2a4 4 0 00-3-3.87M16 3.13a4 4 0 010 7.75' },
]

const TOTAL_NODES = NODES.length
const ANIM_STEP   = 1.6  // seconds per node
const TOTAL_DUR   = TOTAL_NODES * ANIM_STEP

/* ── Component ──────────────────────────────────────────────────── */

export default function SupplyChainJourney() {
  const { t } = useTranslation()

  const nodeY = 60
  const viewW = 920
  const viewH = 160

  // Build a smooth curve through all node cx positions
  const pathPoints = NODES.map((n) => [n.cx, nodeY])
  let pathD = `M ${pathPoints[0][0]} ${pathPoints[0][1]}`
  for (let i = 1; i < pathPoints.length; i++) {
    const [px, py] = pathPoints[i - 1]
    const [nx, ny] = pathPoints[i]
    const cpx1 = px + (nx - px) * 0.45
    const cpx2 = nx - (nx - px) * 0.45
    // gentle arc
    const cpy1 = py - 14
    const cpy2 = ny - 14
    pathD += ` C ${cpx1} ${cpy1}, ${cpx2} ${cpy2}, ${nx} ${ny}`
  }

  return (
    <section className="w-full overflow-hidden bg-stone-50/60 border-y border-stone-200/60 py-10 sm:py-14">
      <div className="max-w-5xl mx-auto px-4 sm:px-6">
        <p className="text-center text-[10px] text-stone-400 uppercase tracking-[0.25em] mb-8">
          {t('sc_heading')}
        </p>

        {/* ---- SVG Journey ---- */}
        <div className="sc-journey-wrap">
          <svg
            viewBox={`0 0 ${viewW} ${viewH}`}
            className="w-full h-auto"
            aria-hidden="true"
          >
            {/* Path behind nodes */}
            <path
              d={pathD}
              fill="none"
              stroke="#d6d3d1"
              strokeWidth="2"
              strokeDasharray="6 4"
              className="sc-path-bg"
            />

            {/* Animated glow path */}
            <path
              d={pathD}
              fill="none"
              stroke="url(#scGrad)"
              strokeWidth="2.5"
              strokeLinecap="round"
              className="sc-path-glow"
            />

            {/* Travelling dot */}
            <circle r="5" fill="#292524" className="sc-dot">
              <animateMotion
                dur={`${TOTAL_DUR}s`}
                repeatCount="indefinite"
                path={pathD}
                keyTimes={NODES.map((_, i) => (i / (TOTAL_NODES - 1)).toFixed(4)).join(';')}
                keySplines={Array(TOTAL_NODES - 1).fill('0.42 0 0.58 1').join(';')}
                calcMode="spline"
              />
            </circle>

            {/* Gradient defs */}
            <defs>
              <linearGradient id="scGrad" x1="0" y1="0" x2="1" y2="0">
                <stop offset="0%" stopColor="#292524" />
                <stop offset="50%" stopColor="#78716c" />
                <stop offset="100%" stopColor="#292524" />
              </linearGradient>
            </defs>

            {/* ── Nodes ── */}
            {NODES.map((n, i) => {
              const delay = i * ANIM_STEP
              return (
                <g key={n.id} className="sc-node" style={{ animationDelay: `${delay}s` }}>
                  {/* Outer ring pulse */}
                  <circle
                    cx={n.cx} cy={nodeY} r="22"
                    fill="none" stroke="#d6d3d1" strokeWidth="1"
                    className="sc-ring"
                    style={{ animationDelay: `${delay}s` }}
                  />

                  {/* Background circle */}
                  <circle
                    cx={n.cx} cy={nodeY} r="18"
                    className="sc-circle"
                    style={{ animationDelay: `${delay}s` }}
                  />

                  {/* Icon */}
                  <g transform={`translate(${n.cx - 10}, ${nodeY - 10}) scale(0.833)`}>
                    <path
                      d={n.icon}
                      fill="none"
                      stroke="currentColor"
                      strokeWidth="1.8"
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      className="sc-icon"
                      style={{ animationDelay: `${delay}s` }}
                    />
                  </g>

                  {/* Label */}
                  <text
                    x={n.cx} y={nodeY + 36}
                    textAnchor="middle"
                    className="sc-label"
                    style={{ animationDelay: `${delay + 0.3}s` }}
                  >
                    {t(n.label)}
                  </text>

                  {/* Tech tag */}
                  <text
                    x={n.cx} y={nodeY + 50}
                    textAnchor="middle"
                    className="sc-tech"
                    style={{ animationDelay: `${delay + 0.5}s` }}
                  >
                    {t(n.tech)}
                  </text>
                </g>
              )
            })}
          </svg>
        </div>
      </div>

      {/* ---- CSS Animations (scoped via class prefix) ---- */}
      <style>{`
        .sc-journey-wrap {
          overflow-x: auto;
          -webkit-overflow-scrolling: touch;
          padding-bottom: 4px;
        }
        .sc-journey-wrap svg { min-width: 680px; }

        /* Path glow reveal */
        .sc-path-glow {
          stroke-dasharray: 900;
          stroke-dashoffset: 900;
          animation: scRevealPath ${TOTAL_DUR}s ease-in-out infinite;
        }
        @keyframes scRevealPath {
          0%   { stroke-dashoffset: 900; }
          90%  { stroke-dashoffset: 0; }
          100% { stroke-dashoffset: 0; }
        }

        /* Node circle */
        .sc-circle {
          fill: #fafaf9;
          stroke: #d6d3d1;
          stroke-width: 1.5;
          transition: fill 0.4s, stroke 0.4s;
          animation: scCirclePop ${TOTAL_DUR}s ease-in-out infinite;
        }
        @keyframes scCirclePop {
          0%, 100% { fill: #fafaf9; stroke: #d6d3d1; }
          ${(100 / TOTAL_DUR * ANIM_STEP * 0.3).toFixed(1)}% { fill: #292524; stroke: #292524; }
          ${(100 / TOTAL_DUR * ANIM_STEP * 0.8).toFixed(1)}% { fill: #fafaf9; stroke: #d6d3d1; }
        }

        /* Ring pulse */
        .sc-ring {
          opacity: 0;
          animation: scRingPulse ${TOTAL_DUR}s ease-out infinite;
        }
        @keyframes scRingPulse {
          0%, 100% { r: 22; opacity: 0; }
          5%  { r: 22; opacity: 0.6; }
          18% { r: 32; opacity: 0; }
        }

        /* Icon colour flip */
        .sc-icon {
          color: #78716c;
          animation: scIconFlip ${TOTAL_DUR}s ease-in-out infinite;
        }
        @keyframes scIconFlip {
          0%, 100% { color: #78716c; }
          ${(100 / TOTAL_DUR * ANIM_STEP * 0.3).toFixed(1)}% { color: white; }
          ${(100 / TOTAL_DUR * ANIM_STEP * 0.8).toFixed(1)}% { color: #78716c; }
        }

        /* Labels */
        .sc-label {
          font-size: 11px;
          font-weight: 600;
          fill: #44403c;
          opacity: 0;
          animation: scFadeIn ${TOTAL_DUR}s ease-in-out infinite;
        }
        .sc-tech {
          font-size: 8.5px;
          font-weight: 500;
          fill: #a8a29e;
          opacity: 0;
          animation: scFadeIn ${TOTAL_DUR}s ease-in-out infinite;
        }
        @keyframes scFadeIn {
          0%, 100% { opacity: 0; transform: translateY(3px); }
          8%  { opacity: 1; transform: translateY(0); }
          25% { opacity: 1; transform: translateY(0); }
          33% { opacity: 0; transform: translateY(3px); }
        }

        /* Dot shadow */
        .sc-dot { filter: drop-shadow(0 1px 3px rgba(0,0,0,0.25)); }
      `}</style>
    </section>
  )
}
