import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'
import {
  LuCoffee, LuShieldCheck, LuHandshake, LuSprout, LuLink, LuMic,
  LuMessageCircle, LuRadioTower, LuLandmark, LuShip, LuFileText,
  LuBox, LuScale, LuStore, LuCpu,
} from 'react-icons/lu'

/* ── Category definitions ───────────────────────────────────────── */

const CATEGORIES = [
  { key: 'supply',     Icon: LuBox,   color: 'bg-emerald-500' },
  { key: 'compliance', Icon: LuScale, color: 'bg-amber-500' },
  { key: 'market',     Icon: LuStore, color: 'bg-blue-500' },
  { key: 'infra',      Icon: LuCpu,   color: 'bg-purple-500' },
]

/* ── Feature card (single) ──────────────────────────────────────── */

function FeatureCard({ f, index, total, expanded }) {
  // 3D stack offsets — when collapsed, cards stack behind the front card
  const stackOffset = expanded ? 0 : index * 6
  const stackScale = expanded ? 1 : 1 - index * 0.03
  const stackRotate = expanded ? 0 : index * -1.5
  const stackZ = total - index

  const style = expanded
    ? {
        transform: 'perspective(800px) rotateY(0deg) translateY(0) scale(1)',
        opacity: 1,
        zIndex: stackZ,
        transition: `all 0.4s cubic-bezier(0.34, 1.56, 0.64, 1) ${index * 0.07}s`,
      }
    : {
        transform: `perspective(800px) rotateY(${stackRotate}deg) translateY(${stackOffset}px) scale(${stackScale})`,
        opacity: index < 3 ? 1 - index * 0.15 : 0,
        zIndex: stackZ,
        transition: `all 0.4s cubic-bezier(0.34, 1.56, 0.64, 1) ${(total - index) * 0.05}s`,
      }

  const inner = (
    <div
      style={style}
      className={`bg-white rounded-2xl p-5 sm:p-6 shadow-sm border border-stone-100 hover:shadow-lg transition-shadow
        ${expanded ? '' : 'absolute inset-x-0 top-0'}
      `}
    >
      <div className="flex items-center gap-2 mb-3">
        <f.Icon className="w-7 h-7 text-stone-700" />
        {f.badge && (
          <span className="text-[10px] font-semibold uppercase tracking-wider bg-amber-100 text-amber-700 px-2 py-0.5 rounded-full">
            {f.badge}
          </span>
        )}
      </div>
      <h3 className="text-base font-semibold text-stone-900 mb-1.5">{f.title}</h3>
      <p className="text-sm text-stone-600 leading-relaxed">{f.desc}</p>
    </div>
  )

  if (f.link) {
    return (
      <Link to={f.link} className={expanded ? 'block' : 'absolute inset-x-0 top-0'} style={expanded ? {} : style}>
        <div className="bg-white rounded-2xl p-5 sm:p-6 shadow-sm border border-stone-100 hover:shadow-lg transition-shadow">
          <div className="flex items-center gap-2 mb-3">
            <f.Icon className="w-7 h-7 text-stone-700" />
            {f.badge && (
              <span className="text-[10px] font-semibold uppercase tracking-wider bg-amber-100 text-amber-700 px-2 py-0.5 rounded-full">
                {f.badge}
              </span>
            )}
          </div>
          <h3 className="text-base font-semibold text-stone-900 mb-1.5">{f.title}</h3>
          <p className="text-sm text-stone-600 leading-relaxed">{f.desc}</p>
        </div>
      </Link>
    )
  }

  return inner
}

/* ── Card deck (stacked 3D → fanned) ───────────────────────────── */

