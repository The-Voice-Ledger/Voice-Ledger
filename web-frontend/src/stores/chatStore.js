import { create } from 'zustand'
import { sendText, sendVoice } from '../api/agent'
import { getVoiceManager } from '../voice/VoiceManager'

/**
 * Chat store - messages, loading state, conversation history.
 *
 * Each message: { id, role: 'user'|'assistant', text, responseType, data, audioBase64, toolsUsed, ts }
 */
const useChatStore = create((set, get) => ({
  messages: [],
  isLoading: false,
  isRecording: false,
  conversationId: null,
  language: 'en',
  error: null,

  setLanguage: (lang) => set({ language: lang }),

  /** Send a text message and append the response. */
  sendMessage: async (text) => {
    const { language, conversationId, messages } = get()
    const userMsg = {
      id: crypto.randomUUID(),
      role: 'user',
      text,
      ts: Date.now(),
    }
    set({ messages: [...messages, userMsg], isLoading: true, error: null })

    try {
      const res = await sendText(text, { language, conversationId, voice: true })
      const assistantMsg = {
        id: crypto.randomUUID(),
        role: 'assistant',
        text: res.text,
        responseType: res.response_type,
        data: res.data,
        audioBase64: res.audio_base64,
        toolsUsed: res.tools_used,
        ts: Date.now(),
      }
      set((s) => ({
        messages: [...s.messages, assistantMsg],
        conversationId: res.conversation_id || s.conversationId,
        isLoading: false,
      }))

      // Auto-play TTS if available
      if (res.audio_base64) {
        try { await getVoiceManager().playBase64(res.audio_base64) } catch {}
      }
    } catch (err) {
      set({ isLoading: false, error: err.message })
    }
  },

  /** Record audio, send to agent, append response, play TTS. */
  sendVoiceMessage: async () => {
    const vm = getVoiceManager()
    const { language, conversationId, messages } = get()

    set({ isRecording: true, error: null })

    try {
      const blob = await vm.record()
      set({ isRecording: false, isLoading: true })

      // Show a placeholder user message
      const userMsg = {
        id: crypto.randomUUID(),
        role: 'user',
        text: 'Voice message...',
        isVoice: true,
        ts: Date.now(),
      }
      set((s) => ({ messages: [...s.messages, userMsg] }))

      const res = await sendVoice(blob, { language, conversationId })

      // Update user message with real transcript from ASR
      const assistantMsg = {
        id: crypto.randomUUID(),
        role: 'assistant',
        text: res.text,
        responseType: res.response_type,
        data: res.data,
        audioBase64: res.audio_base64,
        toolsUsed: res.tools_used,
        ts: Date.now(),
      }
      set((s) => ({
        messages: s.messages
          .map((m) =>
            m.id === userMsg.id && res.transcript
              ? { ...m, text: res.transcript }
              : m,
          )
          .concat(assistantMsg),
        conversationId: res.conversation_id || s.conversationId,
        isLoading: false,
      }))

      // Auto-play TTS if available
      if (res.audio_base64) {
        await vm.playBase64(res.audio_base64)
      }
    } catch (err) {
      set({ isRecording: false, isLoading: false, error: err.message })
    }
  },

  /** Stop an in-progress voice recording. */
  stopRecording: () => {
    getVoiceManager().stop()
  },

  /** Clear chat history. */
  clearChat: () => set({ messages: [], conversationId: null, error: null }),
}))

export default useChatStore
