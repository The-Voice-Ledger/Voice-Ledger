import { useState } from 'react'
import { Link, useLocation } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { LuMenu, LuX } from 'react-icons/lu'
import useAuthStore from '../stores/authStore'
import useChatStore from '../stores/chatStore'

const WAGA_LOGO = 'https://violet-rainy-toad-577.mypinata.cloud/ipfs/bafybeic6pclaqgbaaz6qqvlz2ssjgbzae4y7e76d2pobbwfxs2cviwgyqa'

export default function Navbar() {
  const { t, i18n } = useTranslation()
  const { isAuthenticated, user, logout } = useAuthStore()
  const { setLanguage } = useChatStore()
  const location = useLocation()
  const [menuOpen, setMenuOpen] = useState(false)

  const toggleLang = () => {
    const next = i18n.language === 'en' ? 'am' : 'en'
    i18n.changeLanguage(next)
    setLanguage(next)
  }

  const isActive = (path) => location.pathname === path

  const navLink = (to, label, mobile = false) => (
    <Link
      to={to}
      onClick={() => setMenuOpen(false)}
      className={`${mobile ? 'block px-3 py-2.5 rounded-lg text-sm' : 'relative px-1 py-1 text-[13px] tracking-wide'} transition-colors ${
        isActive(to)
          ? mobile
            ? 'bg-stone-100 text-stone-900 font-semibold'
            : 'text-stone-900 font-semibold after:absolute after:inset-x-0 after:-bottom-0.5 after:h-0.5 after:bg-stone-900 after:rounded-full'
          : mobile
            ? 'text-stone-600 active:bg-stone-50'
            : 'text-stone-500 hover:text-stone-800'
      }`}
    >
      {label}
    </Link>
  )

  return (
    <>
      <nav className="sticky top-0 z-40 h-14 bg-white/80 backdrop-blur-lg border-b border-stone-100 flex items-center px-4 md:px-6">
        {/* Brand */}
        <Link to="/" className="flex items-center gap-2 shrink-0">
          <img src={WAGA_LOGO} alt="WAGA Coffee" className="h-7 w-auto" />
          <div className="hidden sm:flex flex-col leading-none">
            <span className="text-sm font-bold tracking-tight text-stone-900">{t('brand')}</span>
            <span className="text-[9px] text-stone-400 tracking-wide">{t('powered_by')}</span>
          </div>
        </Link>

        {/* Center -- Nav links (desktop) */}
        <div className="flex-1 hidden md:flex items-center justify-center gap-6">
          {navLink('/', t('nav_home'))}
          {navLink('/assistant', t('nav_assistant'))}
          {navLink('/marketplace', t('nav_marketplace'))}
          {isAuthenticated && navLink('/my-rfqs', t('nav_my_rfqs'))}
          {navLink('/compliance', t('nav_compliance'))}
          {navLink('/dpp', t('nav_dpp'))}
        </div>

        {/* Right -- Controls */}
        <div className="flex items-center gap-2 shrink-0 ml-auto">
          <button
            onClick={toggleLang}
            className="px-2 py-1 rounded-md text-[11px] font-semibold tracking-wide uppercase bg-stone-100 hover:bg-stone-200 text-stone-600 transition"
            title="Switch language"
          >
            {i18n.language === 'en' ? 'አማ' : 'EN'}
          </button>

          {isAuthenticated ? (
            <div className="flex items-center gap-2">
              <span className="text-xs text-stone-400 hidden md:inline">
                {user?.phone_number || user?.full_name || 'User'}
              </span>
              <button
                onClick={logout}
                className="px-3 py-1.5 rounded-md text-xs font-medium text-stone-500 hover:text-stone-800 hover:bg-stone-100 transition"
              >
                {t('nav_logout')}
              </button>
            </div>
          ) : (
            <Link
              to="/login"
              className="hidden md:inline-block px-4 py-1.5 rounded-md text-xs font-semibold bg-stone-900 text-white hover:bg-stone-800 transition"
            >
              {t('nav_login')}
            </Link>
          )}

          {/* Mobile hamburger */}
          <button
            onClick={() => setMenuOpen(!menuOpen)}
            className="md:hidden p-1.5 rounded-lg text-stone-600 hover:bg-stone-100 transition"
            aria-label="Toggle menu"
          >
            {menuOpen ? <LuX className="w-5 h-5" /> : <LuMenu className="w-5 h-5" />}
          </button>
        </div>
      </nav>

      {/* Mobile slide-down menu */}
      {menuOpen && (
        <div className="md:hidden fixed inset-x-0 top-14 z-30 bg-white/95 backdrop-blur-lg border-b border-stone-200 shadow-lg animate-fade-in-up">
          <div className="px-4 py-3 space-y-1">
            {navLink('/', t('nav_home'), true)}
            {navLink('/assistant', t('nav_assistant'), true)}
            {navLink('/marketplace', t('nav_marketplace'), true)}
            {isAuthenticated && navLink('/my-rfqs', t('nav_my_rfqs'), true)}
            {navLink('/compliance', t('nav_compliance'), true)}
            {navLink('/dpp', t('nav_dpp'), true)}
            {!isAuthenticated && (
              <Link
                to="/login"
                onClick={() => setMenuOpen(false)}
                className="block mt-2 text-center text-sm font-semibold bg-stone-900 text-white rounded-lg py-2.5 active:bg-stone-800 transition"
              >
                {t('nav_login')}
              </Link>
            )}
          </div>
        </div>
      )}

      {/* Backdrop overlay for mobile menu */}
      {menuOpen && (
        <div
          className="md:hidden fixed inset-0 top-14 z-20 bg-black/20"
          onClick={() => setMenuOpen(false)}
        />
      )}
    </>
  )
}