function CardDeck({ features }) {
  const { t } = useTranslation()
  const [expanded, setExpanded] = useState(false)

  return (
    <div>
      {/* Stacked preview (collapsed) */}
      {!expanded && (
        <div
          className="relative cursor-pointer group"
          style={{ minHeight: `${160 + (Math.min(features.length, 3) - 1) * 6}px` }}
          onClick={() => setExpanded(true)}
        >
          {features.map((f, i) => (
            <FeatureCard key={f.title} f={f} index={i} total={features.length} expanded={false} />
          ))}
          {/* "Tap to explore" hint overlay */}
          <div className="absolute inset-x-0 bottom-0 h-16 bg-gradient-to-t from-stone-50 to-transparent rounded-b-2xl flex items-end justify-center pb-3 z-50 pointer-events-none">
            <span className="text-xs font-medium text-stone-500 group-hover:text-stone-700 transition bg-white/80 backdrop-blur-sm rounded-full px-3 py-1 shadow-sm">
              {t('deck_explore', { count: features.length })}
            </span>
          </div>
        </div>
      )}

      {/* Expanded grid */}
      {expanded && (
        <div>
          <div className="grid gap-4 sm:grid-cols-2">
            {features.map((f, i) => (
              <FeatureCard key={f.title} f={f} index={i} total={features.length} expanded={true} />
            ))}
          </div>
          <button
            onClick={() => setExpanded(false)}
            className="mt-4 mx-auto block text-xs text-stone-400 hover:text-stone-600 transition"
          >
            {t('deck_collapse')}
          </button>
        </div>
      )}
    </div>
  )
}

/* ── Main landing page ──────────────────────────────────────────── */

