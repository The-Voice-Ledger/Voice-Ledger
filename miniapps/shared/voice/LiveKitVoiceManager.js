/**
 * LiveKitVoiceManager - Real-time voice communication using LiveKit Session API
 * Replaces the basic MediaRecorder with LiveKit WebRTC streaming
 * 
 * Usage:
 *   const vm = new LiveKitVoiceManager()
 *   await vm.startSession(userId, userName)
 *   vm.endSession()
 */

// Import LiveKit client from CDN
import { Room, RoomEvent } from 'https://cdn.skypack.dev/livekit-client@2.17.3'
import { STATE_COLORS, STATE_LABELS } from './livekit-imports.js'

// Use API functions from window (loaded by livekit.js)
const getLiveKitToken = window.getLiveKitToken
const liveKitHealth = window.liveKitHealth

export class LiveKitVoiceManager {
  constructor() {
    this.room = null
    this.isConnected = false
    this.isRecording = false
    this.userId = null
    this.userName = null
    this.userRole = 'user'
    this.transcriptCallback = null
    this.stateChangeCallback = null
    this.audioLevelCallback = null
    this.roomReadyCallback = null
    
    // State management
    this.state = 'disconnected' // disconnected, connecting, connected, listening, thinking, speaking
    
    // Audio level monitoring
    this.audioAnalyser = null
    this.audioLevelInterval = null
  }

  /**
   * Connect to LiveKit room with agent
   */
  async connect(userId = null, userName = null, userRole = 'user') {
    try {
      this.setState('connecting')
      this.userId = userId || `user_${Date.now()}`
      this.userName = userName || 'Telegram User'
      this.userRole = userRole

      // Request microphone permission for Telegram environment only
      if (window.Telegram?.WebApp) {
        try {
          const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
          stream.getTracks().forEach(track => track.stop())
          console.log('[VoiceLedger] Telegram microphone permission granted')
        } catch (err) {
          console.error('[VoiceLedger] Telegram microphone permission denied:', err.name)
          if (err.name === 'NotAllowedError') {
            throw new Error('Microphone permission required. Please enable in Telegram settings.')
          }
          throw err
        }
      }

      // Check if LiveKit is configured
      const health = await liveKitHealth()
      if (!health.configured) {
        throw new Error('LiveKit is not configured on the backend')
      }

      // Get LiveKit token with agent dispatch
      const tokenData = await getLiveKitToken({
        userId: this.userId,
        userName: this.userName,
        userRole: this.userRole,
        agentName: 'voice-agent' // Request agent dispatch
      })

      // Create and connect to room with Telegram-specific settings
      this.room = new Room({
        audioCaptureDefaults: {
          deviceId: undefined,
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
        },
        publishDefaults: {
          audioPreset: 'speech', // Use speech preset for better voice quality
          videoSimulcastLayers: [],
        },
        adaptiveStream: true,
        // Telegram-specific settings
        dynacast: true,
        stopLocalTrackOnUnpublish: true,
      })

      // Set up event listeners
      this.setupEventListeners()
      if (this.roomReadyCallback) {
        this.roomReadyCallback(this.room)
      }

      // Connect to LiveKit room
      await this.room.connect(tokenData.url, tokenData.token)
      this.isConnected = true
      this.setState('connected')

      console.log('[VoiceLedger] Connected to LiveKit room successfully')
      return true

    } catch (error) {
      console.error('Failed to connect to LiveKit:', error)
      this.setState('failed')
      throw error
    }
  }

  
  /**
   * Set up LiveKit room event listeners
   */
  setupEventListeners() {
    if (!this.room) return

    this.room.on(RoomEvent.Connected, () => {
      console.log('[VoiceLedger] Room connected')
      this.setState('connected')
    })

    this.room.on(RoomEvent.Disconnected, () => {
      console.log('[VoiceLedger] Room disconnected')
      this.isConnected = false
      this.setState('disconnected')
    })

    this.room.on(RoomEvent.Reconnected, () => {
      console.log('[VoiceLedger] Room reconnected')
      this.setState('connected')
    })

    // Handle agent tracks (remote audio from agent)
    this.room.on(RoomEvent.TrackSubscribed, (track, publication, participant) => {
      console.log('[VoiceLedger] Track subscribed:', track.kind, 'from:', participant.identity)
      
      // Agent audio track
      if (track.kind === 'audio' && participant.identity.startsWith('agent-')) {
        console.log('[VoiceLedger] Agent audio track detected')
        this.setState('speaking')
        
        // When track ends, agent finished speaking
        track.on('ended', () => {
          console.log('[VoiceLedger] Agent finished speaking')
          setTimeout(() => {
            this.setState('listening')
          }, 500)
        })
      }
    })

    this.room.on(RoomEvent.TrackUnsubscribed, (track, publication, participant) => {
      if (track.kind === 'audio' && participant.identity.startsWith('agent-')) {
        console.log('[VoiceLedger] Agent track unsubscribed')
        this.setState('connected')
      }
    })

    console.log('[VoiceLedger] Room listeners set up')
  }

