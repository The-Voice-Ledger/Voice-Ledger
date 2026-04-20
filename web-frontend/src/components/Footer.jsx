import { Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'

const WAGA_LOGO = 'https://violet-rainy-toad-577.mypinata.cloud/ipfs/bafybeic6pclaqgbaaz6qqvlz2ssjgbzae4y7e76d2pobbwfxs2cviwgyqa'

/* ── Bespoke social SVG icons ──────────────────────────────────── */

function TelegramIcon({ className }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="currentColor">
      <path d="M11.944 0A12 12 0 0 0 0 12a12 12 0 0 0 12 12 12 12 0 0 0 12-12A12 12 0 0 0 12 0a12 12 0 0 0-.056 0zm4.962 7.224c.1-.002.321.023.465.14a.506.506 0 0 1 .171.325c.016.093.036.306.02.472-.18 1.898-.962 6.502-1.36 8.627-.168.9-.499 1.201-.82 1.23-.696.065-1.225-.46-1.9-.902-1.056-.693-1.653-1.124-2.678-1.8-1.185-.78-.417-1.21.258-1.91.177-.184 3.247-2.977 3.307-3.23.007-.032.014-.15-.056-.212s-.174-.041-.249-.024c-.106.024-1.793 1.14-5.061 3.345-.48.33-.913.49-1.302.48-.428-.008-1.252-.241-1.865-.44-.752-.245-1.349-.374-1.297-.789.027-.216.325-.437.893-.663 3.498-1.524 5.83-2.529 6.998-3.014 3.332-1.386 4.025-1.627 4.476-1.635z" />
    </svg>
  )
}

function LinkedInIcon({ className }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="currentColor">
      <path d="M20.447 20.452h-3.554v-5.569c0-1.328-.027-3.037-1.852-3.037-1.853 0-2.136 1.445-2.136 2.939v5.667H9.351V9h3.414v1.561h.046c.477-.9 1.637-1.85 3.37-1.85 3.601 0 4.267 2.37 4.267 5.455v6.286zM5.337 7.433a2.062 2.062 0 0 1-2.063-2.065 2.064 2.064 0 1 1 2.063 2.065zm1.782 13.019H3.555V9h3.564v11.452zM22.225 0H1.771C.792 0 0 .774 0 1.729v20.542C0 23.227.792 24 1.771 24h20.451C23.2 24 24 23.227 24 22.271V1.729C24 .774 23.2 0 22.222 0h.003z" />
    </svg>
  )
}

function XIcon({ className }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="currentColor">
      <path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z" />
    </svg>
  )
}

/* ── Circuit-board SVG background ──────────────────────────────── */

function FooterCircuitBg() {
  return (
    <svg
      className="absolute inset-0 w-full h-full pointer-events-none text-white/[0.04]"
      preserveAspectRatio="xMidYMid slice"
      aria-hidden="true"
    >
      <defs>
        <pattern id="footer-circuit" x="0" y="0" width="120" height="100" patternUnits="userSpaceOnUse">
          <g stroke="currentColor" strokeWidth="0.6" fill="none">
            {/* horizontal & vertical traces */}
            <path d="M0 20h30 M30 20v25 M30 45h20 M100 10h-20 M80 10v30 M80 40h-15" />
            <path d="M10 70h25 M35 70v-15 M35 55h20 M95 65h-15 M95 65v-20" />
            <path d="M5 90h40 M45 90v-12 M45 78h15 M110 85h-10 M110 85v-25" />
            {/* solder pads */}
            {[[30,20],[30,45],[80,10],[80,40],[35,70],[110,85],[45,78],[10,70],[5,90]].map(([cx,cy],i) => (
              <circle key={i} cx={cx} cy={cy} r="2" fill="currentColor" opacity="0.6" />
            ))}
            {/* IC chips */}
            <rect x="55" y="18" width="12" height="18" rx="1.5" strokeWidth="0.8" />
            <rect x="88" y="42" width="10" height="14" rx="1.5" strokeWidth="0.8" />
            {/* IC pins */}
            {[22,26,30,34].map((y,i) => <line key={`a${i}`} x1="53" y1={y} x2="55" y2={y} strokeWidth="0.5" />)}
            {[22,26,30,34].map((y,i) => <line key={`b${i}`} x1="67" y1={y} x2="69" y2={y} strokeWidth="0.5" />)}
          </g>
        </pattern>
      </defs>
      <rect width="100%" height="100%" fill="url(#footer-circuit)" />
    </svg>
  )
}

/* ── Social link component ─────────────────────────────────────── */

const SOCIALS = [
  {
    label: 'Telegram',
    href: 'https://t.me/wagatoken',
    Icon: TelegramIcon,
    hoverColor: 'hover:bg-[#229ED9]/20 hover:text-[#229ED9]',
  },
  {
    label: 'LinkedIn',
    href: 'https://www.linkedin.com/company/the-waga-protocol/',
    Icon: LinkedInIcon,
    hoverColor: 'hover:bg-[#0A66C2]/20 hover:text-[#0A66C2]',
  },
  {
    label: 'X',
    href: 'https://x.com/Wagatoken',
    Icon: XIcon,
    hoverColor: 'hover:bg-white/15 hover:text-white',
  },
]

/* ── Tech badge pills (bottom bar) ─────────────────────────────── */

const TECH_BADGES = [
  'Base (Ethereum L2)',
  'Chainlink CRE',
  'GS1 / EPCIS',
  'IPFS / Pinata',
  'ERC-4626 Vault',
]

