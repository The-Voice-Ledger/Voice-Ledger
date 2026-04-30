/**
 * UATWidget — floating bug reporter for UAT sessions.
 *
 * Renders a fixed orange bug button (bottom-left). Clicking opens a panel
 * where the tester fills in category, severity, title and description.
 * The widget auto-captures page name, browser info, viewport, and the last
 * 20 JS console errors / unhandled rejections.
 *
 * Enabled only when VITE_UAT_MODE=true (set in .env.local).
 * Must be rendered inside <BrowserRouter> because it uses useLocation().
 */

import { useState } from 'react'
import { useLocation } from 'react-router-dom'
import useAuthStore from '../stores/authStore'
import { createUATIssue } from '../api/admin'

// ── Module-level error capture (runs before any component mounts) ──

const _capturedErrors = []

if (typeof window !== 'undefined') {
  const origError = console.error
  console.error = (...args) => {
    _capturedErrors.push({ ts: new Date().toISOString(), message: args.join(' ') })
    if (_capturedErrors.length > 20) _capturedErrors.shift()
    origError.apply(console, args)
  }
  window.addEventListener('error', (e) => {
    _capturedErrors.push({
      ts: new Date().toISOString(),
      message: `Uncaught: ${e.message} at ${e.filename}:${e.lineno}`,
    })
    if (_capturedErrors.length > 20) _capturedErrors.shift()
  })
  window.addEventListener('unhandledrejection', (e) => {
    _capturedErrors.push({
      ts: new Date().toISOString(),
      message: `UnhandledRejection: ${e.reason}`,
    })
    if (_capturedErrors.length > 20) _capturedErrors.shift()
  })
}

// ── Page name map — update when new routes are added ──────────────

const PAGE_NAMES = {
  '/':            'Home',
  '/assistant':   'Assistant',
  '/login':       'Login',
  '/marketplace': 'Marketplace',
  '/my-rfqs':     'My RFQs',
  '/dpp':         'DPP Viewer',
  '/compliance':  'Compliance',
  '/financing':   'Financing',
  '/tracking':    'Tracking',
  '/how-it-works':'How It Works',
  '/platform':    'Platform',
  '/admin':       'Admin',
}

const INITIAL_FORM = { category: 'bug', severity: 'minor', title: '', description: '' }

// ── Inline SVG icons (no external dependency) ─────────────────────

function BugIcon({ className }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"
      strokeLinecap="round" strokeLinejoin="round" className={className} aria-hidden="true">
      <circle cx="12" cy="11" r="4" />
      <path d="M12 7V3" />
      <path d="M8.5 9.5L5 6" />
      <path d="M15.5 9.5L19 6" />
      <path d="M2 13h4" />
      <path d="M18 13h4" />
      <path d="M5.5 18.5L8 16.5" />
      <path d="M18.5 18.5L16 16.5" />
      <path d="M8 21a4 4 0 008 0v-6H8v6z" />
    </svg>
  )
}

function CloseIcon({ className }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"
      strokeLinecap="round" strokeLinejoin="round" className={className} aria-hidden="true">
      <line x1="18" y1="6" x2="6" y2="18" />
      <line x1="6" y1="6" x2="18" y2="18" />
    </svg>
  )
}

function CheckIcon({ className }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"
      strokeLinecap="round" strokeLinejoin="round" className={className} aria-hidden="true">
      <circle cx="12" cy="12" r="9" />
      <polyline points="9 12 11.5 14.5 16 9.5" />
    </svg>
  )
}

// ── Component ─────────────────────────────────────────────────────

