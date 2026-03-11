/**
 * Bespoke SVG icon set for Voice Ledger.
 *
 * 44 hand-crafted inline SVG icons replacing the Lucide (react-icons/lu) set.
 * Each icon renders a pure SVG at the given size.  All icons use currentColor
 * for stroke/fill so they inherit text colour from the parent element.
 *
 * Usage:
 *   import { IconCoffee, IconShip } from '../components/svg/Icons'
 *   <IconCoffee className="w-5 h-5 text-stone-600" />
 */

/* ── Wrapper ────────────────────────────────────────────────────── */

function I({ children, className = '', size, ...rest }) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
      width={size}
      height={size}
      aria-hidden="true"
      {...rest}
    >
      {children}
    </svg>
  )
}

/* ── Icons ──────────────────────────────────────────────────────── */

// 1. Anchor — port/dock
export function IconAnchor(p) {
  return <I {...p}><circle cx="12" cy="5" r="2"/><line x1="12" y1="7" x2="12" y2="21"/><path d="M5 12H2a10 10 0 0020 0h-3"/></I>
}

// 2. ArrowRight
export function IconArrowRight(p) {
  return <I {...p}><line x1="5" y1="12" x2="19" y2="12"/><polyline points="13 6 19 12 13 18"/></I>
}

// 3. Box — container/package
export function IconBox(p) {
  return <I {...p}><path d="M21 16V8a2 2 0 00-1-1.73l-7-4a2 2 0 00-2 0l-7 4A2 2 0 003 8v8a2 2 0 001 1.73l7 4a2 2 0 002 0l7-4A2 2 0 0021 16z"/><polyline points="3.27 6.96 12 12.01 20.73 6.96"/><line x1="12" y1="22.08" x2="12" y2="12"/></I>
}

// 4. ChartBar — bar chart
export function IconChartBar(p) {
  return <I {...p}><rect x="3" y="12" width="4" height="9" rx="1"/><rect x="10" y="7" width="4" height="14" rx="1"/><rect x="17" y="3" width="4" height="18" rx="1"/></I>
}

// 5. Check — simple checkmark
export function IconCheck(p) {
  return <I {...p}><polyline points="5 12 10 17 19 7"/></I>
}

// 6. ChevronDown
export function IconChevronDown(p) {
  return <I {...p}><polyline points="6 9 12 15 18 9"/></I>
}

// 7. Circle — empty circle
export function IconCircle(p) {
  return <I {...p}><circle cx="12" cy="12" r="9"/></I>
}

// 8. CircleCheck — circle with checkmark
export function IconCircleCheck(p) {
  return <I {...p}><circle cx="12" cy="12" r="9"/><polyline points="9 12 11.5 14.5 16 9.5"/></I>
}

// 9. CircleDot — current/active dot
export function IconCircleDot(p) {
  return <I {...p}><circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="2" fill="currentColor" stroke="none"/></I>
}

// 10. CircleX — failure circle
export function IconCircleX(p) {
  return <I {...p}><circle cx="12" cy="12" r="9"/><line x1="9" y1="9" x2="15" y2="15"/><line x1="15" y1="9" x2="9" y2="15"/></I>
}

// 11. Coffee — coffee bean / cup
export function IconCoffee(p) {
  return <I {...p}><path d="M18 8h1a4 4 0 010 8h-1"/><path d="M2 8h16v9a4 4 0 01-4 4H6a4 4 0 01-4-4V8z"/><line x1="6" y1="1" x2="6" y2="4"/><line x1="10" y1="1" x2="10" y2="4"/><line x1="14" y1="1" x2="14" y2="4"/></I>
}

// 12. Copy — clipboard copy
export function IconCopy(p) {
  return <I {...p}><rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 01-2-2V4a2 2 0 012-2h9a2 2 0 012 2v1"/></I>
}