/* ── Footer ────────────────────────────────────────────────────── */

export default function Footer() {
  const { t } = useTranslation()
  const year = new Date().getFullYear()

  return (
    <footer className="relative bg-gradient-to-b from-stone-900 via-stone-900 to-stone-950 text-stone-400 overflow-hidden">
      <FooterCircuitBg />

      {/* Top accent line */}
      <div className="h-px bg-gradient-to-r from-transparent via-coffee-500/40 to-transparent" />

      <div className="relative z-10 max-w-6xl mx-auto px-4 sm:px-6">

        {/* ── Main grid ────────────────────────────────────────── */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-8 pt-12 pb-10">

          {/* Column 1: Brand */}
          <div className="col-span-2 md:col-span-1">
            <Link to="/" className="inline-flex items-center gap-2.5 group">
              <img src={WAGA_LOGO} alt="WAGA Coffee" className="h-8 w-auto rounded opacity-90 group-hover:opacity-100 transition" />
              <div className="flex flex-col leading-none">
                <span className="text-sm font-bold text-white font-display tracking-tight">{t('brand')}</span>
                <span className="text-[9px] text-stone-500 tracking-wide">{t('powered_by')}</span>
              </div>
            </Link>
            <p className="mt-4 text-sm text-stone-500 leading-relaxed max-w-xs">
              {t('footer_desc', 'AI-powered traceability, EUDR compliance, and marketplace for Ethiopian specialty coffee.')}
            </p>

            {/* Social icons */}
            <div className="flex gap-2 mt-5">
              {SOCIALS.map((s) => (
                <a
                  key={s.label}
                  href={s.href}
                  target="_blank"
                  rel="noopener noreferrer"
                  aria-label={s.label}
                  className={`w-9 h-9 rounded-lg bg-white/5 border border-white/10 flex items-center justify-center text-stone-400 transition-all duration-200 ${s.hoverColor}`}
                >
                  <s.Icon className="w-4 h-4" />
                </a>
              ))}
            </div>
          </div>

          {/* Column 2: Platform */}
          <div>
            <h4 className="text-xs font-semibold uppercase tracking-widest text-stone-500 mb-4 font-display">
              {t('footer_platform', 'Platform')}
            </h4>
            <ul className="space-y-2.5">
              {[
                ['/', t('nav_home')],
                ['/assistant', t('nav_assistant')],
                ['/marketplace', t('nav_marketplace')],
                ['/my-rfqs', t('nav_my_rfqs')],
                ['/how-it-works', t('nav_how_it_works', 'How It Works')],
                ['/platform', t('nav_platform', 'The Platform')],
              ].map(([to, label]) => (
                <li key={to}>
                  <Link to={to} className="text-sm text-stone-400 hover:text-white transition-colors">
                    {label}
                  </Link>
                </li>
              ))}
            </ul>
          </div>

          {/* Column 3: Tools */}
          <div>
            <h4 className="text-xs font-semibold uppercase tracking-widest text-stone-500 mb-4 font-display">
              {t('nav_tools', 'Tools')}
            </h4>
            <ul className="space-y-2.5">
              {[
                ['/financing', t('nav_financing')],
                ['/tracking', t('nav_tracking')],
                ['/compliance', t('nav_compliance')],
                ['/dpp', t('nav_dpp')],
              ].map(([to, label]) => (
                <li key={to}>
                  <Link to={to} className="text-sm text-stone-400 hover:text-white transition-colors">
                    {label}
                  </Link>
                </li>
              ))}
            </ul>
          </div>

          {/* Column 4: Connect */}
          <div>
            <h4 className="text-xs font-semibold uppercase tracking-widest text-stone-500 mb-4 font-display">
              {t('footer_connect', 'Connect')}
            </h4>
            <ul className="space-y-2.5">
              {SOCIALS.map((s) => (
                <li key={s.label}>
                  <a
                    href={s.href}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center gap-2 text-sm text-stone-400 hover:text-white transition-colors"
                  >
                    <s.Icon className="w-3.5 h-3.5" />
                    {s.label}
                  </a>
                </li>
              ))}
              <li>
                <a
                  href="https://www.addisai.ch/"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-2 text-sm text-stone-400 hover:text-white transition-colors"
                >
                  <svg className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18z" />
                    <path d="M3.6 9h16.8 M3.6 15h16.8" />
                    <path d="M12 3a15 15 0 0 1 4 9 15 15 0 0 1-4 9 15 15 0 0 1-4-9 15 15 0 0 1 4-9z" />
                  </svg>
                  Addis AI
                </a>
              </li>
            </ul>
          </div>
        </div>

        {/* ── Divider ──────────────────────────────────────────── */}
        <div className="h-px bg-gradient-to-r from-transparent via-stone-700/50 to-transparent" />

        {/* ── Bottom bar ───────────────────────────────────────── */}
        <div className="py-6 flex flex-col sm:flex-row items-center justify-between gap-4">
          <p className="text-xs text-stone-500">
            © {year} WAGA Coffee · {t('powered_by')}
          </p>

          {/* Tech stack badges */}
          <div className="flex flex-wrap justify-center gap-1.5">
            {TECH_BADGES.map((b) => (
              <span
                key={b}
                className="text-[9px] font-medium tracking-wide text-stone-500/70 border border-stone-700/40 rounded-full px-2 py-0.5 bg-stone-800/30"
              >
                {b}
              </span>
            ))}
          </div>
        </div>
      </div>
    </footer>
  )
}