export default function UATWidget() {
  const { pathname } = useLocation()
  const { isAuthenticated, user } = useAuthStore()

  const [open, setOpen] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [success, setSuccess] = useState(false)
  const [error, setError] = useState(null)
  const [form, setForm] = useState(INITIAL_FORM)

  const pageName = PAGE_NAMES[pathname] || pathname

  const handleClose = () => {
    setOpen(false)
    setError(null)
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    setSubmitting(true)
    setError(null)
    try {
      await createUATIssue({
        page: pageName,
        category: form.category,
        severity: form.severity,
        title: form.title,
        description: form.description,
        context_json: {
          route: pathname,
          ...(typeof window !== 'undefined' && window.__UAT_CONTEXT__ ? window.__UAT_CONTEXT__ : {}),
          timestamp: new Date().toISOString(),
        },
        browser_info: `${navigator.userAgent} | ${window.innerWidth}x${window.innerHeight}`,
        console_errors: [..._capturedErrors],
      })
      setSuccess(true)
      setTimeout(() => {
        setSuccess(false)
        setOpen(false)
        setForm(INITIAL_FORM)
      }, 1600)
    } catch (err) {
      setError('Submission failed. Please try again.')
    } finally {
      setSubmitting(false)
    }
  }

  const field = (key, value) => setForm((f) => ({ ...f, [key]: value }))

  return (
    <>
      {/* Floating trigger button */}
      <button
        onClick={() => setOpen(true)}
        className="fixed bottom-6 left-6 z-50 w-11 h-11 rounded-full bg-orange-500 hover:bg-orange-600 active:bg-orange-700 text-white shadow-lg shadow-orange-500/30 flex items-center justify-center transition-all hover:scale-110 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-orange-400"
        title="Report a UAT issue"
        aria-label="Report UAT issue"
      >
        <BugIcon className="w-5 h-5" />
      </button>

      {/* Backdrop */}
      {open && (
        <div
          className="fixed inset-0 z-50 bg-black/25 backdrop-blur-sm"
          onClick={handleClose}
          aria-hidden="true"
        />
      )}

      {/* Panel */}
      {open && (
        <div
          role="dialog"
          aria-modal="true"
          aria-label="Report UAT Issue"
          className="fixed bottom-20 left-6 z-50 w-80 bg-white rounded-2xl shadow-2xl border border-stone-200 animate-fade-in-up overflow-hidden"
        >
          {/* Header */}
          <div className="flex items-center justify-between px-4 py-3 border-b border-stone-100">
            <div className="flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-orange-400" />
              <span className="text-sm font-semibold text-stone-900 font-display">Report UAT Issue</span>
            </div>
            <button
              onClick={handleClose}
              className="text-stone-400 hover:text-stone-700 transition rounded-md p-0.5"
              aria-label="Close"
            >
              <CloseIcon className="w-4 h-4" />
            </button>
          </div>

          {/* Success state */}
          {success ? (
            <div className="px-4 py-8 text-center">
              <CheckIcon className="w-10 h-10 text-green-500 mx-auto mb-2" />
              <p className="text-sm font-medium text-stone-700">Issue submitted. Thank you!</p>
            </div>
          ) : (
            <form onSubmit={handleSubmit} className="px-4 py-3 space-y-3">
              {/* Page context */}
              <p className="text-[11px] text-stone-400">
                Page: <span className="font-medium text-stone-600">{pageName}</span>
              </p>

              {/* Category + Severity */}
              <div className="grid grid-cols-2 gap-2">
                <div>
                  <label className="block text-xs font-medium text-stone-600 mb-1">Category</label>
                  <select
                    value={form.category}
                    onChange={(e) => field('category', e.target.value)}
                    className="w-full rounded-lg border border-stone-200 px-2 py-1.5 text-xs bg-stone-50 outline-none focus:border-stone-400 focus:ring-1 focus:ring-stone-200"
                  >
                    <option value="bug">Bug</option>
                    <option value="data">Data</option>
                    <option value="feature">Feature</option>
                    <option value="performance">Performance</option>
                    <option value="other">Other</option>
                  </select>
                </div>
                <div>
                  <label className="block text-xs font-medium text-stone-600 mb-1">Severity</label>
                  <select
                    value={form.severity}
                    onChange={(e) => field('severity', e.target.value)}
                    className="w-full rounded-lg border border-stone-200 px-2 py-1.5 text-xs bg-stone-50 outline-none focus:border-stone-400 focus:ring-1 focus:ring-stone-200"
                  >
                    <option value="cosmetic">Cosmetic</option>
                    <option value="minor">Minor</option>
                    <option value="major">Major</option>
                    <option value="blocker">Blocker</option>
                  </select>
                </div>
              </div>

              {/* Title */}
              <div>
                <label className="block text-xs font-medium text-stone-600 mb-1">Title</label>
                <input
                  type="text"
                  required
                  maxLength={120}
                  value={form.title}
                  onChange={(e) => field('title', e.target.value)}
                  placeholder="Short summary..."
                  className="w-full rounded-lg border border-stone-200 px-3 py-1.5 text-xs outline-none focus:border-stone-400 focus:ring-1 focus:ring-stone-200"
                />
              </div>

              {/* Description */}
              <div>
                <label className="block text-xs font-medium text-stone-600 mb-1">Description</label>
                <textarea
                  required
                  rows={3}
                  value={form.description}
                  onChange={(e) => field('description', e.target.value)}
                  placeholder="Steps to reproduce or details..."
                  className="w-full rounded-lg border border-stone-200 px-3 py-1.5 text-xs outline-none focus:border-stone-400 focus:ring-1 focus:ring-stone-200 resize-none"
                />
              </div>

              {/* Reporter identity */}
              {isAuthenticated && user && (
                <p className="text-[10px] text-stone-400">
                  Reporting as: {user.phone_number || user.full_name || user.name}
                </p>
              )}

              {/* Error */}
              {error && (
                <p className="text-xs text-red-600 bg-red-50 rounded-lg px-3 py-1.5">{error}</p>
              )}

              {/* Submit */}
              <button
                type="submit"
                disabled={submitting || !form.title || !form.description}
                className="w-full bg-orange-500 hover:bg-orange-600 active:bg-orange-700 text-white text-xs font-semibold rounded-lg py-2 transition disabled:opacity-50"
              >
                {submitting ? 'Submitting...' : 'Submit Issue'}
              </button>
            </form>
          )}
        </div>
      )}
    </>
  )
}
