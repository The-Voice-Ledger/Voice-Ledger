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

  /** Play base64 audio (TTS). */
  playBase64(base64, mimeType = 'audio/mp3') {
    // Stop any existing audio
    this.stopAudio()

    // Create blob URL
    const byteCharacters = atob(base64)
    const byteNumbers = new Array(byteCharacters.length)
    for (let i = 0; i < byteCharacters.length; i++) {
      byteNumbers[i] = byteCharacters.charCodeAt(i)
    }
    const byteArray = new Uint8Array(byteNumbers)
    const blob = new Blob([byteArray], { type: mimeType })
    
    this.currentAudioUrl = URL.createObjectURL(blob)
    this.currentAudio = new Audio(this.currentAudioUrl)
    
    this.currentAudio.onended = () => {
      this.stopAudio()
    }
    
    this.currentAudio.onerror = () => {
      console.error('Audio playback error')
      this.stopAudio()
    }
    
    return this.currentAudio.play()
  }

  /** Stop current audio playback. */
  stopAudio() {
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

  /** Release microphone. */
  release() {
    this.stop()
    this.stopAudio()
    if (this.stream) {
      this.stream.getTracks().forEach(track => track.stop())
      this.stream = null
    }
  }
}

// Export singleton instance
export default new VoiceManager()