// 13. Cpu — processor/infrastructure
export function IconCpu(p) {
  return <I {...p}><rect x="4" y="4" width="16" height="16" rx="2"/><rect x="9" y="9" width="6" height="6" rx="1"/><line x1="9" y1="1" x2="9" y2="4"/><line x1="15" y1="1" x2="15" y2="4"/><line x1="9" y1="20" x2="9" y2="23"/><line x1="15" y1="20" x2="15" y2="23"/><line x1="20" y1="9" x2="23" y2="9"/><line x1="20" y1="14" x2="23" y2="14"/><line x1="1" y1="9" x2="4" y2="9"/><line x1="1" y1="14" x2="4" y2="14"/></I>
}

// 14. Download
export function IconDownload(p) {
  return <I {...p}><path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></I>
}

// 15. ExternalLink
export function IconExternalLink(p) {
  return <I {...p}><path d="M18 13v6a2 2 0 01-2 2H5a2 2 0 01-2-2V8a2 2 0 012-2h6"/><polyline points="15 3 21 3 21 9"/><line x1="10" y1="14" x2="21" y2="3"/></I>
}

// 16. FileText — document
export function IconFileText(p) {
  return <I {...p}><path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/><line x1="10" y1="9" x2="8" y2="9"/></I>
}

// 17. Globe
export function IconGlobe(p) {
  return <I {...p}><circle cx="12" cy="12" r="10"/><line x1="2" y1="12" x2="22" y2="12"/><path d="M12 2a15.3 15.3 0 014 10 15.3 15.3 0 01-4 10 15.3 15.3 0 01-4-10 15.3 15.3 0 014-10z"/></I>
}

// 18. Handshake — deal/trade
export function IconHandshake(p) {
  return <I {...p}><path d="M20.5 11.5L17 8l-5 3-4-2.5L3.5 11.5"/><path d="M3.5 11.5L7 15l3-1 4 3 6.5-5.5"/><path d="M2 17l3.5-5.5"/><path d="M22 17l-3.5-5.5"/></I>
}

// 19. Info — information circle
export function IconInfo(p) {
  return <I {...p}><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><circle cx="12" cy="8" r="0.5" fill="currentColor" stroke="none"/></I>
}

// 20. Landmark — bank/institution
export function IconLandmark(p) {
  return <I {...p}><line x1="3" y1="22" x2="21" y2="22"/><line x1="6" y1="18" x2="6" y2="11"/><line x1="10" y1="18" x2="10" y2="11"/><line x1="14" y1="18" x2="14" y2="11"/><line x1="18" y1="18" x2="18" y2="11"/><polygon points="12 2 20 7 4 7"/><line x1="2" y1="22" x2="22" y2="22"/><rect x="2" y="18" width="20" height="4" rx="0"/></I>
}

// 21. Link — chain link / blockchain
export function IconLink(p) {
  return <I {...p}><path d="M10 13a5 5 0 007.54.54l3-3a5 5 0 00-7.07-7.07l-1.72 1.71"/><path d="M14 11a5 5 0 00-7.54-.54l-3 3a5 5 0 007.07 7.07l1.71-1.71"/></I>
}

// 22. Loader — spinner
export function IconLoader(p) {
  return <I {...p} className={`animate-spin ${p.className || ''}`}><path d="M21 12a9 9 0 11-6.219-8.56"/></I>
}

// 23. LogIn — sign in
export function IconLogIn(p) {
  return <I {...p}><path d="M15 3h4a2 2 0 012 2v14a2 2 0 01-2 2h-4"/><polyline points="10 17 15 12 10 7"/><line x1="15" y1="12" x2="3" y2="12"/></I>
}

// 24. MapPin — location marker
export function IconMapPin(p) {
  return <I {...p}><path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0118 0z"/><circle cx="12" cy="10" r="3"/></I>
}

// 25. Menu — hamburger
export function IconMenu(p) {
  return <I {...p}><line x1="3" y1="6" x2="21" y2="6"/><line x1="3" y1="12" x2="21" y2="12"/><line x1="3" y1="18" x2="21" y2="18"/></I>
}

