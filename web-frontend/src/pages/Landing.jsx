import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'
import { LuCoffee, LuShieldCheck, LuHandshake, LuSprout, LuLink, LuMic, LuMessageCircle, LuRadioTower } from 'react-icons/lu'

export default function Landing() {
  const { t } = useTranslation()

  const features = [
    {
      Icon: LuCoffee,
      title: t('feat_traceability'),
      desc: t('feat_traceability_desc'),
    },
    {
      Icon: LuShieldCheck,
      title: t('feat_eudr'),
      desc: t('feat_eudr_desc'),
    },
    {
      Icon: LuHandshake,
      title: t('feat_rfq'),
      desc: t('feat_rfq_desc'),
    },
    {
      Icon: LuSprout,
      title: t('feat_dpp'),
      desc: t('feat_dpp_desc'),
    },
    {
      Icon: LuLink,
      title: t('feat_blockchain'),
      desc: t('feat_blockchain_desc'),
    },
    {
      Icon: LuMic,
      title: t('feat_voice'),
      desc: t('feat_voice_desc'),
    },
    {
      Icon: LuRadioTower,
      title: t('feat_cre'),
      desc: t('feat_cre_desc'),
      badge: t('feat_cre_badge'),
    },
  ]

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

      {/* Features grid */}
      <section className="max-w-6xl mx-auto px-4 sm:px-6 py-12 sm:py-20">
        <h2 className="text-2xl md:text-3xl font-bold text-center text-stone-900 mb-12">
          {t('features_heading')}
        </h2>
        <div className="flex flex-wrap justify-center gap-4 sm:gap-8">
          {features.map((f) => (
            <div
              key={f.title}
              className="bg-white rounded-2xl p-5 sm:p-6 shadow-sm border border-stone-100 hover:shadow-md transition w-full sm:w-[calc(50%-1rem)] lg:w-[calc(33.333%-1.34rem)]"
            >
              <div className="flex items-center gap-2 mb-3">
                <f.Icon className="w-8 h-8 text-stone-700" />
                {f.badge && (
                  <span className="text-[10px] font-semibold uppercase tracking-wider bg-amber-100 text-amber-700 px-2 py-0.5 rounded-full">
                    {f.badge}
                  </span>
                )}
              </div>
              <h3 className="text-lg font-semibold text-stone-900 mb-2">{f.title}</h3>
              <p className="text-sm text-stone-600 leading-relaxed">{f.desc}</p>
            </div>
          ))}
        </div>
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
