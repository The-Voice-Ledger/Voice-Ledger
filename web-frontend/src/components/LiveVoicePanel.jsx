/**
 * LiveVoicePanel — Full-screen LiveKit voice overlay for The Voice Ledger.
 *
 * Themed to match the Landing page hero:
 *  - Dark gradient bg (stone-900 → stone-950) with floating blurred orbs
 *  - Constellation-style ambient SVG
 *  - WAGA logo in the top bar
 *  - State-driven color palette on the central orb
 *  - Mute + End call controls
 *  - Live transcript & action cards
 */

import { useState, useEffect, useRef, useMemo, useCallback } from 'react'
import {
  SessionProvider,
  useSession,
  useVoiceAssistant,
  useAgent,
  BarVisualizer,
  RoomAudioRenderer,
  useTextStream,
} from '@livekit/components-react'
import { TokenSource } from 'livekit-client'
import useAuthStore from '../stores/authStore'
import { getLiveKitToken } from '../api/livekit'
import ActionCards from './ActionCards'

const WAGA_LOGO =
  'https://violet-rainy-toad-577.mypinata.cloud/ipfs/bafybeic6pclaqgbaaz6qqvlz2ssjgbzae4y7e76d2pobbwfxs2cviwgyqa'

/* ================================================================
   Color system — state-driven palette
   ================================================================ */

const STATE_COLORS = {
  disconnected: { ring: '#6B7280', dot: '#9CA3AF', glow: 'rgba(107,114,128,0.15)' },
  connecting:   { ring: '#F59E0B', dot: '#FBBF24', glow: 'rgba(245,158,11,0.2)' },
  initializing: { ring: '#F59E0B', dot: '#FBBF24', glow: 'rgba(245,158,11,0.2)' },
  idle:         { ring: '#10B981', dot: '#34D399', glow: 'rgba(16,185,129,0.2)' },
  listening:    { ring: '#10B981', dot: '#34D399', glow: 'rgba(16,185,129,0.35)' },
  thinking:     { ring: '#8B5CF6', dot: '#A78BFA', glow: 'rgba(139,92,246,0.25)' },
  speaking:     { ring: '#06B6D4', dot: '#22D3EE', glow: 'rgba(6,182,212,0.3)' },
  failed:       { ring: '#EF4444', dot: '#F87171', glow: 'rgba(239,68,68,0.2)' },
}

const STATE_LABELS = {
  disconnected: 'Disconnected',
  connecting:   'Connecting…',
  initializing: 'Starting up…',
  idle:         'Ready',
  listening:    'Listening…',
  thinking:     'Thinking…',
  speaking:     'Speaking…',
  failed:       'Connection failed',
}

const PULSING_STATES = new Set(['listening', 'connecting', 'thinking'])

/* ================================================================
   Outer wrapper — manages token + session
   ================================================================ */

export default function LiveVoicePanel({ isOpen, onClose }) {
  const { user } = useAuthStore()

  const tokenSource = useMemo(
    () =>
      TokenSource.custom(async () => {
        const data = await getLiveKitToken({
          userId: user?.id?.toString() || 'anonymous',
          userName: user?.full_name || 'Guest',
          userRole: user?.role || 'user',
          userDid: user?.did || null,
        })
        return { participantToken: data.token, serverUrl: data.url }
      }),
    [user?.id, user?.full_name, user?.role],
  )

  const session = useSession(tokenSource)

  if (!isOpen) return null

  return (
    <SessionProvider session={session}>
      <VoicePanelOverlay
        session={session}
        onClose={onClose}
        userName={user?.full_name || 'Guest'}
      />
    </SessionProvider>
  )
}

/* ================================================================
   The overlay — hero-themed, orb, transcript, action cards, controls
   ================================================================ */

