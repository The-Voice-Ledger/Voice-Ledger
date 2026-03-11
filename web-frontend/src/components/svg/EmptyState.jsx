/**
 * Animated empty state with custom SVG illustrations.
 *
 * Usage:
 *   <EmptyState
 *     variant="rfqs"          // rfqs | pools | containers | tracking | compliance | financing
 *     message="No RFQs yet."
 *     sub="Create one via the assistant"
 *     actionLabel="Create RFQ"
 *     actionTo="/assistant"
 *   />
 */

import { Link } from 'react-router-dom'

/* ── Illustration variants (inline SVG, 80×80 viewBox) ──────── */

const ILLUSTRATIONS = {
  /* Empty document / inbox */
  rfqs: (
    <g>
      <rect x="22" y="14" width="36" height="50" rx="3" fill="none" stroke="currentColor" strokeWidth="1.5" />
      <path d="M50 14 L58 24 L50 24 Z" fill="none" stroke="currentColor" strokeWidth="1.2" />
      <line x1="30" y1="30" x2="50" y2="30" stroke="currentColor" strokeWidth="1" strokeLinecap="round" opacity="0.4" />
      <line x1="30" y1="37" x2="46" y2="37" stroke="currentColor" strokeWidth="1" strokeLinecap="round" opacity="0.3" />
      <line x1="30" y1="44" x2="42" y2="44" stroke="currentColor" strokeWidth="1" strokeLinecap="round" opacity="0.2" />
      <circle cx="40" cy="56" r="4" fill="none" stroke="currentColor" strokeWidth="1" opacity="0.3" />
    </g>
  ),

  /* Empty pool (concentric ripples) */
  pools: (
    <g>
      <circle cx="40" cy="40" r="8" fill="none" stroke="currentColor" strokeWidth="1.4" />
      <circle cx="40" cy="40" r="16" fill="none" stroke="currentColor" strokeWidth="1" opacity="0.5" />
      <circle cx="40" cy="40" r="24" fill="none" stroke="currentColor" strokeWidth="0.7" opacity="0.3" />
      <circle cx="40" cy="40" r="32" fill="none" stroke="currentColor" strokeWidth="0.5" opacity="0.15" />
      <circle cx="40" cy="40" r="3" fill="currentColor" opacity="0.3" />
    </g>
  ),

  /* Empty box / container */
  containers: (
    <g>
      <path d="M18 28 L40 16 L62 28 L62 52 L40 64 L18 52 Z" fill="none" stroke="currentColor" strokeWidth="1.3" />
      <path d="M18 28 L40 40 L62 28" fill="none" stroke="currentColor" strokeWidth="1" opacity="0.5" />
      <line x1="40" y1="40" x2="40" y2="64" stroke="currentColor" strokeWidth="1" opacity="0.5" />
      {/* Dashed outline to suggest emptiness */}
      <path d="M30 34 L40 28 L50 34" fill="none" stroke="currentColor" strokeWidth="0.8" strokeDasharray="2 2" opacity="0.3" />
    </g>
  ),

  /* Ship on water */
  tracking: (
    <g>
      <path d="M20 45 Q30 38 40 42 Q50 46 60 40" fill="none" stroke="currentColor" strokeWidth="1" opacity="0.3" />
      <path d="M15 52 Q30 46 40 50 Q55 54 65 48" fill="none" stroke="currentColor" strokeWidth="0.8" opacity="0.2" />
      {/* Simple ship hull */}
      <path d="M28 40 L32 28 L48 28 L52 40 Z" fill="none" stroke="currentColor" strokeWidth="1.3" />
      <line x1="40" y1="28" x2="40" y2="18" stroke="currentColor" strokeWidth="1.2" />
      <path d="M40 18 L50 24 L40 24" fill="none" stroke="currentColor" strokeWidth="0.8" opacity="0.5" />
    </g>
  ),

  /* Shield outline */
  compliance: (
    <g>
      <path d="M40 12 L58 22 L58 42 Q58 58 40 66 Q22 58 22 42 L22 22 Z" fill="none" stroke="currentColor" strokeWidth="1.3" />
      <path d="M33 38 L38 43 L48 32" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" opacity="0.4" />
    </g>
  ),

  /* Coin stack */
  financing: (
    <g>
      <ellipse cx="40" cy="52" rx="16" ry="6" fill="none" stroke="currentColor" strokeWidth="1.2" />
      <ellipse cx="40" cy="44" rx="16" ry="6" fill="none" stroke="currentColor" strokeWidth="1" opacity="0.6" />
      <ellipse cx="40" cy="36" rx="16" ry="6" fill="none" stroke="currentColor" strokeWidth="0.8" opacity="0.4" />
      <ellipse cx="40" cy="28" rx="16" ry="6" fill="none" stroke="currentColor" strokeWidth="0.7" opacity="0.25" />
      <line x1="24" y1="28" x2="24" y2="52" stroke="currentColor" strokeWidth="0.6" opacity="0.2" />
      <line x1="56" y1="28" x2="56" y2="52" stroke="currentColor" strokeWidth="0.6" opacity="0.2" />
    </g>
  ),
}

export default function EmptyState({
  variant = 'rfqs',
  message,
  sub,
  actionLabel,
  actionTo,
}) {
  const illustration = ILLUSTRATIONS[variant] || ILLUSTRATIONS.rfqs

  return (
    <div className="flex flex-col items-center justify-center py-16 px-4 animate-fade-in-up">
      {/* SVG illustration */}
      <div className="w-20 h-20 mb-5 text-stone-400">
        <svg viewBox="0 0 80 80" fill="none" className="w-full h-full" aria-hidden="true">
          {illustration}
        </svg>
      </div>

      {message && (
        <p className="text-sm font-medium text-stone-600 text-center">{message}</p>
      )}
      {sub && (
        <p className="text-xs text-stone-400 mt-1 text-center max-w-xs">{sub}</p>
      )}
      {actionLabel && actionTo && (
        <Link
          to={actionTo}
          className="mt-4 inline-flex items-center gap-1.5 text-sm font-medium text-stone-600 hover:text-stone-800 hover:scale-105 active:scale-95 transition-all"
        >
          {actionLabel} &rarr;
        </Link>
      )}
    </div>
  )
}
