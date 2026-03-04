import { Link, useLocation } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import useAuthStore from '../stores/authStore'
import useChatStore from '../stores/chatStore'

const WAGA_LOGO = 'https://violet-rainy-toad-577.mypinata.cloud/ipfs/bafybeic6pclaqgbaaz6qqvlz2ssjgbzae4y7e76d2pobbwfxs2cviwgyqa'

export default function Navbar() {
  const { t, i18n } = useTranslation()
  const { isAuthenticated, user, logout } = useAuthStore()
  const { setLanguage } = useChatStore()
  const location = useLocation()

  const toggleLang = () => {
    const next = i18n.language === 'en' ? 'am' : 'en'
    i18n.changeLanguage(next)
    setLanguage(next)
  }

  const isActive = (path) => location.pathname === path

  const navLink = (to, label, hideMobile = false) => (
    <Link
      to={to}
      className={`relative px-1 py-1 text-[13px] tracking-wide transition-colors ${
        hideMobile ? 'hidden md:block' : ''
      } ${
        isActive(to)
          ? 'text-stone-900 font-semibold after:absolute after:inset-x-0 after:-bottom-0.5 after:h-0.5 after:bg-stone-900 after:rounded-full'
          : 'text-stone-500 hover:text-stone-800'
      }`}
    >
      {label}
    </Link>
  )

  return (
    <nav className="sticky top-0 z-40 h-14 bg-white/80 backdrop-blur-lg border-b border-stone-100 flex items-center px-4 md:px-6">
      {/* Brand */}
      <Link to="/" className="flex items-center gap-2 shrink-0">
        <img src={WAGA_LOGO} alt="WAGA Coffee" className="h-7 w-auto" />
        <div className="hidden sm:flex flex-col leading-none">
          <span className="text-sm font-bold tracking-tight text-stone-900">{t('brand')}</span>
          <span className="text-[9px] text-stone-400 tracking-wide">{t('powered_by')}</span>
        </div>
      </Link>

      {/* Center -- Nav links */}
      <div className="flex-1 flex items-center justify-center gap-6">
        {navLink('/', t('nav_home'))}
        {navLink('/assistant', t('nav_assistant'))}
        {navLink('/marketplace', t('nav_marketplace'), true)}
        {isAuthenticated && navLink('/my-rfqs', t('nav_my_rfqs'), true)}
        {navLink('/compliance', t('nav_compliance'), true)}
        {navLink('/dpp', t('nav_dpp'), true)}
      </div>

      {/* Right -- Controls */}
      <div className="flex items-center gap-2 shrink-0">
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
            className="px-4 py-1.5 rounded-md text-xs font-semibold bg-stone-900 text-white hover:bg-stone-800 transition"
          >
            {t('nav_login')}
          </Link>
        )}
      </div>
    </nav>
  )
}
