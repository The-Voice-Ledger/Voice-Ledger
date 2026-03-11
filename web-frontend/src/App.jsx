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

export default function App() {
  const { pathname } = useLocation()
  const hideFooter = pathname === '/assistant'

  return (
    <div className="flex flex-col min-h-dvh bg-stone-50 text-stone-900">
      <Navbar />
      <main className="flex-1 flex flex-col">
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
      {/* Footer on all pages except Assistant (chat fills viewport) */}
      {!hideFooter && <Footer />}
    </div>
  )
}
