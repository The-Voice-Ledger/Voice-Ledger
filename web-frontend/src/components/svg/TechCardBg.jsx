/**
 * TechCardBg – subtle SVG background patterns for cards.
 * Layered as `position: absolute; inset: 0` inside a card with `position: relative; overflow: hidden`.
 *
 * Variants:
 *   circuit  – circuit-board traces with solder pads (supply-chain / infra)
 *   hex      – honeycomb hexagonal mesh  (compliance / security)
 *   dotgrid  – evenly-spaced dots with occasional connecting lines (marketplace)
 *   finance  – ascending bar-chart silhouettes + trend line (financing / DeFi)
 *   chain    – chain-link pattern (blockchain)
 *   shipment – dotted route with waypoints (tracking / shipping)
 */

const VARIANTS = {
  /* ── circuit board ──────────────────────────────────── */
  circuit: (
    <g stroke="currentColor" strokeWidth="0.5" fill="none" opacity="0.35">
      {/* horizontal / vertical traces */}
      <path d="M0 20h30 M30 20v25 M30 45h20 M100 10h-30 M70 10v30 M70 40h-15" />
      <path d="M10 60h25 M35 60v-15 M35 45h20 M90 55h-20 M70 55v15" />
      <path d="M5 80h40 M45 80v-10 M45 70h15 M80 75h-10 M80 75v-20" />
      {/* solder pads */}
      {[[30,20],[30,45],[70,10],[70,40],[35,60],[80,75],[45,70],[10,60],[5,80]].map(([cx,cy],i)=>(
        <circle key={i} cx={cx} cy={cy} r="1.5" fill="currentColor" opacity="0.5" />
      ))}
      {/* IC chip outlines */}
      <rect x="48" y="16" width="10" height="14" rx="1" strokeWidth="0.6" />
      <rect x="80" y="42" width="8" height="10" rx="1" strokeWidth="0.6" />
      {/* IC pins */}
      {[18,21,24,28].map((y,i)=><line key={`a${i}`} x1="46" y1={y} x2="48" y2={y} strokeWidth="0.4" />)}
      {[18,21,24,28].map((y,i)=><line key={`b${i}`} x1="58" y1={y} x2="60" y2={y} strokeWidth="0.4" />)}
    </g>
  ),

  /* ── hexagonal mesh ────────────────────────────────── */
  hex: (() => {
    const hexes = []
    const w = 18, h = 15.588 // hex spacing
    for (let row = 0; row < 7; row++) {
      for (let col = 0; col < 7; col++) {
        const cx = col * w + (row % 2 ? w / 2 : 0)
        const cy = row * h
        const pts = Array.from({ length: 6 }, (_, k) => {
          const a = (Math.PI / 3) * k - Math.PI / 6
          return `${cx + 9 * Math.cos(a)},${cy + 9 * Math.sin(a)}`
        }).join(' ')
        hexes.push(<polygon key={`${row}-${col}`} points={pts} />)
      }
    }
    return (
      <g stroke="currentColor" strokeWidth="0.4" fill="none" opacity="0.25">
        {hexes}
      </g>
    )
  })(),

  /* ── dot-grid with occasional lines ────────────────── */
  dotgrid: (() => {
    const dots = []
    const lines = []
    for (let y = 5; y < 100; y += 12) {
      for (let x = 5; x < 100; x += 12) {
        dots.push(<circle key={`${x}-${y}`} cx={x} cy={y} r="0.8" fill="currentColor" />)
      }
    }
    // A few random connecting lines for network feel
    const pairs = [[5,5,17,17],[29,5,41,17],[53,29,65,41],[77,53,89,65],[17,41,29,53],[65,17,77,29],[41,65,53,77]]
    pairs.forEach(([x1,y1,x2,y2],i) => {
      lines.push(<line key={`l${i}`} x1={x1} y1={y1} x2={x2} y2={y2} stroke="currentColor" strokeWidth="0.3" />)
    })
    return <g opacity="0.22">{dots}{lines}</g>
  })(),

  /* ── finance: bar chart + trend line ───────────────── */
  finance: (
    <g opacity="0.2">
      {/* Ascending bars */}
      {[
        [8, 70, 6, 20],
        [18, 62, 6, 28],
        [28, 55, 6, 35],
        [38, 48, 6, 42],
        [48, 38, 6, 52],
        [58, 42, 6, 48],
        [68, 30, 6, 60],
        [78, 22, 6, 68],
        [88, 28, 6, 62],
      ].map(([x, y, w, h], i) => (
        <rect key={i} x={x} y={y} width={w} height={h} rx="1" fill="currentColor" opacity="0.35" />
      ))}
      {/* Trend line */}
      <polyline
        points="11,68 21,60 31,53 41,46 51,36 61,40 71,28 81,20 91,26"
        stroke="currentColor" strokeWidth="1.2" fill="none" strokeLinecap="round" strokeLinejoin="round"
        opacity="0.5"
      />
      {/* Grid lines */}
      {[30,50,70].map(y=>(
        <line key={y} x1="5" y1={y} x2="95" y2={y} stroke="currentColor" strokeWidth="0.2" strokeDasharray="2 3" />
      ))}
    </g>
  ),

  /* ── chain links ───────────────────────────────────── */
  chain: (() => {
    const links = []
    for (let i = 0; i < 6; i++) {
      const x = 10 + i * 16
      const y = 40 + (i % 2 ? -8 : 8)
      links.push(
        <g key={i} transform={`translate(${x},${y}) rotate(${i % 2 ? 15 : -15})`}>
          <rect x="-5" y="-8" width="10" height="16" rx="5" stroke="currentColor" strokeWidth="0.8" fill="none" />
        </g>
      )
      if (i < 5) {
        const nx = 10 + (i + 1) * 16
        const ny = 40 + ((i+1) % 2 ? -8 : 8)
        links.push(<line key={`c${i}`} x1={x+5} y1={y} x2={nx-5} y2={ny} stroke="currentColor" strokeWidth="0.3" />)
      }
    }
    return <g opacity="0.2">{links}</g>
  })(),

  /* ── shipment route ────────────────────────────────── */
  shipment: (
    <g opacity="0.2">
      {/* Dotted route */}
      <path
        d="M5 75 Q25 55 45 60 Q65 65 75 40 Q85 15 95 25"
        stroke="currentColor" strokeWidth="1" fill="none"
        strokeDasharray="3 4" strokeLinecap="round"
      />
      {/* Waypoint circles */}
      {[[5,75],[45,60],[75,40],[95,25]].map(([cx,cy],i)=>(
        <g key={i}>
          <circle cx={cx} cy={cy} r="3" stroke="currentColor" strokeWidth="0.6" fill="none" />
          <circle cx={cx} cy={cy} r="1" fill="currentColor" />
        </g>
      ))}
      {/* Small ship icon at end */}
      <g transform="translate(90,20) scale(0.5)" stroke="currentColor" strokeWidth="1.2" fill="none">
        <path d="M0 8 L8 8 L10 4 L2 4 Z" />
        <line x1="5" y1="4" x2="5" y2="0" />
      </g>
    </g>
  ),
}

export default function TechCardBg({ variant = 'circuit', className = '' }) {
  const children = VARIANTS[variant] || VARIANTS.circuit

  return (
    <svg
      className={`absolute inset-0 w-full h-full pointer-events-none text-stone-400 ${className}`}
      viewBox="0 0 100 100"
      preserveAspectRatio="xMidYMid slice"
      fill="none"
      aria-hidden="true"
    >
      {children}
    </svg>
  )
}
