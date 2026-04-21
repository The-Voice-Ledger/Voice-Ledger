// LiveKit state management
const STATE_COLORS = {
  disconnected: { ring: '#6B7280', dot: '#9CA3AF', glow: 'rgba(107,114,128,0.15)' },
  connecting:   { ring: '#F59E0B', dot: '#FBBF24', glow: 'rgba(245,158,11,0.2)' },
  initializing: { ring: '#F59E0B', dot: '#FBBF24', glow: 'rgba(245,158,11,0.2)' },
  idle:         { ring: '#10B981', dot: '#34D399', glow: 'rgba(16,185,129,0.2)' },
  listening:    { ring: '#10B981', dot: '#34D399', glow: 'rgba(16,185,129,0.35)' },
  thinking:     { ring: '#8B5CF6', dot: '#A78BFA', glow: 'rgba(139,92,246,0.25)' },
  speaking:     { ring: '#06B6D4', dot: '#22D3EE', glow: 'rgba(6,182,212,0.3)' },
  failed:       { ring: '#EF4444', dot: '#F87171', glow: 'rgba(239,68,68,0.2)' },
};

const STATE_LABELS = {
  disconnected: 'Disconnected',
  connecting: 'Connecting',
  initializing: 'Starting up',
  idle: 'Ready',
  listening: 'Listening',
  thinking: 'Thinking',
  speaking: 'Speaking',
  failed: 'Connection failed',
};

let isLiveKitStarted = false;
let isLiveKitMuted = false;

function updateLiveKitState(state) {
  const colors = STATE_COLORS[state] || STATE_COLORS.disconnected;
  const isPulsing = ['listening', 'connecting', 'thinking'].includes(state);
  
  const stateDot = document.getElementById('livekitStateDot');
  const stateLabel = document.getElementById('livekitStateLabel');
  if (stateDot && stateLabel) {
    stateDot.style.backgroundColor = colors.dot;
    stateDot.style.boxShadow = '0 0 8px ' + colors.glow;
    stateLabel.textContent = STATE_LABELS[state] || 'Unknown';
    stateLabel.style.color = colors.dot;
    
    if (isPulsing) {
      stateDot.style.animation = 'pulse 1.5s infinite';
    } else {
      stateDot.style.animation = 'none';
    }
  }
  
  const orb = document.getElementById('livekitOrb');
  if (orb) {
    orb.style.boxShadow = '0 0 60px 12px ' + colors.glow + ', 0 0 120px 24px ' + colors.glow;
    orb.style.opacity = (state === 'speaking' || state === 'listening') ? 0.7 : 0.25;
  }
  
  updateOrbContent(state);
}

function updateOrbContent(state) {
  const orbContent = document.getElementById('livekitOrbContent');
  if (!orbContent) return;
  
  if (isLiveKitStarted && state !== 'disconnected') {
    if (state === 'listening' || state === 'speaking') {
      orbContent.innerHTML = '<div style="width: 60px; height: 60px; display: flex; align-items: center; justify-content: center; gap: 2px;"><div style="width: 4px; height: 20px; background: rgba(255,255,255,0.6); border-radius: 2px;"></div><div style="width: 4px; height: 25px; background: rgba(255,255,255,0.6); border-radius: 2px;"></div><div style="width: 4px; height: 30px; background: rgba(255,255,255,0.6); border-radius: 2px;"></div><div style="width: 4px; height: 35px; background: rgba(255,255,255,0.6); border-radius: 2px;"></div><div style="width: 4px; height: 30px; background: rgba(255,255,255,0.6); border-radius: 2px;"></div><div style="width: 4px; height: 25px; background: rgba(255,255,255,0.6); border-radius: 2px;"></div><div style="width: 4px; height: 20px; background: rgba(255,255,255,0.6); border-radius: 2px;"></div></div>';
    }
  } else {
    orbContent.innerHTML = '<svg width="60" height="60" viewBox="0 0 80 80" fill="none"><circle cx="40" cy="40" r="25" fill="rgba(16,185,129,0.25)" opacity="0.8"><animate attributeName="r" values="23;27;23" dur="4s" repeatCount="indefinite"></animate><animate attributeName="opacity" values="0.6;0.9;0.6" dur="4s" repeatCount="indefinite"></animate></circle><rect x="36" y="28" width="8" height="14" rx="4" fill="none" stroke="#fff" stroke-width="1.5" opacity="0.7"></rect><path d="M32 40a8 8 0 0016 0" fill="none" stroke="#fff" stroke-width="1.5" opacity="0.7"></path><path d="M40 48v5" stroke="#fff" stroke-width="1.5" opacity="0.7"></path></svg>';
  }
}

async function startLiveKitSession() {
  try {
    updateLiveKitState('connecting');
    document.getElementById('livekitConnectError').style.display = 'none';
    console.log('[VoiceLedger] Starting voice session...');
    await initializeLiveKit();
  } catch (err) {
    console.error('[VoiceLedger] session.start() failed:', err);
    const errorEl = document.getElementById('livekitConnectError');
    if (errorEl) {
      errorEl.textContent = err.message || 'Failed to connect. Check microphone permissions.';
      errorEl.style.display = 'block';
    }
    updateLiveKitState('failed');
  }
}

async function endLiveKitSession() {
  if (liveKitSession) {
    liveKitSession.disconnect();
  }
  isLiveKitStarted = false;
  closeLiveKitVoicePanel();
}

async function toggleLiveKitMute() {
  try {
    if (liveKitSession && liveKitSession.localParticipant) {
      const mic = liveKitSession.localParticipant.getTrackPublication('microphone');
      if (mic?.track) {
        if (isLiveKitMuted) {
          mic.track.unmute();
        } else {
          mic.track.mute();
        }
      }
    }
    
    isLiveKitMuted = !isLiveKitMuted;
    
    const muteBtn = document.getElementById('livekitMuteBtn');
    const mutedIndicator = document.getElementById('livekitMutedIndicator');
    
    if (muteBtn) {
      if (isLiveKitMuted) {
        muteBtn.style.background = 'rgba(245,158,11,0.2)';
        muteBtn.style.color = '#F59E0B';
        muteBtn.title = 'Unmute microphone';
      } else {
        muteBtn.style.background = 'rgba(255,255,255,0.08)';
        muteBtn.style.color = 'rgba(255,255,255,0.7)';
        muteBtn.title = 'Mute microphone';
      }
    }
    
    if (mutedIndicator) {
      mutedIndicator.style.display = isLiveKitMuted ? 'block' : 'none';
    }
  } catch (e) {
    console.error('Failed to toggle mute:', e);
  }
}
