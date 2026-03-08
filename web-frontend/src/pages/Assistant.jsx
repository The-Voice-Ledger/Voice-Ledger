import { useEffect, useRef, useState, useCallback } from 'react'
import { useTranslation } from 'react-i18next'
import ReactMarkdown from 'react-markdown'
import { LuVolume2, LuLoader, LuCopy, LuCheck, LuChevronDown, LuCircleCheck, LuCircleX, LuWrench, LuSparkles } from 'react-icons/lu'
import { getVoiceManager } from '../voice/VoiceManager'

const WAGA_LOGO = 'https://violet-rainy-toad-577.mypinata.cloud/ipfs/bafybeic6pclaqgbaaz6qqvlz2ssjgbzae4y7e76d2pobbwfxs2cviwgyqa'
import useChatStore from '../stores/chatStore'
import useAuthStore from '../stores/authStore'
import { ResponseCard } from '../components/cards/ResponseCard'

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
      {copied ? <LuCheck className="w-3.5 h-3.5" /> : <LuCopy className="w-3.5 h-3.5" />}
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
        <LuWrench className="w-3 h-3" />
        <span>{t('tools_used', { count: tools.length })}</span>
        {failed > 0 && <span className="text-red-400">({failed} failed)</span>}
        <LuChevronDown className={`w-3 h-3 transition-transform duration-200 ${open ? 'rotate-180' : ''}`} />
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
              {tc.success ? <LuCircleCheck className="w-2.5 h-2.5" /> : <LuCircleX className="w-2.5 h-2.5" />}
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
              <LuVolume2 className="w-3 h-3" />
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
    messages, isLoading, isRecording, error,
    sendMessage, sendVoiceMessage, stopRecording, clearChat,
  } = useChatStore()
  const [input, setInput] = useState('')
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

  const handleVoice = () => {
    if (isRecording) {
      stopRecording()
    } else {
      sendVoiceMessage()
    }
  }

  const initial = userInitial(user)

  return (
    <div className="flex flex-col flex-1 max-w-3xl mx-auto w-full">
      {/* Header bar */}
      <div className="flex items-center justify-between px-3 sm:px-4 py-2 border-b border-stone-200">
        <div className="flex items-center gap-2">
          <div className="w-7 h-7 rounded-full bg-stone-900 flex items-center justify-center">
            <LuSparkles className="w-3.5 h-3.5 text-white" />
          </div>
          <div>
            <h1 className="text-base sm:text-lg font-semibold text-stone-900 leading-tight">{t('nav_assistant')}</h1>
            <p className="text-[10px] text-stone-400 leading-tight">{t('assistant_subtitle')}</p>
          </div>
        </div>
        <button
          onClick={clearChat}
          className="text-xs text-stone-400 hover:text-stone-600 transition"
        >
          {t('clear_chat')}
        </button>
      </div>

      {/* Messages area - with top fade gradient */}
      <div ref={scrollRef} className="relative flex-1 overflow-y-auto">
        {/* Top fade hint */}
        <div className="sticky top-0 left-0 right-0 h-6 bg-gradient-to-b from-stone-50 to-transparent z-10 pointer-events-none" />

        <div className="px-3 sm:px-4 pb-4 space-y-4">
          {messages.length === 0 && (
            <div className="text-center mt-12 mb-8 space-y-4">
              {/* Empty-state illustration area */}
              <div className="relative mx-auto w-32 h-32 rounded-full bg-gradient-to-br from-coffee-100 via-stone-100 to-forest-100 flex items-center justify-center">
                <img src={WAGA_LOGO} alt="WAGA Coffee" className="h-14 opacity-70" />
                <div className="absolute inset-0 rounded-full animate-pulse-ring border-2 border-coffee-200 opacity-30" />
              </div>
              <div>
                <p className="text-base font-medium text-stone-700">{t('assistant_welcome')}</p>
                <p className="text-sm text-stone-400 mt-1">{t('chat_placeholder')}</p>
              </div>
              {/* Prompt pills - 2-column grid */}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 max-w-md mx-auto mt-6">
                {[
                  t('prompt_rfqs'),
                  t('prompt_create_rfq'),
                  t('prompt_eudr'),
                  t('prompt_containers'),
                  t('prompt_lineage'),
                  t('prompt_dpp'),
                  t('prompt_blockchain'),
                  t('prompt_eudr_docs'),
                ].map((q) => (
                  <button
                    key={q}
                    onClick={() => sendMessage(q)}
                    className="text-xs text-left bg-white hover:bg-stone-50 text-stone-600 hover:text-stone-900 border border-stone-200 hover:border-stone-300 rounded-xl px-3 py-2.5 transition shadow-sm hover:shadow"
                  >
                    {q}
                  </button>
                ))}
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
                      <LuSparkles className="w-3.5 h-3.5 text-white" />
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
                <LuSparkles className="w-3.5 h-3.5 text-white" />
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
      <div className="border-t border-stone-200 bg-white px-3 sm:px-4 py-3 pb-[calc(0.75rem+env(safe-area-inset-bottom))]">
        <form onSubmit={handleSubmit} className="flex items-center gap-1.5 sm:gap-2">
          {/* Voice button */}
          <button
            type="button"
            onClick={handleVoice}
            disabled={isLoading}
            className={`shrink-0 w-10 h-10 rounded-full flex items-center justify-center transition-all duration-200 ${
              isRecording
                ? 'bg-red-500 text-white scale-110'
                : 'bg-stone-100 hover:bg-stone-200 hover:scale-105 text-stone-600'
            }`}
            title={isRecording ? t('chat_recording') : t('chat_voice')}
          >
            {isRecording ? (
              <span className="relative flex items-center justify-center">
                <span className="absolute w-10 h-10 rounded-full bg-red-400 animate-pulse-ring" />
                <svg className="w-5 h-5 relative" fill="currentColor" viewBox="0 0 24 24">
                  <rect x="6" y="6" width="12" height="12" rx="2" />
                </svg>
              </span>
            ) : (
              <svg className="w-5 h-5" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" d="M12 1a3 3 0 00-3 3v8a3 3 0 006 0V4a3 3 0 00-3-3z" />
                <path strokeLinecap="round" strokeLinejoin="round" d="M19 10v2a7 7 0 01-14 0v-2" />
                <line x1="12" y1="19" x2="12" y2="23" />
                <line x1="8" y1="23" x2="16" y2="23" />
              </svg>
            )}
          </button>

          {/* Text input */}
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder={t('chat_placeholder')}
            disabled={isLoading || isRecording}
            className="flex-1 rounded-full border border-stone-300 px-4 py-2.5 text-sm outline-none focus:border-stone-500 focus:ring-2 focus:ring-stone-200/60 transition disabled:opacity-50"
          />

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
  )
}
