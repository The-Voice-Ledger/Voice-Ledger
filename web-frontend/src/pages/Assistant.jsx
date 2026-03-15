import { useEffect, useRef, useState, useCallback } from 'react'
import { useTranslation } from 'react-i18next'
import ReactMarkdown from 'react-markdown'
import { IconVolume2, IconLoader, IconCopy, IconCheck, IconChevronDown, IconCircleCheck, IconCircleX, IconWrench, IconSparkles } from '../components/svg/Icons'
import { getVoiceManager } from '../voice/VoiceManager'
import LiveVoicePanel from '../components/LiveVoicePanel'
import ConstellationBg from '../components/svg/ConstellationBg'
import useAuthStore from '../stores/authStore'
import useChatStore from '../stores/chatStore'
import { ResponseCard } from '../components/cards/ResponseCard'

const WAGA_LOGO =
  'https://violet-rainy-toad-577.mypinata.cloud/ipfs/bafybeic6pclaqgbaaz6qqvlz2ssjgbzae4y7e76d2pobbwfxs2cviwgyqa'

/* ── Helpers ─────────────────────────────────────────────────── */

/** Format epoch-ms to a short time string */
function formatTime(ts) {
  if (!ts) return ''
  const d = new Date(ts)
  return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
}

/** Get user initial(s) for avatar */
function userInitial(user) {
  if (user?.full_name) return user.full_name.charAt(0).toUpperCase()
  if (user?.phone_number) return user.phone_number.slice(-2)
  return 'U'
}

/* ── Copy button for code blocks ─────────────────────────────── */

function CopyButton({ text }) {
  const [copied, setCopied] = useState(false)
  const handleCopy = useCallback(() => {
    navigator.clipboard.writeText(text).then(() => {
      setCopied(true)
      setTimeout(() => setCopied(false), 1500)
    })
  }, [text])

  return (
    <button
      onClick={handleCopy}
      className="absolute top-2 right-2 p-1 rounded bg-stone-700 hover:bg-stone-600 text-stone-300 hover:text-white transition opacity-0 group-hover/code:opacity-100"
      title="Copy code"
    >
      {copied ? <IconCheck className="w-3.5 h-3.5" /> : <IconCopy className="w-3.5 h-3.5" />}
    </button>
  )
}

/* ── Tool‑usage collapsible ──────────────────────────────────── */

function ToolUsagePills({ tools, t }) {
  const [open, setOpen] = useState(false)
  if (!tools?.length) return null

  const succeeded = tools.filter((tc) => tc.success).length
  const failed = tools.length - succeeded

  return (
    <div className="mt-2">
      <button
        onClick={() => setOpen((o) => !o)}
        className="inline-flex items-center gap-1.5 text-[10px] text-stone-400 hover:text-stone-600 transition"
      >
        <IconWrench className="w-3 h-3" />
        <span>{t('tools_used', { count: tools.length })}</span>
        {failed > 0 && <span className="text-red-400">({failed} failed)</span>}
        <IconChevronDown className={`w-3 h-3 transition-transform duration-200 ${open ? 'rotate-180' : ''}`} />
      </button>
      {open && (
        <div className="flex flex-wrap gap-1 mt-1 animate-fade-in-up">
          {tools.map((tc, i) => (
            <span
              key={i}
              className={`inline-flex items-center gap-0.5 text-[10px] rounded px-1.5 py-0.5 ${
                tc.success
                  ? 'bg-forest-100 text-forest-700'
                  : 'bg-red-100 text-red-700'
              }`}
            >
              {tc.success ? <IconCircleCheck className="w-2.5 h-2.5" /> : <IconCircleX className="w-2.5 h-2.5" />}
              {tc.tool_name}
            </span>
          ))}
        </div>
      )}
    </div>
  )
}

