/**
 * LiveKit imports for miniapps
 * Since we can't use npm packages directly, we'll load LiveKit from CDN
 */

// Import LiveKit client from CDN
import { Room, RoomEvent, RemoteTrack, RemoteTrackPublication, LocalAudioTrack, AudioPresets } from 'https://cdn.skypack.dev/livekit-client@2.17.3'

// Export LiveKit components for use in miniapps
export {
  Room,
  RoomEvent,
  RemoteTrack,
  RemoteTrackPublication,
  LocalAudioTrack,
  AudioPresets
}

// LiveKit state colors (matching web-frontend)
export const STATE_COLORS = {
  disconnected: { ring: '#6B7280', dot: '#9CA3AF', glow: 'rgba(107,114,128,0.15)' },
  connecting:   { ring: '#F59E0B', dot: '#FBBF24', glow: 'rgba(245,158,11,0.2)' },
  initializing: { ring: '#F59E0B', dot: '#FBBF24', glow: 'rgba(245,158,11,0.2)' },
  idle:         { ring: '#10B981', dot: '#34D399', glow: 'rgba(16,185,129,0.2)' },
  listening:    { ring: '#10B981', dot: '#34D399', glow: 'rgba(16,185,129,0.35)' },
  thinking:     { ring: '#8B5CF6', dot: '#A78BFA', glow: 'rgba(139,92,246,0.25)' },
  speaking:     { ring: '#06B6D4', dot: '#22D3EE', glow: 'rgba(6,182,212,0.3)' },
  failed:       { ring: '#EF4444', dot: '#F87171', glow: 'rgba(239,68,68,0.2)' },
}

// State labels
export const STATE_LABELS = {
  disconnected: 'Disconnected',
  connecting:   'Connecting…',
  initializing: 'Starting up…',
  idle:         'Ready',
  listening:    'Listening…',
  thinking:     'Thinking…',
  speaking:     'Speaking…',
  failed:       'Connection Failed',
}
