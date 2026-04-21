/**
 * LiveKit Voice UI Components for Miniapps
 * Provides visual feedback and controls for LiveKit voice sessions
 * Similar to web-frontend's LiveVoicePanel but adapted for vanilla JS
 */

import { STATE_COLORS, STATE_LABELS } from './livekit-imports.js'

export class LiveKitVoiceUI {
  constructor(container, voiceManager) {
    console.log('LiveKitVoiceUI constructor called')
    this.container = container
    this.voiceManager = voiceManager
    this.isVisible = false
    this.currentTranscript = ''
    this.audioLevel = 0
    
    this.setupUI()
    this.bindEvents()
  }

  /**
   * Create the LiveKit voice UI
   */
  setupUI() {
    console.log('LiveKitVoiceUI.setupUI() called, container:', this.container)
    
    // Create overlay element and add to container (but keep it hidden initially)
    this.container.insertAdjacentHTML('beforeend', `
      <div class="livekit-voice-overlay" id="livekitOverlay" style="display: none;">
        <div class="livekit-voice-panel">
          <!-- Header -->
          <div class="livekit-header">
            <div class="livekit-logo">
              <img src="https://violet-rainy-toad-577.mypinata.cloud/ipfs/bafybeic6pclaqgbaaz6qqvlz2ssjgbzae4y7e76d2pobbwfxs2cviwgyqa" alt="WAGA Coffee" />
            </div>
            <div class="livekit-status">
              <div class="status-text" id="statusText">Ready</div>
              <div class="status-indicator" id="statusIndicator"></div>
            </div>
            <button class="close-btn" id="closeLiveKit">×</button>
          </div>

          <!-- Voice Visualizer -->
          <div class="voice-visualizer">
            <div class="voice-orb" id="voiceOrb">
              <div class="voice-ring" id="voiceRing"></div>
              <div class="voice-dot" id="voiceDot"></div>
              <div class="voice-waves">
                <div class="wave wave-1"></div>
                <div class="wave wave-2"></div>
                <div class="wave wave-3"></div>
              </div>
            </div>
            <div class="voice-state" id="voiceState">Ready</div>
          </div>

          <!-- Transcript Display -->
          <div class="transcript-container">
            <div class="transcript-text" id="transcriptText">
              Tap the microphone to start speaking...
            </div>
          </div>

          <!-- Controls -->
          <div class="voice-controls">
            <button class="mic-btn" id="micBtn">
              <div class="mic-icon">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z"/>
                  <path d="M19 10v2a7 7 0 0 1-14 0v-2"/>
                  <line x1="12" y1="19" x2="12" y2="23"/>
                  <line x1="8" y1="23" x2="16" y2="23"/>
                </svg>
              </div>
            </button>
            <div class="control-label">Tap to speak</div>
          </div>
        </div>
      </div>
    `);

    this.addStyles();
  }

