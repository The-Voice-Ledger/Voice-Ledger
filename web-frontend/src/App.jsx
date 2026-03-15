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
import About from './pages/About'

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
          <Route path="/about" element={<About />} />
        </Routes>
      </main>
      {pathname === '/assistant' ? <MiniFooter /> : <Footer />}
    </div>
  )
}


