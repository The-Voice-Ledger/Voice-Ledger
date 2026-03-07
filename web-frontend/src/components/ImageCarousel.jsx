/**
 * Full-width auto-sliding image carousel for IPFS-hosted farm photos.
 *
 * Crossfade transition, no visible controls.
 * Thin progress dots at the bottom for context.
 * Pauses on hover / touch. Lazy-loads images.
 * Zero external dependencies.
 */

import { useState, useEffect, useCallback, useRef } from 'react'
import { useTranslation } from 'react-i18next'

const INTERVAL_MS = 3500 // time per slide
const FADE_MS     = 800  // crossfade duration

const SLIDES = [
  {
    src: 'https://violet-rainy-toad-577.mypinata.cloud/ipfs/bafkreicev3h5qhcf6d4wj7yiznigwsg5ebozey7xzf7alnkhualritbhz4',
    alt: 'carousel_alt_1',
  },
  {
    src: 'https://violet-rainy-toad-577.mypinata.cloud/ipfs/bafkreibmvvnwv5adpgmtah4od4jju32aeu3jgkd4eehwyzwpl74q3s4lj4',
    alt: 'carousel_alt_2',
  },
  {
    src: 'https://violet-rainy-toad-577.mypinata.cloud/ipfs/bafkreidg2ozctxon6x5n2sm5ws7qi4xst7svkknxthnthpdeww6gv25cmm',
    alt: 'carousel_alt_3',
  },
  {
    src: 'https://violet-rainy-toad-577.mypinata.cloud/ipfs/bafkreigbkn363elp6z6eogs55qdbfmhf6mrgs4xwzhlluzz5f6qevef6gi',
    alt: 'carousel_alt_4',
  },
  {
    src: 'https://violet-rainy-toad-577.mypinata.cloud/ipfs/bafybeibkdsmgcglaasxxwlml3gjrbzimgrpksa7qqhpnn6ixuxfr352jhe',
    alt: 'carousel_alt_5',
  },
  {
    src: 'https://violet-rainy-toad-577.mypinata.cloud/ipfs/bafkreighnwmof6uvaw5ic7uagz7hkffbi3rixywb7etao77hwbxu4a2k4u',
    alt: 'carousel_alt_6',
  },
]

export default function ImageCarousel() {
  const { t } = useTranslation()
  const [current, setCurrent] = useState(0)
  const [paused, setPaused] = useState(false)
  const timerRef = useRef(null)

  const advance = useCallback(() => {
    setCurrent((prev) => (prev + 1) % SLIDES.length)
  }, [])

  // Auto-advance
  useEffect(() => {
    if (paused) return
    timerRef.current = setInterval(advance, INTERVAL_MS)
    return () => clearInterval(timerRef.current)
  }, [paused, advance])

  return (
    <section
      className="relative w-full overflow-hidden bg-stone-900"
      onMouseEnter={() => setPaused(true)}
      onMouseLeave={() => setPaused(false)}
      aria-roledescription="carousel"
      aria-label={t('carousel_label')}
    >
      {/* Heading */}
      <div className="absolute top-0 left-0 right-0 z-20 pt-6 pb-10 bg-gradient-to-b from-stone-900/80 to-transparent pointer-events-none">
        <p className="text-center text-[10px] text-stone-300/70 uppercase tracking-[0.25em]">
          {t('carousel_heading')}
        </p>
      </div>

      {/* Slides */}
      <div className="relative w-full aspect-[21/9] sm:aspect-[2.5/1] md:aspect-[3/1]">
        {SLIDES.map((slide, i) => (
          <img
            key={i}
            src={slide.src}
            alt={t(slide.alt)}
            loading={i === 0 ? 'eager' : 'lazy'}
            className="absolute inset-0 w-full h-full object-cover carousel-slide"
            style={{
              opacity: i === current ? 1 : 0,
              transition: `opacity ${FADE_MS}ms ease-in-out`,
              zIndex: i === current ? 10 : 1,
            }}
            aria-hidden={i !== current}
          />
        ))}

        {/* Subtle Ken Burns zoom on active slide */}
        <style>{`
          .carousel-slide[aria-hidden="false"] {
            animation: ken-burns ${INTERVAL_MS + FADE_MS}ms ease-in-out forwards;
          }
        `}</style>

        {/* Dark vignette overlay */}
        <div className="absolute inset-0 z-10 pointer-events-none bg-gradient-to-t from-stone-900/50 via-transparent to-stone-900/30" />
      </div>

      {/* Progress dots */}
      <div className="absolute bottom-4 left-0 right-0 z-20 flex justify-center gap-2">
        {SLIDES.map((_, i) => (
          <button
            key={i}
            onClick={() => setCurrent(i)}
            aria-label={`${t('carousel_goto')} ${i + 1}`}
            className={`h-1.5 rounded-full transition-all duration-500 ${
              i === current
                ? 'w-6 bg-white/90'
                : 'w-1.5 bg-white/30 hover:bg-white/50'
            }`}
          />
        ))}
      </div>
    </section>
  )
}