/** Simple audio controls for existing auto-played audio */
function PlayButton({ audioBase64 }) {
  const [isPlaying, setIsPlaying] = useState(false)
  const [currentTime, setCurrentTime] = useState(0)
  const [duration, setDuration] = useState(0)
  const voiceManagerRef = useRef(null)
  const progressIntervalRef = useRef(null)

  useEffect(() => {
    voiceManagerRef.current = getVoiceManager()
    
    // Check if audio is currently playing
    const checkAudio = () => {
      const vm = voiceManagerRef.current
      const audio = vm.getCurrentAudio()
      
      if (audio) {
        setIsPlaying(!audio.paused)
        setDuration(audio.duration || 0)
        setCurrentTime(audio.currentTime || 0)
        
        // Start progress tracking if playing
        if (!audio.paused && !progressIntervalRef.current) {
          progressIntervalRef.current = setInterval(() => {
            setCurrentTime(audio.currentTime || 0)
          }, 100)
        } else if (audio.paused && progressIntervalRef.current) {
          clearInterval(progressIntervalRef.current)
          progressIntervalRef.current = null
        }
      } else {
        setIsPlaying(false)
        if (progressIntervalRef.current) {
          clearInterval(progressIntervalRef.current)
          progressIntervalRef.current = null
        }
      }
    }

    // Check immediately
    checkAudio()
    
    // Set up periodic check
    const interval = setInterval(checkAudio, 200)
    
    return () => {
      clearInterval(interval)
      if (progressIntervalRef.current) {
        clearInterval(progressIntervalRef.current)
      }
    }
  }, [])

  const play = async () => {
    const vm = voiceManagerRef.current
    
    // Always play - either resume or start new
    const audio = vm.getCurrentAudio()
    if (audio && audio.paused) {
      // Resume existing audio
      audio.play()
      setIsPlaying(true)
    } else {
      // Start new audio
      await vm.playBase64(audioBase64)
      setIsPlaying(true)
    }
  }

  const pause = () => {
    const vm = voiceManagerRef.current
    const audio = vm.getCurrentAudio()
    if (audio && !audio.paused) {
      audio.pause()
      setIsPlaying(false)
    }
  }

  const stop = () => {
    const vm = voiceManagerRef.current
    vm.stopCurrentAudio()
    setIsPlaying(false)
    setCurrentTime(0)
    
    if (progressIntervalRef.current) {
      clearInterval(progressIntervalRef.current)
      progressIntervalRef.current = null
    }
  }

  const formatTime = (time) => {
    if (!time || !isFinite(time)) return '0:00'
    const minutes = Math.floor(time / 60)
    const seconds = Math.floor(time % 60)
    return `${minutes}:${seconds.toString().padStart(2, '0')}`
  }

  const progress = duration > 0 ? (currentTime / duration) * 100 : 0

  // Always show controls if we have audioBase64
  const showControls = audioBase64

  return (
    <div className="mt-2 flex items-center gap-2 text-[10px] text-stone-500">
      {showControls && (
        <>
          {!isPlaying ? (
            <button
              onClick={play}
              className="inline-flex items-center gap-1 px-2 py-1 rounded bg-stone-100 hover:bg-stone-200 transition"
              title="Play audio"
            >
              <IconVolume2 className="w-3 h-3" />
              <span>Play</span>
            </button>
          ) : (
            <>
              <button
                onClick={pause}
                className="inline-flex items-center gap-1 px-2 py-1 rounded bg-stone-100 hover:bg-stone-200 transition"
                title="Pause audio"
              >
                <svg className="w-3 h-3" fill="currentColor" viewBox="0 0 24 24">
                  <rect x="6" y="4" width="4" height="16" />
                  <rect x="14" y="4" width="4" height="16" />
                </svg>
                <span>Pause</span>
              </button>

              <button
                onClick={stop}
                className="inline-flex items-center gap-1 px-2 py-1 rounded bg-stone-100 hover:bg-stone-200 transition"
                title="Stop audio"
              >
                <svg className="w-3 h-3" fill="currentColor" viewBox="0 0 24 24">
                  <rect x="6" y="6" width="12" height="12" />
                </svg>
                <span>Stop</span>
              </button>

              {/* Progress bar */}
              <div className="flex-1 max-w-32">
                <div className="flex items-center gap-1">
                  <span className="text-[9px] text-stone-400">{formatTime(currentTime)}</span>
                  <div className="flex-1 h-1 bg-stone-200 rounded-full overflow-hidden">
                    <div 
                      className="h-full bg-stone-400 transition-all duration-100"
                      style={{ width: `${progress}%` }}
                    />
                  </div>
                  <span className="text-[9px] text-stone-400">{formatTime(duration)}</span>
                </div>
              </div>
            </>
          )}
        </>
      )}
    </div>
  )
}

/* ── Markdown renderers ──────────────────────────────────────── */