// 26. MessageCircle — chat bubble
export function IconMessageCircle(p) {
  return <I {...p}><path d="M21 11.5a8.38 8.38 0 01-.9 3.8 8.5 8.5 0 01-7.6 4.7 8.38 8.38 0 01-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 01-.9-3.8 8.5 8.5 0 014.7-7.6 8.38 8.38 0 013.8-.9h.5a8.48 8.48 0 018 8v.5z"/></I>
}

// 27. Mic — microphone
export function IconMic(p) {
  return <I {...p}><path d="M12 1a3 3 0 00-3 3v8a3 3 0 006 0V4a3 3 0 00-3-3z"/><path d="M19 10v2a7 7 0 01-14 0v-2"/><line x1="12" y1="19" x2="12" y2="23"/><line x1="8" y1="23" x2="16" y2="23"/></I>
}

// 28. Package — parcel/batch
export function IconPackage(p) {
  return <I {...p}><path d="M16.5 9.4l-9-5.19"/><path d="M21 16V8a2 2 0 00-1-1.73l-7-4a2 2 0 00-2 0l-7 4A2 2 0 003 8v8a2 2 0 001 1.73l7 4a2 2 0 002 0l7-4A2 2 0 0021 16z"/><polyline points="3.27 6.96 12 12.01 20.73 6.96"/><line x1="12" y1="22.08" x2="12" y2="12"/></I>
}

// 29. PackageCheck — delivered/verified package
export function IconPackageCheck(p) {
  return <I {...p}><path d="M16.5 9.4l-9-5.19"/><path d="M21 16V8a2 2 0 00-1-1.73l-7-4a2 2 0 00-2 0l-7 4A2 2 0 003 8v8a2 2 0 001 1.73l7 4a2 2 0 002 0l7-4A2 2 0 0021 16z"/><polyline points="3.27 6.96 12 12.01 20.73 6.96"/><line x1="12" y1="22.08" x2="12" y2="12"/><polyline points="10 15 12.5 17.5 17 12" strokeWidth="2"/></I>
}

// 30. RadioTower — broadcast/CRE oracle
export function IconRadioTower(p) {
  return <I {...p}><path d="M4.9 16.1C1 12.2 1 5.8 4.9 1.9"/><path d="M7.8 13.2c-2.3-2.3-2.3-6.1 0-8.5"/><circle cx="12" cy="9" r="2"/><path d="M16.2 13.2c2.3-2.3 2.3-6.1 0-8.5"/><path d="M19.1 16.1c3.9-3.9 3.9-10.2 0-14.1"/><line x1="12" y1="11" x2="12" y2="23"/></I>
}

// 31. RefreshCw — refresh arrows
export function IconRefreshCw(p) {
  return <I {...p}><polyline points="23 4 23 10 17 10"/><polyline points="1 20 1 14 7 14"/><path d="M3.51 9a9 9 0 0114.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0020.49 15"/></I>
}

// 32. Scale — balance/compliance
export function IconScale(p) {
  return <I {...p}><line x1="12" y1="3" x2="12" y2="21"/><path d="M5 8l7-5 7 5"/><path d="M3 14l2-6 2 6a4 4 0 01-4 0z"/><path d="M17 14l2-6 2 6a4 4 0 01-4 0z"/></I>
}

// 33. Search — magnifying glass
export function IconSearch(p) {
  return <I {...p}><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></I>
}

// 34. ShieldCheck — EUDR shield
export function IconShieldCheck(p) {
  return <I {...p}><path d="M12 2l8 4v6c0 5.5-3.84 10.74-8 12-4.16-1.26-8-6.5-8-12V6l8-4z"/><polyline points="9 12 11 14 15 10"/></I>
}

