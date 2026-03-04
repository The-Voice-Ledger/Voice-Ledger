import { useEffect, useRef, useState, useCallback } from 'react'
import { useTranslation } from 'react-i18next'
import ReactMarkdown from 'react-markdown'
import { LuVolume2, LuLoader } from 'react-icons/lu'
import { getVoiceManager } from '../voice/VoiceManager'

const WAGA_LOGO = 'https://violet-rainy-toad-577.mypinata.cloud/ipfs/bafybeic6pclaqgbaaz6qqvlz2ssjgbzae4y7e76d2pobbwfxs2cviwgyqa'
import useChatStore from '../stores/chatStore'
import { ResponseCard } from '../components/cards/ResponseCard'

/** Tiny replay button for TTS audio */
function PlayButton({ audioBase64 }) {
  const [playing, setPlaying] = useState(false)
  const play = useCallback(async () => {
    if (playing) return
    setPlaying(true)
    try { await getVoiceManager().playBase64(audioBase64) } catch {}
    setPlaying(false)
  }, [audioBase64, playing])

  return (
    <button
      onClick={play}
      className="inline-flex items-center gap-1 text-[10px] text-stone-400 hover:text-stone-600 transition mt-1"
      title="Replay audio"
    >
      {playing
        ? <LuLoader className="w-3 h-3 animate-spin" />
        : <LuVolume2 className="w-3 h-3" />
      }
      <span>{playing ? 'Playing…' : 'Play'}</span>
    </button>
  )
}

export default function Assistant() {
  const { t } = useTranslation()
  const {
    messages, isLoading, isRecording, error,
    sendMessage, sendVoiceMessage, stopRecording, clearChat,
  } = useChatStore()
  const [input, setInput] = useState('')
  const bottomRef = useRef(null)

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

  return (
    <div className="flex flex-col flex-1 max-w-3xl mx-auto w-full">
      {/* Header bar */}
      <div className="flex items-center justify-between px-3 sm:px-4 py-2 border-b border-stone-200">
        <h1 className="text-base sm:text-lg font-semibold text-stone-900">{t('nav_assistant')}</h1>
        <button
          onClick={clearChat}
          className="text-xs text-stone-400 hover:text-stone-600 transition"
        >
          {t('clear_chat')}
        </button>
      </div>

      {/* Messages area */}
      <div className="flex-1 overflow-y-auto px-3 sm:px-4 py-4 space-y-4">
        {messages.length === 0 && (
          <div className="text-center text-stone-400 mt-16 space-y-2">
            <img src={WAGA_LOGO} alt="WAGA Coffee" className="h-10 mx-auto opacity-60" />
            <p className="text-sm">{t('chat_placeholder')}</p>
            <div className="flex flex-wrap justify-center gap-2 mt-4">
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
                  className="text-xs bg-stone-100 hover:bg-stone-200 text-stone-800 rounded-full px-3 py-1.5 transition"
                >
                  {q}
                </button>
              ))}
            </div>
          </div>
        )}

        {messages.map((msg) => (
          <div
            key={msg.id}
            className={`animate-fade-in-up flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
          >
            <div
              className={`max-w-[85%] rounded-2xl px-4 py-2.5 text-sm leading-relaxed ${
                msg.role === 'user'
                  ? 'bg-stone-900 text-white rounded-br-md'
                  : 'bg-white border border-stone-200 text-stone-800 rounded-bl-md shadow-sm'
              }`}
            >
              {msg.role === 'assistant' ? (
                <>
                  <ReactMarkdown
                    components={{
                      p: ({ children }) => <p className="mb-1.5 last:mb-0">{children}</p>,
                      ul: ({ children }) => <ul className="list-disc pl-4 mb-1.5">{children}</ul>,
                      ol: ({ children }) => <ol className="list-decimal pl-4 mb-1.5">{children}</ol>,
                      code: ({ children }) => (
                        <code className="bg-stone-100 text-stone-700 rounded px-1 py-0.5 text-xs">
                          {children}
                        </code>
                      ),
                    }}
                  >
                    {msg.text}
                  </ReactMarkdown>
                  <ResponseCard responseType={msg.responseType} data={msg.data} />
                  {msg.toolsUsed?.length > 0 && (
                    <div className="mt-2 flex flex-wrap gap-1">
                      {msg.toolsUsed.map((tc, i) => (
                        <span
                          key={i}
                          className={`text-[10px] rounded px-1.5 py-0.5 ${
                            tc.success
                              ? 'bg-forest-100 text-forest-700'
                              : 'bg-red-100 text-red-700'
                          }`}
                        >
                          {tc.tool_name}
                        </span>
                      ))}
                    </div>
                  )}
                  {msg.audioBase64 && <PlayButton audioBase64={msg.audioBase64} />}
                </>
              ) : (
                <span>{msg.text}</span>
              )}
            </div>
          </div>
        ))}

        {/* Loading indicator */}
        {isLoading && (
          <div className="flex justify-start animate-fade-in-up">
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

      {/* Input bar */}
      <div className="border-t border-stone-200 bg-white px-3 sm:px-4 py-3 pb-[calc(0.75rem+env(safe-area-inset-bottom))]">
        <form onSubmit={handleSubmit} className="flex items-center gap-1.5 sm:gap-2">
          {/* Voice button */}
          <button
            type="button"
            onClick={handleVoice}
            disabled={isLoading}
            className={`shrink-0 w-10 h-10 rounded-full flex items-center justify-center transition ${
              isRecording
                ? 'bg-red-500 text-white'
                : 'bg-stone-100 hover:bg-stone-200 text-stone-600'
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
            className="flex-1 rounded-full border border-stone-300 px-4 py-2.5 text-sm outline-none focus:border-stone-400 focus:ring-2 focus:ring-stone-200 transition disabled:opacity-50"
          />

          {/* Send button */}
          <button
            type="submit"
            disabled={!input.trim() || isLoading}
            className="shrink-0 w-10 h-10 rounded-full bg-stone-900 text-white flex items-center justify-center hover:bg-stone-800 transition disabled:opacity-40"
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