const mdComponents = {
  p: ({ children }) => <p className="mb-1.5 last:mb-0">{children}</p>,
  ul: ({ children }) => <ul className="list-disc pl-4 mb-1.5">{children}</ul>,
  ol: ({ children }) => <ol className="list-decimal pl-4 mb-1.5">{children}</ol>,
  code: ({ children, className }) => {
    const text = String(children).replace(/\n$/, '')
    const isBlock = Boolean(className) || text.includes('\n')
    if (!isBlock) {
      return (
        <code className="bg-stone-100 text-stone-700 rounded px-1 py-0.5 text-xs font-mono">
          {children}
        </code>
      )
    }
    // Multi-line fenced code block
    return (
      <div className="relative group/code my-2 rounded-lg overflow-hidden bg-stone-900 text-stone-100">
        <CopyButton text={text} />
        <pre className="overflow-x-auto p-3 text-xs leading-relaxed font-mono">
          <code className={className}>{children}</code>
        </pre>
      </div>
    )
  },
  pre: ({ children }) => <>{children}</>,
}

/* ── Main assistant page ─────────────────────────────────────── */

export default function Assistant() {
  const { t } = useTranslation()
  const { user } = useAuthStore()
  const {
    messages, isLoading, error,
    sendMessage, clearChat,
  } = useChatStore()
  const [input, setInput] = useState('')
  const [voiceOpen, setVoiceOpen] = useState(false)
  const bottomRef = useRef(null)
  const scrollRef = useRef(null)

  // Auto-scroll to bottom on new messages
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, isLoading])

  const handleSubmit = (e) => {
    e.preventDefault()
    const text = input.trim()
    if (!text || isLoading) return
    setInput('')
    sendMessage(text)
  }

  const initial = userInitial(user)

  return (
    <>
    <div className="flex flex-col flex-1 max-w-3xl mx-auto w-full">
      {/* Header bar */}
      <div className="flex items-center justify-between px-3 sm:px-4 py-2.5 border-b border-stone-200 bg-white">
        <div className="flex items-center gap-2.5">
          <div className="w-7 h-7 rounded-lg bg-stone-900 flex items-center justify-center">
            <IconSparkles className="w-3.5 h-3.5 text-white" />
          </div>
          <div>
            <h1 className="text-base sm:text-lg font-semibold text-stone-900 leading-tight font-display tracking-tight">{t('nav_assistant')}</h1>
            <p className="text-[10px] text-stone-400 leading-tight">{t('assistant_subtitle')}</p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          {/* Quick voice access (always visible) */}
          <button
            onClick={() => setVoiceOpen(true)}
            className="hidden sm:flex items-center gap-1.5 text-[10px] font-medium text-stone-400 hover:text-emerald-600 bg-stone-50 hover:bg-emerald-50 rounded-lg px-2.5 py-1.5 transition-colors"
            title="Open voice assistant"
          >
            <svg className="w-3 h-3" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
              <rect x="9" y="2" width="6" height="11" rx="3" />
              <path d="M5 12a7 7 0 0014 0" />
              <line x1="12" y1="19" x2="12" y2="22" />
            </svg>
            Voice
          </button>
          <button
            onClick={clearChat}
            className="text-xs text-stone-400 hover:text-stone-600 transition"
          >
            {t('clear_chat')}
          </button>
        </div>
      </div>

      {/* Messages area - with top fade gradient */}
      <div ref={scrollRef} className="relative flex-1 overflow-y-auto">
        {/* Top fade hint */}
        <div className="sticky top-0 left-0 right-0 h-6 bg-gradient-to-b from-stone-50 to-transparent z-10 pointer-events-none" />

        <div className="px-3 sm:px-4 pb-4 space-y-4">
          {messages.length === 0 && (
            <div className="mt-6 sm:mt-10 mb-8 px-1 animate-fade-in-up">
              {/* ── Greeting with animated logo ── */}
              <div className="text-center mb-6">
                <div className="inline-block mb-4">
                  {/* Animated logo card — larger, centered */}
                  <div className="relative mx-auto w-16 h-16">
                    <svg className="absolute -inset-2.5 w-[calc(100%+20px)] h-[calc(100%+20px)]" viewBox="0 0 84 84" fill="none">
                      <rect x="2" y="2" width="80" height="80" rx="22" stroke="url(#logo-ring-grad)" strokeWidth="0.7" strokeDasharray="4 8" opacity="0.35">
                        <animateTransform attributeName="transform" type="rotate" from="0 42 42" to="360 42 42" dur="20s" repeatCount="indefinite" />
                      </rect>
                      <circle cx="8" cy="8" r="1" fill="#10B981" opacity="0.3">
                        <animate attributeName="opacity" values="0.2;0.5;0.2" dur="3s" repeatCount="indefinite" />
                      </circle>
                      <circle cx="76" cy="76" r="1" fill="#06B6D4" opacity="0.25">
                        <animate attributeName="opacity" values="0.15;0.45;0.15" dur="4s" repeatCount="indefinite" />
                      </circle>
                      <defs>
                        <linearGradient id="logo-ring-grad" x1="0" y1="0" x2="84" y2="84">
                          <stop offset="0%" stopColor="#10B981" />
                          <stop offset="100%" stopColor="#06B6D4" />
                        </linearGradient>
                      </defs>
                    </svg>
                    <img src={WAGA_LOGO} alt="WAGA" className="w-16 h-16 rounded-2xl shadow-sm" />
                  </div>
                </div>
                <h2 className="text-xl sm:text-2xl font-semibold text-stone-800 font-display tracking-tight">
                  {t('assistant_welcome')}
                </h2>
                <p className="text-sm text-stone-400 mt-1">Choose how you'd like to interact</p>
              </div>

              {/* ── Two-mode cards ── */}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 max-w-xl mx-auto">

                {/* === Voice Card === */}
                <button
                  onClick={() => setVoiceOpen(true)}
                  className="group relative overflow-hidden rounded-2xl text-left transition-all duration-300
                    bg-gradient-to-br from-stone-900 via-stone-800 to-stone-950
                    hover:shadow-xl hover:shadow-emerald-900/20 hover:scale-[1.02] active:scale-[0.98]
                    ring-1 ring-white/5 hover:ring-emerald-500/20"
                  aria-label="Start voice session"
                >
                  {/* Constellation background — the dark-theme network pattern */}
                  <div className="absolute inset-0 opacity-40">
                    <ConstellationBg />
                  </div>

                  {/* Floating orbs (miniature) */}
                  <div className="absolute -top-6 -right-6 w-28 h-28 rounded-full bg-emerald-500/10 blur-2xl animate-float-slow" />
                  <div className="absolute -bottom-4 -left-4 w-20 h-20 rounded-full bg-cyan-500/8 blur-2xl animate-float-slower" />

                  <div className="relative z-10 p-5 sm:p-6 flex flex-col items-center text-center min-h-[200px] justify-center gap-4">
                    {/* Animated logo with orbital rings */}
                    <div className="relative w-24 h-24 flex items-center justify-center">
                      <svg className="absolute inset-0 w-full h-full" viewBox="0 0 96 96">
                        {/* Outer dashed orbit */}
                        <circle cx="48" cy="48" r="44" fill="none" stroke="#10B981" strokeWidth="0.5"
                                strokeDasharray="3 8" strokeOpacity="0.3">
                          <animateTransform attributeName="transform" type="rotate"
                                            from="0 48 48" to="360 48 48" dur="16s" repeatCount="indefinite" />
                        </circle>
                        {/* Inner counter-rotating ring */}
                        <circle cx="48" cy="48" r="35" fill="none" stroke="#10B981" strokeWidth="0.3" strokeOpacity="0.15">
                          <animateTransform attributeName="transform" type="rotate"
                                            from="360 48 48" to="0 48 48" dur="12s" repeatCount="indefinite" />
                        </circle>
                        {/* Breathing ring around logo */}
                        <circle cx="48" cy="48" fill="none" stroke="#10B981" strokeWidth="0.5" strokeOpacity="0.25">
                          <animate attributeName="r" values="24;27;24" dur="3s" repeatCount="indefinite" />
                        </circle>
                        {/* Orbital dot */}
                        <circle r="1.2" fill="#34D399" opacity="0.5">
                          <animateMotion dur="8s" repeatCount="indefinite" path="M48,4 A44,44 0 1,1 47.99,4" />
                        </circle>
                        {/* Soft glow behind logo */}
                        <circle cx="48" cy="48" r="18" fill="#10B981" opacity="0.06">
                          <animate attributeName="r" values="16;20;16" dur="4s" repeatCount="indefinite" />
                          <animate attributeName="opacity" values="0.04;0.08;0.04" dur="4s" repeatCount="indefinite" />
                        </circle>
                      </svg>
                      {/* Logo center */}
                      <img src={WAGA_LOGO} alt="" className="relative w-10 h-10 rounded-xl group-hover:scale-110 transition-transform duration-300" />
                    </div>

                    <div>
                      <p className="text-sm font-semibold text-white/90 font-display tracking-tight">
                        Speak to The Voice Ledger
                      </p>
                      <p className="text-[11px] text-white/35 mt-0.5">
                        Your Voice Assistant
                      </p>
                    </div>

                    {/* CTA pill */}
                    <span className="inline-flex items-center gap-1.5 text-[10px] font-medium text-emerald-400/80 group-hover:text-emerald-300 tracking-wide uppercase transition-colors">
                      <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
                      Tap to start
                    </span>
                  </div>

                  {/* Subtle pulse ring on hover */}
                  <div className="absolute inset-0 rounded-2xl border border-emerald-400/0 group-hover:border-emerald-400/10 transition-all pointer-events-none" />
                </button>

                {/* === Chat Card === */}
                <div className="relative overflow-hidden rounded-2xl bg-white ring-1 ring-stone-200 hover:ring-stone-300 transition-all">
                  {/* Subtle dot-grid pattern */}
                  <svg className="absolute inset-0 w-full h-full opacity-[0.04]" viewBox="0 0 100 100" preserveAspectRatio="xMidYMid slice">
                    {Array.from({ length: 8 }, (_, row) =>
                      Array.from({ length: 8 }, (_, col) => (
                        <circle key={`${row}-${col}`} cx={8 + col * 12} cy={8 + row * 12} r="0.8" fill="currentColor" />
                      ))
                    )}
                  </svg>

                  <div className="relative z-10 p-5 sm:p-6 flex flex-col min-h-[200px]">
                    <div className="flex items-center gap-2.5 mb-4">
                      <div className="relative w-9 h-9 rounded-xl bg-stone-100 flex items-center justify-center text-stone-500">
                        <svg className="w-4.5 h-4.5" fill="none" stroke="currentColor" strokeWidth="1.5" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" d="M7.5 8.25h9m-9 3H12m-9.75 1.51c0 1.6 1.123 2.994 2.707 3.227 1.129.166 2.27.293 3.423.379.35.026.67.21.865.501L12 21l2.755-4.133a1.14 1.14 0 01.865-.501 48.172 48.172 0 003.423-.379c1.584-.233 2.707-1.626 2.707-3.228V6.741c0-1.602-1.123-2.995-2.707-3.228A48.394 48.394 0 0012 3c-2.392 0-4.744.175-7.043.513C3.373 3.746 2.25 5.14 2.25 6.741v6.018z" />
                        </svg>
                        {/* Subtle animated dot */}
                        <span className="absolute -top-0.5 -right-0.5 w-2 h-2 rounded-full bg-emerald-400 ring-2 ring-white">
                          <span className="absolute inset-0 rounded-full bg-emerald-400 animate-ping opacity-40" />
                        </span>
                      </div>
                      <div>
                        <p className="text-sm font-semibold text-stone-800 font-display tracking-tight">
                          Type to ask
                        </p>
                        <p className="text-[11px] text-stone-400">
                          Chat with the assistant below
                        </p>
                      </div>
                    </div>

                    {/* Prompt pills */}
                    <div className="grid grid-cols-1 gap-1.5 flex-1">
                      {[
                        t('prompt_rfqs'),
                        t('prompt_create_rfq'),
                        t('prompt_eudr'),
                        t('prompt_containers'),
                      ].map((q) => (
                        <button
                          key={q}
                          onClick={() => sendMessage(q)}
                          className="text-[11px] text-left text-stone-500 hover:text-stone-800 bg-stone-50 hover:bg-stone-100 rounded-lg px-3 py-2 transition truncate"
                        >
                          {q}
                        </button>
                      ))}
                    </div>

                    <p className="text-[10px] text-stone-300 mt-3 text-center">
                      + {4} more prompts — just start typing
                    </p>
                  </div>
                </div>
              </div>
            </div>
          )}

          {messages.map((msg, idx) => {
            // Date separator
            const prevMsg = messages[idx - 1]
            const showDate = !prevMsg || new Date(msg.ts).toDateString() !== new Date(prevMsg.ts).toDateString()

            return (
              <div key={msg.id}>
                {showDate && msg.ts && (
                  <div className="flex items-center gap-3 my-4">
                    <div className="flex-1 h-px bg-stone-200" />
                    <span className="text-[10px] font-medium text-stone-400 uppercase tracking-wider">
                      {new Date(msg.ts).toLocaleDateString(undefined, { weekday: 'short', month: 'short', day: 'numeric' })}
                    </span>
                    <div className="flex-1 h-px bg-stone-200" />
                  </div>
                )}

                <div className={`animate-fade-in-up flex gap-2.5 ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                  {/* Assistant avatar */}
                  {msg.role === 'assistant' && (
                    <div className="shrink-0 w-7 h-7 rounded-full bg-stone-900 flex items-center justify-center mt-1">
                      <IconSparkles className="w-3.5 h-3.5 text-white" />
                    </div>
                  )}

                  <div className="max-w-[80%] space-y-0.5">
                    <div
                      className={`rounded-2xl px-4 py-2.5 text-sm leading-relaxed ${
                        msg.role === 'user'
                          ? 'bg-stone-900 text-white rounded-br-md'
                          : 'bg-white border border-stone-200 text-stone-800 rounded-bl-md shadow-sm'
                      }`}
                    >
                      {msg.role === 'assistant' ? (
                        <>
                          <ReactMarkdown components={mdComponents}>
                            {msg.text}
                          </ReactMarkdown>
                          <ResponseCard responseType={msg.responseType} data={msg.data} />
                          <ToolUsagePills tools={msg.toolsUsed} t={t} />
                          {msg.audioBase64 && <PlayButton audioBase64={msg.audioBase64} />}
                        </>
                      ) : (
                        <span>{msg.text}</span>
                      )}
                    </div>
                    {/* Timestamp */}
                    {msg.ts && (
                      <p className={`text-[10px] text-stone-400 px-1 ${msg.role === 'user' ? 'text-right' : 'text-left'}`}>
                        {formatTime(msg.ts)}
                      </p>
                    )}
                  </div>

                  {/* User avatar */}
                  {msg.role === 'user' && (
                    <div className="shrink-0 w-7 h-7 rounded-full bg-coffee-200 flex items-center justify-center mt-1 text-[11px] font-bold text-coffee-800">
                      {initial}
                    </div>
                  )}
                </div>
              </div>
            )
          })}

          {/* Loading indicator */}
          {isLoading && (
            <div className="flex gap-2.5 justify-start animate-fade-in-up">
              <div className="shrink-0 w-7 h-7 rounded-full bg-stone-900 flex items-center justify-center">
                <IconSparkles className="w-3.5 h-3.5 text-white" />
              </div>
              <div className="bg-white border border-stone-200 rounded-2xl rounded-bl-md px-4 py-3 shadow-sm">
                <div className="flex gap-1.5">
                  <span className="w-2 h-2 bg-stone-400 rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
                  <span className="w-2 h-2 bg-stone-400 rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
                  <span className="w-2 h-2 bg-stone-400 rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
                </div>
              </div>
            </div>
          )}

          {/* Error display */}
          {error && (
            <div className="text-center text-sm text-red-500 bg-red-50 rounded-lg p-2">
              {error}
            </div>
          )}

          <div ref={bottomRef} />
        </div>
      </div>

      {/* Input bar */}
      <div className="border-t border-stone-200 bg-white px-3 sm:px-4 pt-3 pb-6 mb-2">
        <form onSubmit={handleSubmit} className="flex items-center gap-2">
          {/* Text input with embedded mic icon */}
          <div className="relative flex-1">
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder={t('chat_placeholder')}
              disabled={isLoading}
              className="w-full rounded-full border border-stone-300 pl-4 pr-12 py-2.5 text-sm outline-none focus:border-stone-500 focus:ring-2 focus:ring-stone-200/60 transition disabled:opacity-50"
            />
            {/* Mic icon inside input — opens voice panel */}
            <button
              type="button"
              onClick={() => setVoiceOpen(true)}
              className="absolute right-2 top-1/2 -translate-y-1/2 w-8 h-8 rounded-full flex items-center justify-center
                text-stone-400 hover:text-emerald-600 hover:bg-emerald-50 transition-all duration-200"
              title="Open voice assistant"
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth="1.8" viewBox="0 0 24 24">
                <rect x="9" y="2" width="6" height="11" rx="3" />
                <path d="M5 12a7 7 0 0014 0" />
                <line x1="12" y1="19" x2="12" y2="22" />
              </svg>
            </button>
          </div>

          {/* Send button */}
          <button
            type="submit"
            disabled={!input.trim() || isLoading}
            className="shrink-0 w-10 h-10 rounded-full bg-stone-900 text-white flex items-center justify-center hover:bg-stone-800 hover:scale-105 active:scale-95 transition-all duration-150 disabled:opacity-40 disabled:hover:scale-100"
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" d="M22 2L11 13" />
              <path strokeLinecap="round" strokeLinejoin="round" d="M22 2l-7 20-4-9-9-4 20-7z" />
            </svg>
          </button>
        </form>
      </div>
    </div>

      <LiveVoicePanel isOpen={voiceOpen} onClose={() => setVoiceOpen(false)} />
    </>
  )
}
