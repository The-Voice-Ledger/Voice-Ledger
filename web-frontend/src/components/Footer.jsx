import { useTranslation } from 'react-i18next'

export default function Footer() {
  const { t } = useTranslation()

  return (
    <footer className="bg-stone-100 border-t border-stone-200 py-6 text-center text-xs text-stone-500 space-y-1">
      <p>{t('footer_text')}</p>
      <p className="text-stone-400">{t('powered_by')}</p>
    </footer>
  )
}