function VoicePanelOverlay({ session, onClose, userName }) {
  const { state: agentState, audioTrack, agentTranscriptions } = useVoiceAssistant()
  useAgent() // keep the agent connection alive
  const transcriptions = agentTranscriptions || []

  const { textStreams: actionStreams } = useTextStream('vl.action')

  const [isStarted, setIsStarted] = useState(false)
  const [isMuted, setIsMuted] = useState(false)
  const [showTranscript, setShowTranscript] = useState(false)
  const [showActions, setShowActions] = useState(true)
  const [connectError, setConnectError] = useState(null)
  const [splitPct, setSplitPct] = useState(45) // left panel percentage
  const transcriptRef = useRef(null)
  const actionsRef = useRef(null)
  const containerRef = useRef(null)
  const isDragging = useRef(false)

  const colors = STATE_COLORS[agentState] || STATE_COLORS.disconnected
  const isPulsing = PULSING_STATES.has(agentState)

  // Auto-scroll transcript
  useEffect(() => {
    if (transcriptRef.current) {
      transcriptRef.current.scrollTop = transcriptRef.current.scrollHeight
    }
  }, [transcriptions])

  // Auto-show transcript when greeting arrives
  useEffect(() => {
    if (transcriptions.length > 0 && !showTranscript) {
      setShowTranscript(true)
    }
  }, [transcriptions.length])

  // Auto-show & auto-scroll actions
  useEffect(() => {
    if (actionsRef.current) {
      actionsRef.current.scrollTop = actionsRef.current.scrollHeight
    }
    if (actionStreams?.length > 0) setShowActions(true)
  }, [actionStreams])

  // Track started state
  useEffect(() => {
    if (agentState !== 'disconnected' && agentState !== 'connecting') {
      setIsStarted(true)
    }
  }, [agentState])

  // Resizable divider drag handling
  const handleDragStart = useCallback((e) => {
    e.preventDefault()
    isDragging.current = true
  }, [])

  useEffect(() => {
    const handleMove = (e) => {
      if (!isDragging.current || !containerRef.current) return
      const rect = containerRef.current.getBoundingClientRect()
      const clientX = e.touches ? e.touches[0].clientX : e.clientX
      const pct = ((clientX - rect.left) / rect.width) * 100
      setSplitPct(Math.min(Math.max(pct, 25), 75))
    }
    const handleUp = () => { isDragging.current = false }
    window.addEventListener('mousemove', handleMove)
    window.addEventListener('mouseup', handleUp)
    window.addEventListener('touchmove', handleMove)
    window.addEventListener('touchend', handleUp)
    return () => {
      window.removeEventListener('mousemove', handleMove)
      window.removeEventListener('mouseup', handleUp)
      window.removeEventListener('touchmove', handleMove)
      window.removeEventListener('touchend', handleUp)
    }
  }, [])

  const handleStart = useCallback(async () => {
    try {
      setConnectError(null)
      console.log('[VoiceLedger] Starting voice session...')
      await session.start({ tracks: { microphone: { enabled: true } } })
      console.log('[VoiceLedger] Session connected!')
    } catch (err) {
      console.error('[VoiceLedger] session.start() failed:', err)
      setConnectError(err.message || 'Failed to connect. Check microphone permissions.')
    }
  }, [session])

  const handleEnd = useCallback(() => {
    session.end()
    setIsStarted(false)
    onClose()
  }, [session, onClose])

  const handleMuteToggle = useCallback(() => {
    // Toggle local audio track mute via the session's room
    try {
      const room = session?.room
      if (room?.localParticipant) {
        const mic = room.localParticipant.getTrackPublication('microphone')
        if (mic?.track) {
          if (isMuted) {
            mic.track.unmute()
          } else {
            mic.track.mute()
          }
        }
      }
    } catch (e) {
      // fallback — just toggle UI state
    }
    setIsMuted((m) => !m)
  }, [session, isMuted])

  return (
    <div className="fixed inset-0 z-50 flex flex-col overflow-hidden">
      {/* ── Landing-hero-style background ── */}
      <div className="absolute inset-0 bg-gradient-to-br from-stone-900 via-stone-800 to-stone-950" />

      {/* Floating gradient orbs (same as Landing hero) */}
      <div className="absolute inset-0 overflow-hidden pointer-events-none" aria-hidden>
        <div
          className="absolute -top-24 -left-24 w-96 h-96 rounded-full blur-3xl animate-float-slow"
          style={{ backgroundColor: `${colors.ring}20` }}
        />
        <div
          className="absolute top-1/3 -right-32 w-80 h-80 rounded-full blur-3xl animate-float-slower"
          style={{ backgroundColor: 'rgba(37, 140, 37, 0.08)' }}
        />
        <div
          className="absolute -bottom-16 left-1/3 w-72 h-72 rounded-full blur-3xl animate-float-slow"
          style={{ backgroundColor: 'rgba(192, 142, 66, 0.06)', animationDelay: '3s' }}
        />
      </div>

      {/* Subtle grid pattern */}
      <div className="absolute inset-0 opacity-[0.04] bg-[url('data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iNjAiIGhlaWdodD0iNjAiIHZpZXdCb3g9IjAgMCA2MCA2MCIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj48ZyBmaWxsPSJub25lIiBmaWxsLXJ1bGU9ImV2ZW5vZGQiPjxnIGZpbGw9IiNmZmYiIGZpbGwtb3BhY2l0eT0iMC4xIj48cGF0aCBkPSJNMzYgMzRoLTJ2LTRoMnYtMmgtNHY2aDR2LTJ6bTAtMTZ2Mmg0di02aC00djRoLTJ2Mmgyem0tOCA4aDJ2NmgtMnYyaDR2LTZoMnYtMmgtNHYtMnptMC0ydi0ySDI0djJoMnYyaDJ2LTJ6Ii8+PC9nPjwvZz48L3N2Zz4=')]" />

      {/* SVG ambient background */}
      <AmbientBackground colors={colors} />

      {/* Required: renders hidden <audio> for agent playback */}
      <RoomAudioRenderer />

      {/* ── Top bar ── */}
      <div className="relative z-10 w-full flex items-center justify-between px-5 py-4 flex-shrink-0">
        <div className="flex items-center gap-3">
          <div className="relative">
            <svg className="absolute -inset-2 w-[calc(100%+16px)] h-[calc(100%+16px)]" viewBox="0 0 56 56" fill="none">
              <rect x="2" y="2" width="52" height="52" rx="16" stroke="url(#panel-logo-grad)" strokeWidth="0.6" strokeDasharray="3 7" opacity="0.35">
                <animateTransform attributeName="transform" type="rotate" from="0 28 28" to="360 28 28" dur="18s" repeatCount="indefinite" />
              </rect>
              <circle cx="6" cy="6" r="1" fill="#10B981" opacity="0.4">
                <animate attributeName="opacity" values="0.2;0.6;0.2" dur="3s" repeatCount="indefinite" />
              </circle>
              <circle cx="50" cy="50" r="1" fill="#06B6D4" opacity="0.3">
                <animate attributeName="opacity" values="0.3;0.6;0.3" dur="4s" repeatCount="indefinite" />
              </circle>
              <defs>
                <linearGradient id="panel-logo-grad" x1="0" y1="0" x2="56" y2="56">
                  <stop offset="0%" stopColor="#10B981" />
                  <stop offset="50%" stopColor="#06B6D4" />
                  <stop offset="100%" stopColor="#8B5CF6" />
                </linearGradient>
              </defs>
            </svg>
            <img src={WAGA_LOGO} alt="WAGA" className="h-8 w-auto rounded-xl" />
          </div>
          <div className="flex flex-col">
            <span className="text-sm font-semibold text-white/85 tracking-wide font-display">
              The Voice Ledger
            </span>
            <span className="text-[10px] text-white/30 font-mono tracking-wider">
              voice assistant
            </span>
          </div>
        </div>
        <button
          onClick={onClose}
          className="w-9 h-9 rounded-xl flex items-center justify-center text-white/30 hover:text-white/70 hover:bg-white/5 transition-all duration-200"
        >
          <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
            <path d="M4 4l8 8M12 4l-8 8" />
          </svg>
        </button>
      </div>

      {/* ── Split panel body ── */}
      <div ref={containerRef} className="relative z-10 flex-1 flex min-h-0">
        {/* ── LEFT PANEL: Orb + Controls ── */}
        <div
          className="flex flex-col items-center justify-center relative"
          style={{ width: `${splitPct}%` }}
        >
          {/* Central orb */}
          <div
            className="relative flex items-center justify-center transition-all duration-1000"
            style={{
              width: 'min(16rem, 60%)',
              aspectRatio: '1',
              borderRadius: '50%',
              boxShadow: `0 0 60px 12px ${colors.glow}, 0 0 120px 24px ${colors.glow}`,
              opacity: agentState === 'speaking' || agentState === 'listening' ? 0.7 : 0.25,
            }}
          >
            <OrbSVG colors={colors} agentState={agentState} />
            <div className="absolute inset-0 flex items-center justify-center">
              {isStarted && audioTrack ? (
                <BarVisualizer state={agentState} barCount={7} trackRef={audioTrack} className="lk-voice-bars" />
              ) : (
                <IdleMicIcon />
              )}
            </div>
          </div>

          {/* State label + dot */}
          <div className="mt-6 flex flex-col items-center gap-1.5">
            <div className="flex items-center gap-2">
              <div
                className={`w-2 h-2 rounded-full ${isPulsing ? 'animate-pulse-dot' : ''}`}
                style={{ backgroundColor: colors.dot, boxShadow: `0 0 8px ${colors.glow}` }}
              />
              <span className="text-sm font-medium tracking-wide" style={{ color: colors.dot }}>
                {STATE_LABELS[agentState] || 'Unknown'}
              </span>
            </div>
            {isStarted && (
              <span className="text-[11px] text-white/20 font-mono tracking-wide">
                {userName} • live session
              </span>
            )}
          </div>

          {/* Controls */}
          <div className="mt-8 flex flex-col items-center gap-3">
            {connectError && (
              <div className="mb-2 px-4 py-2 rounded-xl bg-red-500/10 border border-red-500/20 text-red-300 text-xs text-center max-w-xs">
                {connectError}
              </div>
            )}

            {!isStarted ? (
              <button
                onClick={handleStart}
                className="group relative px-8 py-4 rounded-2xl bg-gradient-to-br from-emerald-500 to-green-600 text-white font-semibold text-sm shadow-lg shadow-emerald-500/20 hover:shadow-emerald-500/40 hover:scale-105 active:scale-95 transition-all"
              >
                <div className="absolute -inset-px rounded-2xl bg-gradient-to-br from-emerald-400/20 to-green-400/20 opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none" />
                <span className="relative flex items-center gap-2">
                  <svg width="18" height="18" viewBox="0 0 18 18" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
                    <rect x="7" y="3" width="4" height="8" rx="2" />
                    <path d="M5 10a4 4 0 008 0" />
                    <path d="M9 14v2" />
                  </svg>
                  Start Voice Session
                </span>
              </button>
            ) : (
              <div className="flex items-center gap-4">
                <button
                  onClick={handleMuteToggle}
                  className={`w-14 h-14 rounded-full flex items-center justify-center transition-all duration-200 ${
                    isMuted
                      ? 'bg-amber-500/20 text-amber-400 ring-1 ring-amber-400/30'
                      : 'bg-white/8 text-white/70 hover:bg-white/12 hover:text-white/90'
                  }`}
                  title={isMuted ? 'Unmute microphone' : 'Mute microphone'}
                >
                  {isMuted ? (
                    <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
                      <line x1="1" y1="1" x2="23" y2="23" />
                      <path d="M9 9v3a3 3 0 005.12 2.12M15 9.34V4a3 3 0 00-5.94-.6" />
                      <path d="M17 16.95A7 7 0 015 12" />
                      <path d="M19 12a7 7 0 01-.11 1.23" />
                      <line x1="12" y1="19" x2="12" y2="23" />
                      <line x1="8" y1="23" x2="16" y2="23" />
                    </svg>
                  ) : (
                    <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
                      <rect x="9" y="2" width="6" height="11" rx="3" />
                      <path d="M5 12a7 7 0 0014 0" />
                      <line x1="12" y1="19" x2="12" y2="23" />
                      <line x1="8" y1="23" x2="16" y2="23" />
                    </svg>
                  )}
                </button>
                <button
                  onClick={handleEnd}
                  className="w-14 h-14 rounded-full flex items-center justify-center bg-red-500/15 text-red-400 hover:bg-red-500/25 hover:text-red-300 hover:scale-105 active:scale-95 transition-all duration-200 ring-1 ring-red-500/10 hover:ring-red-500/20"
                  title="End voice session"
                >
                  <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M10.68 13.31a16 16 0 003.41 2.6l1.27-1.27a2 2 0 012.11-.45 12.84 12.84 0 002.73.8 2 2 0 011.72 2v3a2 2 0 01-2.18 2 19.79 19.79 0 01-8.63-3.07 19.42 19.42 0 01-6-6A19.79 19.79 0 012 4.18 2 2 0 014 2h3a2 2 0 012 1.72 12.84 12.84 0 00.7 2.81 2 2 0 01-.45 2.11L8.09 9.91a16 16 0 002.59 3.4z" />
                    <line x1="1" y1="1" x2="23" y2="23" />
                  </svg>
                </button>
              </div>
            )}

            {isStarted && isMuted && (
              <span className="text-[10px] text-amber-400/60 font-mono tracking-wider animate-pulse">
                microphone muted
              </span>
            )}
          </div>

          {/* Footer */}
          <div className="mt-6 flex flex-col items-center gap-1">
            <span className="text-[9px] text-white/15 font-display tracking-wide">The Voice Ledger</span>
            <span className="text-[8px] text-white/8 font-mono tracking-wider">Powered by LiveKit • Deepgram • OpenAI</span>
          </div>
        </div>

        {/* ── Draggable divider ── */}
        <div
          className="relative z-20 flex-shrink-0 group cursor-col-resize select-none"
          style={{ width: '12px' }}
          onMouseDown={handleDragStart}
          onTouchStart={handleDragStart}
        >
          <div className="absolute inset-y-0 left-1/2 -translate-x-1/2 w-px bg-white/10 group-hover:bg-emerald-400/30 transition-colors" />
          <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-5 h-10 rounded-full bg-white/5 group-hover:bg-emerald-400/10 border border-white/10 group-hover:border-emerald-400/20 flex items-center justify-center transition-all">
            <div className="flex flex-col gap-0.5">
              <div className="w-0.5 h-0.5 rounded-full bg-white/30 group-hover:bg-emerald-400/60" />
              <div className="w-0.5 h-0.5 rounded-full bg-white/30 group-hover:bg-emerald-400/60" />
              <div className="w-0.5 h-0.5 rounded-full bg-white/30 group-hover:bg-emerald-400/60" />
            </div>
          </div>
        </div>

        {/* ── RIGHT PANEL: Data — Welcome cards, Transcript, Action Cards ── */}
        <div
          className="flex flex-col min-h-0 overflow-y-auto scrollbar-thin px-4 py-3 gap-4"
          style={{ width: `${100 - splitPct}%` }}
        >
          {/* Welcome capability cards — shown before actions arrive */}
          {(!actionStreams || actionStreams.length === 0) && (
            <WelcomeCards isStarted={isStarted} />
          )}

          {/* Transcript */}
          {isStarted && transcriptions.length > 0 && (
            <div className="w-full">
              <button
                onClick={() => setShowTranscript((v) => !v)}
                className="w-full flex items-center gap-1.5 text-[11px] text-white/25 hover:text-white/45 transition-colors mb-2"
              >
                <svg width="12" height="12" viewBox="0 0 12 12" fill="none" stroke="currentColor" strokeWidth="1">
                  <path d="M2 4h8M2 6h6M2 8h7" />
                </svg>
                {showTranscript ? 'Hide transcript' : 'Show transcript'}
                <span className="ml-auto text-[9px] text-white/15">
                  {transcriptions.length} segment{transcriptions.length !== 1 ? 's' : ''}
                </span>
              </button>
              {showTranscript && (
                <div
                  ref={transcriptRef}
                  className="max-h-48 overflow-y-auto rounded-xl px-4 py-3 space-y-1.5 scrollbar-thin"
                  style={{
                    background: 'rgba(255,255,255,0.04)',
                    border: '1px solid rgba(255,255,255,0.06)',
                    backdropFilter: 'blur(8px)',
                  }}
                >
                  {transcriptions.map((seg, i) => (
                    <p key={seg.id || i} className="text-xs leading-relaxed text-emerald-300/60">
                      <span className="font-mono text-[9px] text-white/15 mr-1.5">AI</span>
                      {seg.text}
                    </p>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* Action cards */}
          {isStarted && actionStreams?.length > 0 && (
            <div className="w-full">
              <button
                onClick={() => setShowActions((v) => !v)}
                className="w-full flex items-center gap-1.5 text-[11px] text-white/25 hover:text-white/45 transition-colors mb-2"
              >
                {showActions ? 'Hide actions' : `Show actions (${actionStreams.length})`}
              </button>
              {showActions && (
                <div ref={actionsRef} className="overflow-y-auto scrollbar-thin">
                  <ActionCards textStreams={actionStreams} />
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

/* ================================================================
   Welcome capability cards — premium SVG tech design matching hero theme
   ================================================================ */

const CAPABILITY_GROUPS = [
  {
    key: 'supply',
    title: 'Supply Chain',
    accent: '#10B981',
    items: ['Record batches & shipments', 'Track transformations', 'Pack & split batches'],
    // Circuit-trace SVG icon
    svgIcon: (color) => (
      <svg width="28" height="28" viewBox="0 0 28 28" fill="none">
        <rect x="1" y="1" width="26" height="26" rx="6" stroke={color} strokeWidth="0.6" strokeOpacity="0.3" />
        <path d="M7 14h4l2-3h2l2 6h2l2-3h3" stroke={color} strokeWidth="1.2" strokeLinecap="round" strokeLinejoin="round" opacity="0.8" />
        <circle cx="7" cy="14" r="1.5" fill={color} opacity="0.6" />
        <circle cx="24" cy="14" r="1.5" fill={color} opacity="0.6" />
        <path d="M7 8h3v2" stroke={color} strokeWidth="0.5" opacity="0.3" />
        <path d="M21 20h-3v-2" stroke={color} strokeWidth="0.5" opacity="0.3" />
      </svg>
    ),
    // Card background pattern
    bgPattern: (color) => (
      <g stroke={color} strokeWidth="0.4" fill="none" opacity="0.08">
        <path d="M0 30h40 M40 30v20 M40 50h30" />
        <path d="M130 10h-30 M100 10v25" />
        <circle cx="40" cy="30" r="2" fill={color} opacity="0.15" />
        <circle cx="100" cy="10" r="1.5" fill={color} opacity="0.1" />
        <circle cx="40" cy="50" r="1.5" fill={color} opacity="0.1" />
      </g>
    ),
  },
  {
    key: 'market',
    title: 'Marketplace',
    accent: '#06B6D4',
    items: ['Create & browse RFQs', 'Submit & accept offers', 'Shared buying pools'],
    svgIcon: (color) => (
      <svg width="28" height="28" viewBox="0 0 28 28" fill="none">
        <rect x="1" y="1" width="26" height="26" rx="6" stroke={color} strokeWidth="0.6" strokeOpacity="0.3" />
        <rect x="8" y="9" width="12" height="10" rx="2" stroke={color} strokeWidth="1" opacity="0.7" />
        <path d="M10 14h8M10 17h5" stroke={color} strokeWidth="0.8" strokeLinecap="round" opacity="0.5" />
        <circle cx="20" cy="9" r="3" stroke={color} strokeWidth="0.8" fill="none" opacity="0.5" />
        <path d="M19 9l1 1 2-2" stroke={color} strokeWidth="0.8" strokeLinecap="round" strokeLinejoin="round" opacity="0.7" />
      </svg>
    ),
    bgPattern: (color) => (
      <g opacity="0.06">
        {[15,35,55,75,95,115].map((x) => (
          <g key={x}>
            {[15,35,55].map((y) => (
              <circle key={`${x}-${y}`} cx={x} cy={y} r="0.8" fill={color} />
            ))}
          </g>
        ))}
        <line x1="15" y1="15" x2="35" y2="35" stroke={color} strokeWidth="0.3" />
        <line x1="75" y1="15" x2="95" y2="35" stroke={color} strokeWidth="0.3" />
        <line x1="55" y1="35" x2="75" y2="55" stroke={color} strokeWidth="0.3" />
      </g>
    ),
  },
  {
    key: 'compliance',
    title: 'Compliance',
    accent: '#8B5CF6',
    items: ['EUDR deforestation checks', 'Mass balance verification', 'Digital Product Passports'],
    svgIcon: (color) => (
      <svg width="28" height="28" viewBox="0 0 28 28" fill="none">
        <rect x="1" y="1" width="26" height="26" rx="6" stroke={color} strokeWidth="0.6" strokeOpacity="0.3" />
        <path d="M14 6l7 3v5c0 4.5-3 8-7 10-4-2-7-5.5-7-10V9l7-3z" stroke={color} strokeWidth="1" fill="none" opacity="0.6" />
        <path d="M11 14l2 2 4-4" stroke={color} strokeWidth="1.2" strokeLinecap="round" strokeLinejoin="round" opacity="0.8" />
      </svg>
    ),
    bgPattern: (color) => {
      const hexes = []
      const r = 8
      for (let row = 0; row < 4; row++) {
        for (let col = 0; col < 8; col++) {
          const cx = col * 18 + (row % 2 ? 9 : 0)
          const cy = row * 16 + 8
          const pts = Array.from({ length: 6 }, (_, k) => {
            const a = (Math.PI / 3) * k - Math.PI / 6
            return `${cx + r * Math.cos(a)},${cy + r * Math.sin(a)}`
          }).join(' ')
          hexes.push(<polygon key={`${row}-${col}`} points={pts} stroke={color} strokeWidth="0.3" fill="none" opacity="0.06" />)
        }
      }
      return <g>{hexes}</g>
    },
  },
  {
    key: 'blockchain',
    title: 'Blockchain',
    accent: '#F59E0B',
    items: ['On-chain anchoring', 'Chainlink DON attestations', 'Hash verification'],
    svgIcon: (color) => (
      <svg width="28" height="28" viewBox="0 0 28 28" fill="none">
        <rect x="1" y="1" width="26" height="26" rx="6" stroke={color} strokeWidth="0.6" strokeOpacity="0.3" />
        <rect x="5" y="10" width="6" height="8" rx="1.5" stroke={color} strokeWidth="0.8" opacity="0.6" />
        <rect x="11" y="10" width="6" height="8" rx="1.5" stroke={color} strokeWidth="0.8" opacity="0.6" />
        <rect x="17" y="10" width="6" height="8" rx="1.5" stroke={color} strokeWidth="0.8" opacity="0.6" />
        <line x1="11" y1="14" x2="11" y2="14" stroke={color} strokeWidth="1.5" strokeLinecap="round" opacity="0.5" />
        <line x1="17" y1="14" x2="17" y2="14" stroke={color} strokeWidth="1.5" strokeLinecap="round" opacity="0.5" />
        <circle cx="8" cy="14" r="1" fill={color} opacity="0.5" />
        <circle cx="14" cy="14" r="1" fill={color} opacity="0.5" />
        <circle cx="20" cy="14" r="1" fill={color} opacity="0.5" />
      </svg>
    ),
    bgPattern: (color) => {
      const links = []
      for (let i = 0; i < 7; i++) {
        const x = 8 + i * 18
        const y = 32 + (i % 2 ? -6 : 6)
        links.push(
          <rect key={i} x={x - 5} y={y - 7} width="10" height="14" rx="5" stroke={color} strokeWidth="0.5" fill="none" opacity="0.06" />
        )
        if (i < 6) {
          const nx = 8 + (i + 1) * 18
          const ny = 32 + ((i + 1) % 2 ? -6 : 6)
          links.push(<line key={`c${i}`} x1={x + 5} y1={y} x2={nx - 5} y2={ny} stroke={color} strokeWidth="0.3" opacity="0.05" />)
        }
      }
      return <g>{links}</g>
    },
  },
  {
    key: 'settlement',
    title: 'Settlement',
    accent: '#EC4899',
    items: ['Confirm payments', 'Cooperative payouts', 'Trade financing & DeFi'],
    svgIcon: (color) => (
      <svg width="28" height="28" viewBox="0 0 28 28" fill="none">
        <rect x="1" y="1" width="26" height="26" rx="6" stroke={color} strokeWidth="0.6" strokeOpacity="0.3" />
        <path d="M8 20V12M12 20V10M16 20V14M20 20V8" stroke={color} strokeWidth="1.5" strokeLinecap="round" opacity="0.6" />
        <path d="M7 12l4-2 4 4 5-6" stroke={color} strokeWidth="0.8" fill="none" strokeLinecap="round" strokeLinejoin="round" opacity="0.4" />
      </svg>
    ),
    bgPattern: (color) => (
      <g opacity="0.05">
        {[10, 25, 40, 55, 70, 85, 100, 115].map((x, i) => (
          <rect key={i} x={x} y={60 - i * 5 - Math.random() * 10} width="8" height={10 + i * 5} rx="1" fill={color} opacity="0.4" />
        ))}
        <polyline points="14,55 29,48 44,52 59,42 74,46 89,35 104,30 119,22" stroke={color} strokeWidth="0.5" fill="none" opacity="0.3" />
      </g>
    ),
  },
  {
    key: 'traceability',
    title: 'Traceability',
    accent: '#14B8A6',
    items: ['Full bean-to-cup lineage', 'Container DPPs', 'Batch verification'],
    svgIcon: (color) => (
      <svg width="28" height="28" viewBox="0 0 28 28" fill="none">
        <rect x="1" y="1" width="26" height="26" rx="6" stroke={color} strokeWidth="0.6" strokeOpacity="0.3" />
        <circle cx="14" cy="14" r="6" stroke={color} strokeWidth="0.8" fill="none" opacity="0.5" />
        <circle cx="14" cy="14" r="3" stroke={color} strokeWidth="0.8" fill="none" opacity="0.4" />
        <circle cx="14" cy="14" r="1" fill={color} opacity="0.7" />
        <path d="M14 5v3M14 20v3M5 14h3M20 14h3" stroke={color} strokeWidth="0.6" opacity="0.3" />
        <path d="M8.5 8.5l2 2M17.5 17.5l2 2M8.5 19.5l2-2M17.5 8.5l2-2" stroke={color} strokeWidth="0.4" opacity="0.2" />
      </svg>
    ),
    bgPattern: (color) => (
      <g opacity="0.06">
        <path d="M10 50 Q30 30 60 35 Q90 40 100 20 Q110 5 130 15" stroke={color} strokeWidth="0.8" fill="none" strokeDasharray="3 4" strokeLinecap="round" />
        {[[10,50],[60,35],[100,20],[130,15]].map(([cx,cy], i) => (
          <g key={i}>
            <circle cx={cx} cy={cy} r="3" stroke={color} strokeWidth="0.4" fill="none" />
            <circle cx={cx} cy={cy} r="1" fill={color} />
          </g>
        ))}
      </g>
    ),
  },
]

/* ── SVG background for each capability card ── */
function CapabilityCardBg({ pattern, accent }) {
  return (
    <svg
      className="absolute inset-0 w-full h-full pointer-events-none"
      viewBox="0 0 140 70"
      preserveAspectRatio="xMidYMid slice"
      fill="none"
    >
      {pattern(accent)}
    </svg>
  )
}

/* ── Animated trace border for cards ── */
function TraceBorder({ accent, index = 0 }) {
  return (
    <svg
      className="absolute inset-0 w-full h-full pointer-events-none"
      viewBox="0 0 200 100"
      preserveAspectRatio="none"
      fill="none"
    >
      {/* Static dim border */}
      <rect x="1" y="1" width="198" height="98" rx="11" stroke={accent} strokeWidth="0.5" strokeOpacity="0.1" />
      {/* Animated trace that races around the border */}
      <rect
        x="1" y="1" width="198" height="98" rx="11"
        stroke={accent} strokeWidth="1" strokeOpacity="0"
        strokeDasharray="60 540"
        className="animate-card-trace"
        style={{ animationDelay: `${index * 0.6}s` }}
      />
      {/* Corner accents */}
      <circle cx="12" cy="12" r="1" fill={accent} opacity="0.15" />
      <circle cx="188" cy="12" r="1" fill={accent} opacity="0.15" />
      <circle cx="12" cy="88" r="1" fill={accent} opacity="0.1" />
      <circle cx="188" cy="88" r="1" fill={accent} opacity="0.1" />
    </svg>
  )
}

function WelcomeCards({ isStarted }) {
  return (
    <div className="w-full">
      {/* Section header with tech accent */}
      <div className="mb-4 flex items-center gap-3">
        <div className="relative">
          <div className="w-1 h-5 rounded-full bg-gradient-to-b from-emerald-400 via-cyan-400 to-purple-400" />
          <div className="absolute -inset-1 w-3 h-7 rounded-full bg-emerald-400/10 blur-sm" />
        </div>
        <div className="flex items-center gap-2">
          <span className="text-xs font-semibold text-white/60 tracking-widest uppercase">
            {isStarted ? 'Capabilities' : 'What I can do'}
          </span>
          <svg width="40" height="1" className="text-white/10">
            <line x1="0" y1="0.5" x2="40" y2="0.5" stroke="currentColor" strokeWidth="1" strokeDasharray="2 3" />
          </svg>
        </div>
      </div>

      {!isStarted && (
        <div className="mb-4 relative rounded-xl overflow-hidden" style={{ background: 'rgba(255,255,255,0.02)', border: '1px solid rgba(255,255,255,0.04)' }}>
          <svg className="absolute inset-0 w-full h-full pointer-events-none" viewBox="0 0 300 40" preserveAspectRatio="none" fill="none">
            <path d="M0 20h80 M80 20v-10 M80 10h40 M120 10v10 M120 20h60 M180 20v-8 M180 12h120" stroke="#10B981" strokeWidth="0.3" opacity="0.08" />
            <circle cx="80" cy="20" r="1.5" fill="#10B981" opacity="0.1" />
            <circle cx="120" cy="20" r="1.5" fill="#06B6D4" opacity="0.1" />
            <circle cx="180" cy="20" r="1.5" fill="#8B5CF6" opacity="0.08" />
          </svg>
          <p className="relative z-10 text-[11px] text-white/30 px-3 py-2.5 leading-relaxed">
            Start a voice session and ask me anything about your Ethiopian coffee supply chain.
          </p>
        </div>
      )}

      <div className="grid grid-cols-2 gap-3">
        {CAPABILITY_GROUPS.map((g, idx) => (
          <div
            key={g.key}
            className="group relative rounded-xl overflow-hidden transition-all duration-300 hover:scale-[1.02] hover:shadow-lg"
            style={{
              background: 'rgba(255,255,255,0.025)',
              backdropFilter: 'blur(12px)',
              animationDelay: `${idx * 0.1}s`,
            }}
          >
            {/* SVG animated trace border */}
            <TraceBorder accent={g.accent} index={idx} />

            {/* SVG background pattern (circuit/hex/dots per category) */}
            <CapabilityCardBg pattern={g.bgPattern} accent={g.accent} />

            {/* Hover glow */}
            <div
              className="absolute inset-0 opacity-0 group-hover:opacity-100 transition-opacity duration-500 pointer-events-none"
              style={{
                background: `radial-gradient(ellipse at 50% 0%, ${g.accent}12 0%, transparent 70%)`,
              }}
            />

            <div className="relative z-10 px-3 py-3">
              {/* Icon + title row */}
              <div className="flex items-center gap-2.5 mb-2">
                {g.svgIcon(g.accent)}
                <div>
                  <span className="text-[11px] font-bold tracking-wide block" style={{ color: `${g.accent}DD` }}>
                    {g.title}
                  </span>
                  <div className="w-8 h-px mt-0.5" style={{ background: `linear-gradient(to right, ${g.accent}40, transparent)` }} />
                </div>
              </div>

              {/* Items with tech bullets */}
              <ul className="space-y-1">
                {g.items.map((item, i) => (
                  <li key={item} className="flex items-center gap-1.5 text-[10px] text-white/30 group-hover:text-white/40 transition-colors">
                    <svg width="10" height="10" viewBox="0 0 10 10" fill="none" className="flex-shrink-0">
                      <rect x="1" y="1" width="8" height="8" rx="2" stroke={g.accent} strokeWidth="0.5" opacity="0.4" />
                      <rect x="3" y="3" width="4" height="4" rx="1" fill={g.accent} opacity={0.2 + i * 0.1} />
                    </svg>
                    {item}
                  </li>
                ))}
              </ul>
            </div>
          </div>
        ))}
      </div>

      {/* Bottom tech accent — constellation line */}
      <div className="mt-4 flex items-center justify-center">
        <svg width="200" height="12" viewBox="0 0 200 12" fill="none" className="opacity-20">
          <line x1="0" y1="6" x2="60" y2="6" stroke="#10B981" strokeWidth="0.5" />
          <circle cx="60" cy="6" r="2" stroke="#10B981" strokeWidth="0.5" fill="none" />
          <circle cx="60" cy="6" r="0.8" fill="#10B981" />
          <line x1="64" y1="6" x2="100" y2="6" stroke="#06B6D4" strokeWidth="0.5" />
          <circle cx="100" cy="6" r="1.5" stroke="#06B6D4" strokeWidth="0.5" fill="none" />
          <circle cx="100" cy="6" r="0.6" fill="#06B6D4" />
          <line x1="103" y1="6" x2="140" y2="6" stroke="#8B5CF6" strokeWidth="0.5" />
          <circle cx="140" cy="6" r="2" stroke="#8B5CF6" strokeWidth="0.5" fill="none" />
          <circle cx="140" cy="6" r="0.8" fill="#8B5CF6" />
          <line x1="144" y1="6" x2="200" y2="6" stroke="#F59E0B" strokeWidth="0.5" />
        </svg>
      </div>
    </div>
  )
}

/* ================================================================
   Orb SVG — rotating rings, breathing inner circle, orbital dots
   ================================================================ */

function OrbSVG({ colors, agentState }) {
  const isActive = agentState === 'speaking' || agentState === 'listening'
  return (
    <svg width="256" height="256" viewBox="0 0 256 256" className="absolute inset-0">
      <defs>
        <radialGradient id="orb-glow" cx="50%" cy="50%" r="50%">
          <stop offset="0%" stopColor={colors.ring} stopOpacity="0.25" />
          <stop offset="100%" stopColor={colors.ring} stopOpacity="0" />
        </radialGradient>
      </defs>

      {/* Outer dashed ring — slow clockwise */}
      <circle cx="128" cy="128" r="124" fill="none" stroke={colors.ring} strokeWidth="0.5"
        strokeDasharray="3 9" strokeOpacity="0.3">
        <animateTransform attributeName="transform" type="rotate"
          from="0 128 128" to="360 128 128" dur="20s" repeatCount="indefinite" />
      </circle>

      {/* Middle ring — counter-clockwise */}
      <circle cx="128" cy="128" r="108" fill="none" stroke={colors.ring} strokeWidth="0.3"
        strokeOpacity="0.2">
        <animateTransform attributeName="transform" type="rotate"
          from="360 128 128" to="0 128 128" dur="15s" repeatCount="indefinite" />
      </circle>

      {/* Inner breathing ring */}
      <circle cx="128" cy="128" fill="none" stroke={colors.ring} strokeWidth="0.6"
        strokeOpacity={isActive ? 0.4 : 0.1}>
        <animate attributeName="r" values="85;91;85" dur="3s" repeatCount="indefinite" />
      </circle>

      {/* Orbital dot 1 */}
      <circle r="2" fill={colors.dot} opacity="0.5">
        <animateMotion dur="8s" repeatCount="indefinite"
          path="M128,20 A108,108 0 1,1 127.99,20" />
      </circle>

      {/* Orbital dot 2 */}
      <circle r="1.5" fill={colors.dot} opacity="0.3">
        <animateMotion dur="12s" repeatCount="indefinite"
          path="M128,40 A88,88 0 1,0 127.99,40" />
      </circle>

      {/* Center glow */}
      <circle cx="128" cy="128" r="60" fill="url(#orb-glow)" opacity="0.5" />
    </svg>
  )
}

/* ================================================================
   Idle microphone icon (before session starts)
   ================================================================ */

function IdleMicIcon() {
  return (
    <svg width="80" height="80" viewBox="0 0 80 80" fill="none">
      <defs>
        <radialGradient id="orb-idle" cx="50%" cy="50%" r="50%">
          <stop offset="0%" stopColor="#10B981" stopOpacity="0.25" />
          <stop offset="100%" stopColor="#064E3B" stopOpacity="0.10" />
        </radialGradient>
      </defs>
      <circle cx="40" cy="40" r="30" fill="url(#orb-idle)" opacity="0.8">
        <animate attributeName="r" values="28;32;28" dur="4s" repeatCount="indefinite" />
        <animate attributeName="opacity" values="0.6;0.9;0.6" dur="4s" repeatCount="indefinite" />
      </circle>
      <rect x="36" y="28" width="8" height="14" rx="4" fill="none" stroke="#fff" strokeWidth="1.5" opacity="0.7" />
      <path d="M32 40a8 8 0 0016 0" fill="none" stroke="#fff" strokeWidth="1.5" opacity="0.7" />
      <path d="M40 48v5" stroke="#fff" strokeWidth="1.5" opacity="0.7" />
    </svg>
  )
}

/* ================================================================
   Ambient SVG background — grid, gradients, orbital rings, particles
   Blended with Landing-hero floating orbs for consistency
   ================================================================ */

function AmbientBackground({ colors }) {
  return (
    <svg
      className="absolute inset-0 w-full h-full pointer-events-none"
      viewBox="0 0 800 800"
      preserveAspectRatio="xMidYMid slice"
    >
      <defs>
        <pattern id="vp-grid" width="40" height="40" patternUnits="userSpaceOnUse">
          <path d="M 40 0 L 0 0 0 40" fill="none" stroke="#10B981" strokeWidth="0.15" opacity="0.08" />
        </pattern>
        <radialGradient id="vp-glow-primary" cx="50%" cy="45%" r="35%">
          <stop offset="0%" stopColor={colors.ring} stopOpacity="0.10" />
          <stop offset="100%" stopColor={colors.ring} stopOpacity="0" />
        </radialGradient>
        <radialGradient id="vp-glow-secondary" cx="25%" cy="70%" r="25%">
          <stop offset="0%" stopColor="#10B981" stopOpacity="0.05" />
          <stop offset="100%" stopColor="#10B981" stopOpacity="0" />
        </radialGradient>
        <radialGradient id="vp-glow-tertiary" cx="75%" cy="30%" r="20%">
          <stop offset="0%" stopColor="#06B6D4" stopOpacity="0.03" />
          <stop offset="100%" stopColor="#06B6D4" stopOpacity="0" />
        </radialGradient>
      </defs>

      {/* Grid */}
      <rect width="800" height="800" fill="url(#vp-grid)" />

      {/* Radial glows */}
      <rect width="800" height="800" fill="url(#vp-glow-primary)" />
      <rect width="800" height="800" fill="url(#vp-glow-secondary)" />
      <rect width="800" height="800" fill="url(#vp-glow-tertiary)" />

      {/* Orbital rings — slow rotation */}
      <circle cx="400" cy="360" r="180" fill="none" stroke="#10B981" strokeWidth="0.3" opacity="0.05">
        <animateTransform attributeName="transform" type="rotate" from="0 400 360" to="360 400 360" dur="60s" repeatCount="indefinite" />
      </circle>
      <circle cx="400" cy="360" r="240" fill="none" stroke="#10B981" strokeWidth="0.3" strokeDasharray="4 12" opacity="0.03">
        <animateTransform attributeName="transform" type="rotate" from="360 400 360" to="0 400 360" dur="45s" repeatCount="indefinite" />
      </circle>
      <circle cx="400" cy="360" r="300" fill="none" stroke="#10B981" strokeWidth="0.2" strokeDasharray="2 18" opacity="0.02">
        <animateTransform attributeName="transform" type="rotate" from="0 400 360" to="360 400 360" dur="80s" repeatCount="indefinite" />
      </circle>

      {/* Corner accents */}
      <path d="M0 0 L60 0 L0 60Z" fill="#10B981" opacity="0.02" />
      <path d="M800 0 L740 0 L800 60Z" fill="#10B981" opacity="0.02" />
      <path d="M0 800 L60 800 L0 740Z" fill="#10B981" opacity="0.02" />
      <path d="M800 800 L740 800 L800 740Z" fill="#10B981" opacity="0.02" />

      {/* Floating particles */}
      <circle cx="120" cy="200" r="1.5" fill="#10B981" opacity="0.12">
        <animate attributeName="cy" values="200;175;200" dur="5s" repeatCount="indefinite" />
        <animate attributeName="opacity" values="0.12;0.25;0.12" dur="5s" repeatCount="indefinite" />
      </circle>
      <circle cx="680" cy="150" r="1" fill="#06B6D4" opacity="0.10">
        <animate attributeName="cy" values="150;130;150" dur="6.5s" repeatCount="indefinite" />
        <animate attributeName="opacity" values="0.10;0.22;0.10" dur="6.5s" repeatCount="indefinite" />
      </circle>
      <circle cx="200" cy="600" r="0.8" fill="#10B981" opacity="0.08">
        <animate attributeName="cy" values="600;580;600" dur="4s" repeatCount="indefinite" />
      </circle>
      <circle cx="650" cy="550" r="1.2" fill="#8B5CF6" opacity="0.06">
        <animate attributeName="cy" values="550;530;550" dur="7s" repeatCount="indefinite" />
      </circle>
      <circle cx="400" cy="120" r="1" fill="#F59E0B" opacity="0.06">
        <animate attributeName="cy" values="120;105;120" dur="5.5s" repeatCount="indefinite" />
        <animate attributeName="cx" values="400;410;400" dur="8s" repeatCount="indefinite" />
      </circle>

      {/* Constellation-style links (nod to Landing ConstellationBg) */}
      <line x1="120" y1="200" x2="200" y2="600" stroke="#10B981" strokeWidth="0.15" opacity="0.04" />
      <line x1="680" y1="150" x2="650" y2="550" stroke="#06B6D4" strokeWidth="0.15" opacity="0.03" />
      <line x1="120" y1="200" x2="400" y2="120" stroke="#10B981" strokeWidth="0.1" opacity="0.03" />
      <line x1="400" y1="120" x2="680" y2="150" stroke="#06B6D4" strokeWidth="0.1" opacity="0.03" />

      {/* Hexagonal accent */}
      <polygon
        points="400,310 432,328 432,364 400,382 368,364 368,328"
        fill="none" stroke="#10B981" strokeWidth="0.4" opacity="0.03"
      >
        <animateTransform attributeName="transform" type="rotate" from="0 400 346" to="360 400 346" dur="30s" repeatCount="indefinite" />
      </polygon>
    </svg>
  )
}