export default function Landing() {
  const { t } = useTranslation()
  const [activeTab, setActiveTab] = useState('supply')

  // All features grouped by category
  const featuresByCategory = {
    supply: [
      { Icon: LuCoffee, title: t('feat_traceability'), desc: t('feat_traceability_desc') },
      { Icon: LuSprout, title: t('feat_dpp'), desc: t('feat_dpp_desc') },
      { Icon: LuMic, title: t('feat_voice'), desc: t('feat_voice_desc') },
    ],
    compliance: [
      { Icon: LuShieldCheck, title: t('feat_eudr'), desc: t('feat_eudr_desc') },
      { Icon: LuFileText, title: t('feat_customs'), desc: t('feat_customs_desc'), link: '/compliance' },
    ],
    market: [
      { Icon: LuHandshake, title: t('feat_rfq'), desc: t('feat_rfq_desc') },
      { Icon: LuLandmark, title: t('feat_defi'), desc: t('feat_defi_desc'), link: '/financing' },
    ],
    infra: [
      { Icon: LuLink, title: t('feat_blockchain'), desc: t('feat_blockchain_desc') },
      { Icon: LuRadioTower, title: t('feat_cre'), desc: t('feat_cre_desc'), badge: t('feat_cre_badge') },
      { Icon: LuShip, title: t('feat_tracking'), desc: t('feat_tracking_desc'), link: '/tracking' },
    ],
  }

  const categoryLabels = {
    supply: t('cat_supply'),
    compliance: t('cat_compliance'),
    market: t('cat_market'),
    infra: t('cat_infra'),
  }

  return (
    <div className="min-h-screen">
      {/* Hero */}
      <section className="relative overflow-hidden bg-gradient-to-br from-stone-900 via-stone-800 to-stone-950 text-white">
        <div className="absolute inset-0 opacity-10 bg-[url('data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iNjAiIGhlaWdodD0iNjAiIHZpZXdCb3g9IjAgMCA2MCA2MCIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj48ZyBmaWxsPSJub25lIiBmaWxsLXJ1bGU9ImV2ZW5vZGQiPjxnIGZpbGw9IiNmZmYiIGZpbGwtb3BhY2l0eT0iMC4xIj48cGF0aCBkPSJNMzYgMzRoLTJ2LTRoMnYtMmgtNHY2aDR2LTJ6bTAtMTZ2Mmg0di02aC00djRoLTJ2Mmgyem0tOCA4aDJ2NmgtMnYyaDR2LTZoMnYtMmgtNHYtMnptMC0ydi0ySDI0djJoMnYyaDJ2LTJ6Ii8+PC9nPjwvZz48L3N2Zz4=')]" />
        <div className="max-w-5xl mx-auto px-4 sm:px-6 py-16 sm:py-24 md:py-36 relative z-10 text-center flex flex-col items-center">
          <span className="inline-flex items-center gap-1.5 text-[11px] font-medium uppercase tracking-widest text-amber-300/90 border border-amber-400/30 bg-amber-400/10 rounded-full px-3 py-1 mb-6 backdrop-blur-sm">
            <span className="w-1.5 h-1.5 rounded-full bg-amber-400 animate-pulse" />
            Testnet – Base Sepolia
          </span>
          <h1 className="text-3xl sm:text-4xl md:text-6xl font-bold tracking-tight">
            {t('tagline')}
          </h1>
          <p className="mt-6 text-lg md:text-xl text-stone-300 max-w-2xl leading-relaxed">
            {t('hero_subtitle')}
          </p>
          <div className="mt-10 flex flex-wrap justify-center gap-4">
            <Link
              to="/assistant"
              className="inline-flex items-center gap-2 bg-white text-stone-900 font-semibold rounded-full px-6 py-3 hover:bg-stone-50 transition shadow-lg"
            >
              <LuMessageCircle className="w-5 h-5" /> {t('cta_chat')}
            </Link>
            <Link
              to="/login"
              className="inline-flex items-center gap-2 border-2 border-white/40 text-white font-semibold rounded-full px-6 py-3 hover:bg-white/10 transition"
            >
              {t('cta_login')}
            </Link>
          </div>
        </div>
      </section>

      {/* Features — tabbed categories + 3D stacked decks */}
      <section className="max-w-5xl mx-auto px-4 sm:px-6 py-12 sm:py-20">
        <h2 className="text-2xl md:text-3xl font-bold text-center text-stone-900 mb-10">
          {t('features_heading')}
        </h2>

        {/* Category tabs */}
        <div className="flex justify-center flex-wrap gap-2 mb-10">
          {CATEGORIES.map((cat) => {
            const isActive = activeTab === cat.key
            const count = featuresByCategory[cat.key]?.length || 0
            return (
              <button
                key={cat.key}
                onClick={() => setActiveTab(cat.key)}
                className={`inline-flex items-center gap-2 px-4 py-2.5 rounded-full text-sm font-medium transition-all duration-300 ${
                  isActive
                    ? 'bg-stone-900 text-white shadow-lg scale-105'
                    : 'bg-white text-stone-600 border border-stone-200 hover:border-stone-300 hover:bg-stone-50'
                }`}
              >
                <cat.Icon className="w-4 h-4" />
                {categoryLabels[cat.key]}
                <span className={`text-[10px] font-bold rounded-full w-5 h-5 flex items-center justify-center ${
                  isActive ? 'bg-white/20 text-white' : 'bg-stone-100 text-stone-500'
                }`}>
                  {count}
                </span>
              </button>
            )
          })}
        </div>

        {/* Active deck */}
        <div className="max-w-2xl mx-auto">
          {CATEGORIES.map((cat) => (
            <div key={cat.key} className={activeTab === cat.key ? 'block' : 'hidden'}>
              <CardDeck features={featuresByCategory[cat.key] || []} />
            </div>
          ))}
        </div>

        {/* Total feature count hint (Option E touch) */}
        <p className="text-center text-xs text-stone-400 mt-8">
          {t('feat_total', { count: Object.values(featuresByCategory).flat().length })}
        </p>
      </section>

      {/* CTA band */}
      <section className="bg-forest-600 text-white py-12 sm:py-16">
        <div className="max-w-3xl mx-auto text-center px-4 sm:px-6">
          <h2 className="text-2xl md:text-3xl font-bold">{t('cta_ready')}</h2>
          <p className="mt-3 text-forest-100">
            {t('cta_ready_desc')}
          </p>
          <Link
            to="/assistant"
            className="mt-8 inline-flex items-center gap-2 bg-white text-forest-700 font-semibold rounded-full px-8 py-3.5 hover:bg-forest-50 transition shadow-lg"
          >
            <LuMessageCircle className="w-5 h-5" /> {t('cta_start_chat')}
          </Link>
        </div>
      </section>
    </div>
  )
}
