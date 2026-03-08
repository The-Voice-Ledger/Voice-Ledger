import { useState } from 'react'
import { useNavigate, Link, Navigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import useAuthStore from '../stores/authStore'

const WAGA_LOGO = 'https://violet-rainy-toad-577.mypinata.cloud/ipfs/bafybeic6pclaqgbaaz6qqvlz2ssjgbzae4y7e76d2pobbwfxs2cviwgyqa'
import { login as apiLogin } from '../api/agent'

export default function Login() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const { login, isAuthenticated } = useAuthStore()
  const [phone, setPhone] = useState('')
  const [pin, setPin] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  // Redirect if already authenticated
  if (isAuthenticated) {
    return <Navigate to="/assistant" replace />
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      const data = await apiLogin(phone, pin)
      if (!data.success) {
        setError(data.message || t('login_error'))
        return
      }
      login(data.token, data.user)
      navigate('/assistant')
    } catch {
      setError(t('login_error'))
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-[calc(100dvh-4rem)] flex items-center justify-center px-4">
      <div className="w-full max-w-sm">
        <div className="text-center mb-8">
          <img src={WAGA_LOGO} alt="WAGA Coffee" className="h-12 mx-auto mb-2" />
          <h1 className="text-2xl font-bold text-stone-900">{t('login_title')}</h1>
          <p className="text-sm text-stone-500 mt-1">
            {t('login_subtitle')}
          </p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-stone-700 mb-1">
              {t('login_phone')}
            </label>
            <input
              type="tel"
              value={phone}
              onChange={(e) => setPhone(e.target.value)}
              placeholder="+251..."
              required
              className="w-full rounded-lg border border-stone-300 px-4 py-2.5 text-sm outline-none focus:border-stone-400 focus:ring-2 focus:ring-stone-200 transition"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-stone-700 mb-1">
              {t('login_pin')}
            </label>
            <input
              type="password"
              inputMode="numeric"
              maxLength={4}
              value={pin}
              onChange={(e) => setPin(e.target.value.replace(/\D/g, ''))}
              placeholder="••••"
              required
              className="w-full rounded-lg border border-stone-300 px-4 py-2.5 text-sm text-center tracking-[0.5em] outline-none focus:border-stone-400 focus:ring-2 focus:ring-stone-200 transition"
            />
          </div>

          {error && (
            <div className="text-sm text-red-600 bg-red-50 rounded-lg p-2.5 text-center">
              {error}
            </div>
          )}

          <button
            type="submit"
            disabled={loading || !phone || pin.length < 4}
            className="w-full bg-stone-900 text-white font-semibold rounded-lg py-2.5 hover:bg-stone-800 transition disabled:opacity-50"
          >
            {loading ? '...' : t('login_submit')}
          </button>
        </form>

        <div className="mt-6 space-y-3">
          <div className="bg-stone-50 border border-stone-200 rounded-lg p-3 text-center">
            <p className="text-xs text-stone-500">{t('login_no_account')}</p>
            <a
              href="https://t.me/voice_ledger_bot"
              target="_blank"
              rel="noreferrer"
              className="inline-flex items-center gap-1.5 mt-2 text-sm font-medium text-blue-600 hover:text-blue-700 transition"
            >
              <svg className="w-4 h-4" viewBox="0 0 24 24" fill="currentColor"><path d="M11.944 0A12 12 0 0 0 0 12a12 12 0 0 0 12 12 12 12 0 0 0 12-12A12 12 0 0 0 12 0a12 12 0 0 0-.056 0zm4.962 7.224c.1-.002.321.023.465.14a.506.506 0 0 1 .171.325c.016.093.036.306.02.472-.18 1.898-.962 6.502-1.36 8.627-.168.9-.499 1.201-.82 1.23-.696.065-1.225-.46-1.9-.902-1.056-.693-1.653-1.124-2.678-1.8-1.185-.78-.417-1.21.258-1.91.177-.184 3.247-2.977 3.307-3.23.007-.032.014-.15-.056-.212s-.174-.041-.249-.024c-.106.024-1.793 1.14-5.061 3.345-.48.33-.913.49-1.302.48-.428-.008-1.252-.241-1.865-.44-.752-.245-1.349-.374-1.297-.789.027-.216.325-.437.893-.663 3.498-1.524 5.83-2.529 6.998-3.014 3.332-1.386 4.025-1.627 4.476-1.635z"/></svg>
              {t('login_register_telegram')}
            </a>
          </div>
          <p className="text-center text-xs text-stone-400">
            {t('login_or_anonymous')}{' '}
            <Link to="/assistant" className="text-stone-600 underline">
              {t('login_chat_anon')}
            </Link>
          </p>
        </div>
      </div>
    </div>
  )
}