// 35. Ship — shipping vessel
export function IconShip(p) {
  return <I {...p}><path d="M2 21c.6.5 1.2 1 2.5 1 2.5 0 2.5-2 5-2 2.5 0 2.5 2 5 2 2.5 0 2.5-2 5-2 1.3 0 1.9.5 2.5 1"/><path d="M19.38 14H21l-2-8H5L3 14h1.62"/><path d="M19.38 14L17 20H7L4.62 14"/><line x1="12" y1="6" x2="12" y2="2"/><path d="M10 2h4"/></I>
}

// 36. Sparkles — AI/magic
export function IconSparkles(p) {
  return <I {...p} fill="currentColor" stroke="none"><path d="M12 2l1.09 3.26L16.36 4l-1.26 3.36L18.36 8.45l-3.27 1.09L16.36 12l-3.27-1.09L12 14.18l-1.09-3.27L7.64 12l1.27-3.36L5.64 7.36l3.27-1.09L7.64 3l3.27 1.09z"/><path d="M20 14l.6 1.8L22.4 15l-.8 2.1.8 2.1-1.8.6L20 22l-.6-1.8-1.8-.6.8-2.1-.8-2.1 1.8-.6z" opacity="0.6"/></I>
}

// 37. Sprout — plant/DPP
export function IconSprout(p) {
  return <I {...p}><path d="M7 20h10"/><path d="M10 20c5.5-2.5.8-6.4 3-10"/><path d="M9.5 9.4c1.1.8 1.8 2.2 2.3 3.7-2 .4-3.5.4-4.8-.3-1.2-.6-2.3-1.9-3-4.2 2.8-.5 4.4 0 5.5.8z"/><path d="M14.1 6a7 7 0 00-1.1 4c1.9-.1 3.3-.6 4.3-1.4 1-1 1.6-2.5 1.7-4.6-2.7.1-4 1-4.9 2z"/></I>
}

// 38. Store — marketplace/storefront
export function IconStore(p) {
  return <I {...p}><path d="M3 9l1.5-5h15L21 9"/><path d="M3 9v11a1 1 0 001 1h16a1 1 0 001-1V9"/><path d="M3 9h18"/><path d="M9 21V14h6v7"/><path d="M5.5 9a2.5 2.5 0 01-2.5 2.5"/><path d="M9.5 9A2.5 2.5 0 017 11.5"/><path d="M9.5 9a2.5 2.5 0 002.5 2.5"/><path d="M14.5 9a2.5 2.5 0 01-2.5 2.5"/><path d="M14.5 9a2.5 2.5 0 002.5 2.5"/><path d="M18.5 9a2.5 2.5 0 002.5 2.5"/></I>
}

// 39. TrendingUp — upward trend
export function IconTrendingUp(p) {
  return <I {...p}><polyline points="23 6 13.5 15.5 8.5 10.5 1 18"/><polyline points="17 6 23 6 23 12"/></I>
}

// 40. Users — people group
export function IconUsers(p) {
  return <I {...p}><path d="M17 21v-2a4 4 0 00-4-4H5a4 4 0 00-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 00-3-3.87"/><path d="M16 3.13a4 4 0 010 7.75"/></I>
}

// 41. Volume2 — speaker/TTS
export function IconVolume2(p) {
  return <I {...p}><polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"/><path d="M19.07 4.93a10 10 0 010 14.14"/><path d="M15.54 8.46a5 5 0 010 7.07"/></I>
}

// 42. Wallet
export function IconWallet(p) {
  return <I {...p}><rect x="1" y="6" width="22" height="16" rx="2"/><path d="M1 10h22"/><path d="M17 14h.01"/><path d="M7 2l5 4 5-4"/></I>
}

// 43. Wrench — tool
export function IconWrench(p) {
  return <I {...p}><path d="M14.7 6.3a1 1 0 000 1.4l1.6 1.6a1 1 0 001.4 0l3.77-3.77a6 6 0 01-7.94 7.94l-6.91 6.91a2.12 2.12 0 01-3-3l6.91-6.91a6 6 0 017.94-7.94l-3.76 3.76z"/></I>
}

// 44. X — close
export function IconX(p) {
  return <I {...p}><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></I>
}