  /**
   * Start voice recording (enable microphone)
   */
  async startRecording() {
    if (!this.isConnected || !this.room) {
      throw new Error('Not connected to LiveKit room')
    }

    try {
      await this.room.localParticipant.setMicrophoneEnabled(true)
      this.isRecording = true
      this.setState('listening')
      
      console.log('[VoiceLedger] Microphone enabled - listening for voice')
      return true
    } catch (error) {
      console.error('Failed to enable microphone:', error)
      throw error
    }
  }

  /**
   * Stop voice recording (disable microphone)
   */
  async stopRecording() {
    if (!this.isRecording || !this.room) return

    try {
      await this.room.localParticipant.setMicrophoneEnabled(false)
      this.isRecording = false
      this.setState('thinking') // Agent will process the input
      
      console.log('[VoiceLedger] Microphone disabled - agent thinking')
      return true
    } catch (error) {
      console.error('Failed to disable microphone:', error)
      throw error
    }
  }

  /**
   * Toggle recording state
   */
  async toggleRecording() {
    if (this.isRecording) {
      return await this.stopRecording()
    } else {
      return await this.startRecording()
    }
  }

  /**
   * Disconnect from LiveKit room
   */
  async disconnect() {
    if (this.room) {
      await this.room.disconnect()
      this.room = null
    }
    this.isConnected = false
    this.isRecording = false
    this.setState('disconnected')
    console.log('[VoiceLedger] Disconnected from LiveKit room')
  }

  /**
   * Check if room is ready
   */
  isReady() {
    return this.isConnected && this.room !== null
  }

  /**
   * Check if recording is active
   */
  isRecordingActive() {
    return this.isRecording
  }

  /**
   * Set current state and notify callback
   */
  setState(newState) {
    const oldState = this.state
    this.state = newState
    
    if (this.stateChangeCallback) {
      this.stateChangeCallback(newState, oldState)
    }
  }

  /**
   * Set callback for transcript updates
   */
  onTranscript(callback) {
    this.transcriptCallback = callback
  }

  /**
   * Set callback for state changes
   */
  onStateChange(callback) {
    this.stateChangeCallback = callback
  }

  /**
   * Set callback for audio level updates
   */
  onAudioLevel(callback) {
    this.audioLevelCallback = callback
  }

  /**
   * Set callback for when the room instance is created
   */
  onRoomReady(callback) {
    this.roomReadyCallback = callback
  }

  /**
   * Get current state
   */
  getState() {
    return this.state
  }

  /**
   * Check if connected
   */
  isReady() {
    return this.isConnected && this.room
  }

  /**
   * Check if recording
   */
  isRecordingActive() {
    return this.isRecording
  }
}

// Export singleton instance
export const liveKitVoiceManager = new LiveKitVoiceManager()
