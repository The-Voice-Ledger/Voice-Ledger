import { useState } from 'react'
import { Routes, Route, useLocation } from 'react-router-dom'
import Navbar from './components/Navbar'
import Footer from './components/Footer'
import Landing from './pages/Landing'
import Assistant from './pages/Assistant'
import Login from './pages/Login'
import Marketplace from './pages/Marketplace'
import MyRFQs from './pages/MyRFQs'
import DPPViewer from './pages/DPPViewer'
import Compliance from './pages/Compliance'
import Financing from './pages/Financing'
import Tracking from './pages/Tracking'
import LiveVoicePanel from './components/LiveVoicePanel'
import useAuthStore from './stores/authStore'

/* Lightweight footer for the chat page so it doesn't overwhelm the input */
function MiniFooter() {
  return (
    <footer className="bg-stone-100 border-t border-stone-200 py-4 text-center text-xs text-stone-400">
      © {new Date().getFullYear()} WAGA Coffee · Powered by The Voice Ledger
    </footer>
  )
}

export default function App() {
  const { pathname } = useLocation()
  const { isAuthenticated } = useAuthStore()
  const [voiceOpen, setVoiceOpen] = useState(false)

  return (
    <div className="flex flex-col min-h-dvh bg-stone-50 text-stone-900">
      <Navbar />
      <main className="flex-1">
        <Routes>
          <Route path="/" element={<Landing />} />
          <Route path="/assistant" element={<Assistant />} />
          <Route path="/login" element={<Login />} />
          <Route path="/marketplace" element={<Marketplace />} />
          <Route path="/my-rfqs" element={<MyRFQs />} />
          <Route path="/dpp" element={<DPPViewer />} />
          <Route path="/dpp/:batchId" element={<DPPViewer />} />
          <Route path="/compliance" element={<Compliance />} />
          <Route path="/financing" element={<Financing />} />
          <Route path="/tracking" element={<Tracking />} />
        </Routes>
      </main>
      {pathname === '/assistant' ? <MiniFooter /> : <Footer />}

      {/* ── LiveKit Voice ── */}
      {isAuthenticated && (
        <VoiceFAB onClick={() => setVoiceOpen(true)} />
      )}
      <LiveVoicePanel isOpen={voiceOpen} onClose={() => setVoiceOpen(false)} />
    </div>
  )
}

/* Floating action button — bottom-right mic icon */
function VoiceFAB({ onClick }) {
  return (
    <button
      onClick={onClick}
      aria-label="Open voice assistant"
      className="fixed bottom-6 right-6 z-40 w-14 h-14 rounded-full
                 bg-gradient-to-br from-emerald-500 to-green-600
                 text-white shadow-lg shadow-emerald-500/25
                 hover:shadow-emerald-500/40 hover:scale-110
                 active:scale-95 transition-all
                 flex items-center justify-center"
    >
      <svg width="22" height="22" viewBox="0 0 22 22" fill="none" stroke="currentColor"
           strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
        <rect x="8" y="3" width="6" height="10" rx="3" />
        <path d="M5 12a6 6 0 0012 0" />
        <path d="M11 18v2" />
      </svg>
    </button>
  )
}