  /**
   * Add CSS styles for the LiveKit UI
   */
  addStyles() {
    const styleId = 'livekit-voice-styles'
    if (document.getElementById(styleId)) return

    const style = document.createElement('style')
    style.id = styleId
    style.textContent = `
      .livekit-voice-overlay {
        position: fixed;
        top: 0;
        left: 0;
        width: 100%;
        height: 100%;
        background: linear-gradient(135deg, #1c1917 0%, #292524 50%, #1c1917 100%);
        z-index: 9999;
        display: none;
        opacity: 0;
        transition: opacity 0.3s ease;
      }

      .livekit-voice-overlay.visible {
        display: flex;
        align-items: center;
        justify-content: center;
        opacity: 1;
      }

      .livekit-voice-panel {
        width: 90%;
        max-width: 400px;
        height: 80vh;
        max-height: 600px;
        background: rgba(17, 24, 39, 0.95);
        border-radius: 24px;
        border: 1px solid rgba(107, 114, 128, 0.3);
        display: flex;
        flex-direction: column;
        overflow: hidden;
        backdrop-filter: blur(20px);
        box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.5);
      }

      .livekit-header {
        display: flex;
        align-items: center;
        justify-content: space-between;
        padding: 16px 20px;
        border-bottom: 1px solid rgba(107, 114, 128, 0.2);
      }

      .livekit-logo img {
        width: 32px;
        height: 32px;
        border-radius: 8px;
        object-fit: contain;
      }

      .livekit-status {
        display: flex;
        align-items: center;
        gap: 8px;
      }

      .status-text {
        font-size: 12px;
        color: #9ca3af;
        font-weight: 500;
      }

      .status-indicator {
        width: 8px;
        height: 8px;
        border-radius: 50%;
        background: #10b981;
        transition: all 0.3s ease;
      }

      .close-btn {
        background: none;
        border: none;
        color: #9ca3af;
        font-size: 18px;
        cursor: pointer;
        padding: 4px;
        border-radius: 4px;
        transition: all 0.2s ease;
      }

      .close-btn:hover {
        background: rgba(107, 114, 128, 0.2);
        color: #f3f4f6;
      }

      .voice-visualizer {
        flex: 1;
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        padding: 40px 20px;
      }

      .voice-orb {
        position: relative;
        width: 120px;
        height: 120px;
        display: flex;
        align-items: center;
        justify-content: center;
      }

      .voice-ring {
        position: absolute;
        width: 100%;
        height: 100%;
        border-radius: 50%;
        border: 3px solid #10b981;
        opacity: 0.3;
        transition: all 0.3s ease;
      }

      .voice-dot {
        width: 40px;
        height: 40px;
        border-radius: 50%;
        background: #34d399;
        transition: all 0.3s ease;
        box-shadow: 0 0 20px rgba(52, 211, 153, 0.4);
      }

      .voice-waves {
        position: absolute;
        width: 100%;
        height: 100%;
        pointer-events: none;
      }

      .wave {
        position: absolute;
        width: 100%;
        height: 100%;
        border-radius: 50%;
        border: 2px solid #34d399;
        opacity: 0;
        animation: none;
      }

      .wave.active {
        animation: wave-pulse 2s infinite;
      }

      .wave-1 { animation-delay: 0s; }
      .wave-2 { animation-delay: 0.5s; }
      .wave-3 { animation-delay: 1s; }

      @keyframes wave-pulse {
        0% {
          transform: scale(1);
          opacity: 0.6;
        }
        100% {
          transform: scale(1.5);
          opacity: 0;
        }
      }

      .voice-state {
        margin-top: 20px;
        font-size: 14px;
        font-weight: 600;
        color: #f3f4f6;
        text-align: center;
      }

      .transcript-container {
        padding: 20px;
        min-height: 80px;
        display: flex;
        align-items: center;
        justify-content: center;
      }

      .transcript-text {
        font-size: 14px;
        color: #d1d5db;
        text-align: center;
        line-height: 1.5;
        font-style: italic;
      }

      .voice-controls {
        padding: 20px;
        display: flex;
        flex-direction: column;
        align-items: center;
        gap: 12px;
      }

      .mic-btn {
        width: 64px;
        height: 64px;
        border-radius: 50%;
        background: #10b981;
        border: none;
        cursor: pointer;
        display: flex;
        align-items: center;
        justify-content: center;
        transition: all 0.2s ease;
        box-shadow: 0 4px 12px rgba(16, 185, 129, 0.3);
      }

      .mic-btn:hover {
        transform: scale(1.05);
        box-shadow: 0 6px 16px rgba(16, 185, 129, 0.4);
      }

      .mic-btn:active {
        transform: scale(0.95);
      }

      .mic-btn.recording {
        background: #ef4444;
        animation: pulse-red 1.5s infinite;
      }

      @keyframes pulse-red {
        0%, 100% {
          box-shadow: 0 4px 12px rgba(239, 68, 68, 0.3);
        }
        50% {
          box-shadow: 0 4px 20px rgba(239, 68, 68, 0.6);
        }
      }

      .mic-icon {
        width: 24px;
        height: 24px;
        color: white;
      }

      .control-label {
        font-size: 12px;
        color: #9ca3af;
        text-align: center;
      }

      /* State-specific styles */
      .voice-orb.listening .voice-ring {
        border-color: #10b981;
        opacity: 0.8;
        animation: pulse-ring 1.5s infinite;
      }

      .voice-orb.thinking .voice-ring {
        border-color: #8b5cf6;
        opacity: 0.8;
        animation: pulse-ring 1.2s infinite;
      }

      .voice-orb.speaking .voice-ring {
        border-color: #06b6d4;
        opacity: 0.8;
        animation: pulse-ring 1s infinite;
      }

      @keyframes pulse-ring {
        0% {
          transform: scale(1);
          opacity: 0.8;
        }
        50% {
          transform: scale(1.1);
          opacity: 0.4;
        }
        100% {
          transform: scale(1);
          opacity: 0.8;
        }
      }
    `
    document.head.appendChild(style)
  }

