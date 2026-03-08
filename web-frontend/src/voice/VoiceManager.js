/**
 * VoiceManager - singleton that wraps MediaRecorder with silence detection.
 *
 * Usage:
 *   const vm = new VoiceManager()
 *   const blob = await vm.record()          // resolves when user stops or silence detected
 *   vm.playBase64(base64, 'audio/mp3')      // play TTS response
 */

export class VoiceManager {
  constructor() {
    this.stream = null
    this.recorder = null
    this.chunks = []
    this._resolve = null
    this._analyser = null
    this._silenceTimer = null
    this.isRecording = false
    
    // Global TTS audio management
    this.currentAudio = null
    this.currentAudioUrl = null
  }

  /** Request mic permission (call once early to avoid popup delay). */
  async init() {
    if (this.stream) return
    this.stream = await navigator.mediaDevices.getUserMedia({ audio: true })
  }

  /**
   * Start recording. Returns a Promise<Blob> that resolves when
   * stop() is called or silence is detected for `silenceMs`.
   */
  async record({ silenceMs = 2000, silenceThreshold = -45 } = {}) {
    await this.init()
    this.chunks = []
    this.isRecording = true

    // Setup analyser for silence detection
    const ctx = new AudioContext()
    const source = ctx.createMediaStreamSource(this.stream)
    this._analyser = ctx.createAnalyser()
    this._analyser.fftSize = 512
    source.connect(this._analyser)
    const dataArr = new Float32Array(this._analyser.fftSize)

    this.recorder = new MediaRecorder(this.stream, {
      mimeType: MediaRecorder.isTypeSupported('audio/webm;codecs=opus')
        ? 'audio/webm;codecs=opus'
        : 'audio/webm',
    })

    this.recorder.ondataavailable = (e) => {
      if (e.data.size > 0) this.chunks.push(e.data)
    }

    return new Promise((resolve) => {
      this._resolve = resolve

      this.recorder.onstop = () => {
        this.isRecording = false
        clearInterval(this._silenceTimer)
        ctx.close()
        // Release mic stream so browser indicator turns off
        if (this.stream) {
          this.stream.getTracks().forEach((t) => t.stop())
          this.stream = null
        }
        const blob = new Blob(this.chunks, { type: 'audio/webm' })
        resolve(blob)
      }

      this.recorder.start(250) // collect every 250ms

      // Silence detection loop
      let silentSince = null
      this._silenceTimer = setInterval(() => {
        this._analyser.getFloatTimeDomainData(dataArr)
        const rms = Math.sqrt(dataArr.reduce((s, v) => s + v * v, 0) / dataArr.length)
        const dB = 20 * Math.log10(rms + 1e-10)

        if (dB < silenceThreshold) {
          if (!silentSince) silentSince = Date.now()
          if (Date.now() - silentSince > silenceMs) {
            this.stop()
          }
        } else {
          silentSince = null
        }
      }, 200)
    })
  }

  /** Stop recording manually. */
  stop() {
    if (this.recorder && this.recorder.state === 'recording') {
      this.recorder.stop()
    }
  }

  /** Stop any currently playing TTS audio */
  stopCurrentAudio() {
    if (this.currentAudio) {
      this.currentAudio.pause()
      this.currentAudio.currentTime = 0
      this.currentAudio = null
    }
    if (this.currentAudioUrl) {
      URL.revokeObjectURL(this.currentAudioUrl)
      this.currentAudioUrl = null
    }
  }

  /** Play a base64-encoded audio response. Returns a promise that resolves when done. */
  playBase64(b64, mime = 'audio/mp3') {
    return new Promise((resolve) => {
      // Stop any currently playing audio first
      this.stopCurrentAudio()
      
      const bytes = Uint8Array.from(atob(b64), (c) => c.charCodeAt(0))
      const blob = new Blob([bytes], { type: mime })
      const url = URL.createObjectURL(blob)
      this.currentAudioUrl = url
      
      const audio = new Audio(url)
      this.currentAudio = audio
      
      audio.onended = () => {
        URL.revokeObjectURL(url)
        this.currentAudio = null
        this.currentAudioUrl = null
        resolve()
      }
      audio.onerror = () => {
        URL.revokeObjectURL(url)
        this.currentAudio = null
        this.currentAudioUrl = null
        resolve()
      }
      audio.play()
    })
  }

  /** Get current audio instance for external control */
  getCurrentAudio() {
    return this.currentAudio
  }

  /** Check if audio is currently playing */
  isAudioPlaying() {
    return this.currentAudio && !this.currentAudio.paused
  }

  /** Release mic stream. */
  destroy() {
    this.stop()
    this.stopCurrentAudio() // Also stop any playing TTS audio
    if (this.stream) {
      this.stream.getTracks().forEach((t) => t.stop())
      this.stream = null
    }
  }
}

/** Singleton instance */
let _instance = null
export function getVoiceManager() {
  if (!_instance) _instance = new VoiceManager()
  return _instance
}