  /**
   * Bind event handlers
   */
  bindEvents() {
    const micBtn = document.getElementById('micBtn')
    const closeBtn = document.getElementById('closeLiveKit')

    micBtn.addEventListener('click', () => this.toggleRecording())
    closeBtn.addEventListener('click', () => this.hide())

    // Voice manager events
    this.voiceManager.onStateChange((newState, oldState) => {
      this.updateState(newState)
    })

    this.voiceManager.onAudioLevel((level) => {
      this.updateAudioLevel(level)
    })

    this.voiceManager.onTranscript((text) => {
      this.updateTranscript(text)
    })
  }

  /**
   * Show the LiveKit voice UI
   */
  async show() {
    console.log('LiveKitVoiceUI.show() called')
    this.isVisible = true
    const overlay = document.getElementById('livekitOverlay')
    
    if (!overlay) {
      console.error('LiveKit overlay element not found!')
      return
    }
    
    console.log('Showing LiveKit overlay')
    overlay.style.display = 'flex'
    
    // Trigger reflow for transition
    overlay.offsetHeight
    overlay.classList.add('visible')

    // Connect to LiveKit if not already connected
    if (!this.voiceManager.isReady()) {
      try {
        console.log('LiveKit not ready, connecting...')
        await this.voiceManager.connect()
      } catch (error) {
        console.error('Failed to connect to LiveKit:', error)
        this.showError('Failed to connect to voice service')
      }
    } else {
      console.log('LiveKit already ready')
    }
  }

  /**
   * Hide the LiveKit voice UI
   */
  async hide() {
    this.isVisible = false
    const overlay = document.getElementById('livekitOverlay')
    overlay.classList.remove('visible')
    
    setTimeout(() => {
      overlay.style.display = 'none'
    }, 300)

    // Stop recording if active
    if (this.voiceManager.isRecordingActive()) {
      await this.voiceManager.stopRecording()
    }
  }

  /**
   * Toggle recording state
   */
  async toggleRecording() {
    try {
      await this.voiceManager.toggleRecording()
    } catch (error) {
      console.error('Failed to toggle recording:', error)
      this.showError('Failed to access microphone')
    }
  }

  /**
   * Update UI based on voice state
   */
  updateState(state) {
    const statusText = document.getElementById('statusText')
    const statusIndicator = document.getElementById('statusIndicator')
    const voiceState = document.getElementById('voiceState')
    const voiceOrb = document.getElementById('voiceOrb')
    const micBtn = document.getElementById('micBtn')

    // Update text
    statusText.textContent = STATE_LABELS[state] || STATE_LABELS.disconnected
    voiceState.textContent = STATE_LABELS[state] || STATE_LABELS.disconnected

    // Update colors
    const colors = STATE_COLORS[state] || STATE_COLORS.disconnected
    statusIndicator.style.background = colors.dot
    voiceOrb.querySelector('.voice-dot').style.background = colors.dot
    voiceOrb.querySelector('.voice-ring').style.borderColor = colors.ring

    // Update orb state
    voiceOrb.className = `voice-orb ${state}`

    // Update mic button
    micBtn.classList.toggle('recording', state === 'listening')

    // Update waves
    const waves = voiceOrb.querySelectorAll('.wave')
    waves.forEach(wave => {
      wave.classList.toggle('active', state === 'listening')
    })
  }

  /**
   * Update audio level visualization
   */
  updateAudioLevel(level) {
    const voiceDot = document.getElementById('voiceDot')
    const scale = 1 + (level * 0.3) // Scale from 1 to 1.3
    voiceDot.style.transform = `scale(${scale})`
  }

  /**
   * Update transcript display
   */
  updateTranscript(text) {
    const transcriptText = document.getElementById('transcriptText')
    if (text) {
      transcriptText.textContent = text
      transcriptText.style.fontStyle = 'normal'
    } else {
      transcriptText.textContent = 'Tap the microphone to start speaking...'
      transcriptText.style.fontStyle = 'italic'
    }
  }

  /**
   * Show error message
   */
  showError(message) {
    const transcriptText = document.getElementById('transcriptText')
    transcriptText.textContent = `❌ ${message}`
    transcriptText.style.color = '#ef4444'
    
    setTimeout(() => {
      transcriptText.style.color = '#d1d5db'
      this.updateTranscript('')
    }, 3000)
  }
}
