(() => {
  const state = {
    tg: null,
    micBtn: null,
    voiceManager: null,
    isLiveKitStarted: false,
    isLiveKitMuted: false,
    voiceActivityTimeout: null,
    isVoiceDetectionEnabled: false,
    transcriptVisible: false,
    transcriptManuallyHidden: false,
    agentTranscriptions: [],
    agentAttributeState: null,
    boundRoom: null,
    currentUiState: 'disconnected',
    derivedStateTimeout: null,
    depsPromise: null,
    RoomEvent: null,
    liveKitVoiceManager: null,
    isDisconnecting: false,
  };

  function loadScript(src) {
    return new Promise((resolve, reject) => {
      const existing = document.querySelector(`script[src="${src}"]`);
      if (existing) {
        if (existing.dataset.loaded === 'true') {
          resolve();
          return;
        }
        
        // Check if script is actually loaded by testing for global variables
        if (src.includes('assistant-livekit-panel.js') && window.assistantLiveKitPanel) {
          existing.dataset.loaded = 'true';
          resolve();
          return;
        }
        
        existing.addEventListener('load', () => resolve(), { once: true });
        existing.addEventListener('error', (e) => reject(e), { once: true });
        return;
      }

      const script = document.createElement('script');
      script.src = src;
      script.addEventListener('load', () => {
        script.dataset.loaded = 'true';
        resolve();
      }, { once: true });
      script.addEventListener('error', (e) => reject(e), { once: true });
      document.head.appendChild(script);
    });
  }

  async function ensureDependencies() {
    if (state.depsPromise) {
      return state.depsPromise;
    }

    state.depsPromise = (async () => {
      try {
        // Check if dependencies are already available
        if (window.assistantLiveKitPanel && window.liveKitVoiceManager) {
          state.RoomEvent = window.RoomEvent || null;
          state.liveKitVoiceManager = window.liveKitVoiceManager;
          return;
        }

        await loadScript('/miniapps/shared/voice/assistant-livekit-panel.js');
        await loadScript('/miniapps/shared/api/livekit.js?v=2025041901');
        const liveKitImports = await import('/miniapps/shared/voice/livekit-imports.js');
        const voiceManagerModule = await import('/miniapps/shared/voice/LiveKitVoiceManager.js');

        state.RoomEvent = liveKitImports.RoomEvent;
        window.STATE_COLORS = liveKitImports.STATE_COLORS;
        window.STATE_LABELS = liveKitImports.STATE_LABELS;
        state.liveKitVoiceManager = voiceManagerModule.liveKitVoiceManager;
      } catch (error) {
        console.error('ensureDependencies failed:', error);
        throw error;
      }
    })();

    return state.depsPromise;
  }

  async function initializeVoiceManager() {
    if (state.voiceManager) return state.voiceManager;

    await ensureDependencies();

    try {
      state.voiceManager = state.liveKitVoiceManager;
      state.voiceManager.onRoomReady?.((room) => {
        bindAgentStateListeners(room);
      });

      state.voiceManager.onStateChange((newState, oldState) => {
        if (['connecting', 'disconnected', 'failed'].includes(newState)) {
          updateLiveKitState(newState);
          if ((newState === 'disconnected' || newState === 'failed') && !state.isDisconnecting) {
            endLiveKitSession();
          }
        } else if (newState === 'connected') {
          syncAgentStateFromRoom(state.voiceManager.room) || applyDerivedState(getDefaultUiState());
        }

        // Update transcript visibility when state changes (like web-frontend)
        updateTranscriptVisibility();

        // Update UI based on state
        if (newState === 'connected' && !state.isLiveKitStarted) {
          state.isLiveKitStarted = true;
          document.getElementById('livekitStartBtn').style.display = 'none';
          document.getElementById('livekitActiveControls').style.display = 'flex';

          // Auto-unmute microphone when session connects
          if (!state.voiceManager.isRecordingActive()) {
            setTimeout(() => {
              if (state.voiceManager && state.voiceManager.isReady()) {
                toggleLiveKitMute();
              }
            }, 100); // Small delay to ensure room is fully ready
          }

          // Sync UI state
          state.isLiveKitMuted = !state.voiceManager.isRecordingActive();
          const muteBtn = document.getElementById('livekitMuteBtn');
          const mutedIndicator = document.getElementById('livekitMutedIndicator');
          if (muteBtn) {
            muteBtn.style.background = state.isLiveKitMuted ? 'rgba(245,158,11,0.2)' : 'rgba(255,255,255,0.08)';
            muteBtn.style.color = state.isLiveKitMuted ? '#F59E0B' : 'rgba(255,255,255,0.7)';
            muteBtn.title = state.isLiveKitMuted ? 'Unmute microphone' : 'Mute microphone';
          }
          if (mutedIndicator) {
            mutedIndicator.style.display = state.isLiveKitMuted ? 'block' : 'none';
          }

          // Set up track handlers AFTER room is connected
          if (state.voiceManager.room) {
            bindAgentStateListeners(state.voiceManager.room);
            syncAgentStateFromRoom(state.voiceManager.room);

            // Set up transcription handler AFTER room is fully ready
            try {
              state.voiceManager.room.unregisterTextStreamHandler('lk.transcription');
            } catch (error) {
              // Ignore if no handler was registered
            }

            // Register for agent transcriptions (handle both interim and final streams for real-time)
            state.voiceManager.room.registerTextStreamHandler('lk.transcription', async (reader, participantInfo) => {
              try {
                // Use async iterator for real-time chunk processing
                for await (const chunk of reader) {

                  // Check if this is a transcription
                  const isTranscription = reader.info?.attributes['lk.transcribed_track_id'] != null;
                  const isFinal = reader.info?.attributes['lk.transcription_final'] === 'true';
                  const segmentId = reader.info?.attributes['lk.segment_id'];
                  const participantIdentity = participantInfo?.identity || 'unknown';

                  if (isTranscription && chunk.trim()) {
                    // Determine if it's user or agent based on participant identity
                    const isUser = participantIdentity.includes('user') || !participantIdentity.includes('agent');

                    if (!state.agentAttributeState) {
                      if (isUser) {
                        applyDerivedState(isFinal ? 'thinking' : 'listening', isFinal ? 12000 : null);
                      } else {
                        applyDerivedState('speaking', isFinal ? 1200 : null);
                      }
                    }

                    // Update transcriptions array immediately (real-time)
                    updateTranscriptions(chunk.trim(), isUser, segmentId, isFinal);
                  }
                }
              } catch (error) {
                console.error('[VoiceLedger] Error reading transcription stream:', error);
              }
            });

            // Register for action cards from LiveKit agent
            if (window.ActionCards) {
              try {
                state.voiceManager.room.registerTextStreamHandler('vl.action', async (reader, participantInfo) => {
                  try {
                    for await (const chunk of reader) {
                      if (chunk.trim()) {
                        // Parse action card JSON
                        try {
                          const actionCard = JSON.parse(chunk);
                          
                          // Fix data structure - move any top-level arrays/objects to data property if needed
                          if (!actionCard.data) {
                            // Handle array types first
                            const arrayKeys = ['rfqs', 'containers', 'batches', 'offers', 'pools', 'commitments', 'events'];
                            const foundArrayKey = arrayKeys.find(key => Array.isArray(actionCard[key]));
                            
                            if (foundArrayKey) {
                              actionCard.data = { [foundArrayKey]: actionCard[foundArrayKey] };
                            } else {
                              // For single item types, move all non-type properties to data
                              const dataProps = {};
                              Object.keys(actionCard).forEach(key => {
                                if (key !== 'type') {
                                  dataProps[key] = actionCard[key];
                                }
                              });
                              
                              if (Object.keys(dataProps).length > 0) {
                                actionCard.data = dataProps;
                              }
                            }
                          }
                          
                          // Add action card using the panel helper
                          window.assistantLiveKitPanel?.addActionCard(actionCard);
                          
                          // Show action cards section when cards are added
                          const actionCardsSection = document.getElementById('actionCardsSection');
                          if (actionCardsSection) {
                            actionCardsSection.style.display = 'flex';
                          }
                        } catch (parseError) {
                          console.error('Failed to parse action card:', parseError);
                        }
                      }
                    }
                  } catch (error) {
                    console.error('Error reading action cards stream:', error);
                  }
                });
              } catch (error) {
                console.error('Failed to register action cards handler:', error);
              }
            }

            // Handle all track events
            state.voiceManager.room.on(state.RoomEvent.TrackSubscribed, (track, publication, participant) => {
              // Only handle remote audio tracks (not our own microphone)
              if (track.kind === 'audio' && !participant.isLocal) {
                const audioElement = document.getElementById('roomAudioRenderer');
                if (audioElement) {
                  // Clear any existing tracks first
                  while (audioElement.firstChild) {
                    audioElement.removeChild(audioElement.firstChild);
                  }

                  // Attach new track
                  track.attach(audioElement);

                  // Force play with multiple attempts
                  const attemptPlay = async () => {
                    try {
                      await audioElement.play();
                      if (!state.agentAttributeState) {
                        applyDerivedState('speaking');
                      }
                    } catch (e) {
                      // Try unmute and set volume
                      audioElement.muted = false;
                      audioElement.volume = 1.0;

                      // Try again after a short delay
                      setTimeout(() => {
                        audioElement.play().then(() => {
                          if (!state.agentAttributeState) {
                            applyDerivedState('speaking');
                          }
                        }).catch(() => {
                          // Audio play failed, but continue
                        });
                      }, 100);
                    }
                  };

                  // Try to play immediately
                  attemptPlay();

                  document.addEventListener('click', attemptPlay, { once: true });
                  document.addEventListener('touchstart', attemptPlay, { once: true });

                  audioElement.onplaying = () => {
                    if (!state.agentAttributeState) {
                      applyDerivedState('speaking');
                    }
                  };

                  audioElement.onwaiting = () => {
                    if (!state.agentAttributeState) {
                      applyDerivedState('thinking', 8000);
                    }
                  };

                  audioElement.onpause = () => {
                    if (!state.agentAttributeState) {
                      applyDerivedState(getDefaultUiState(), 300);
                    }
                  };

                  audioElement.onended = () => {
                    if (!state.agentAttributeState) {
                      applyDerivedState(getDefaultUiState(), 300);
                    }
                  };

                } else {
                  console.error('roomAudioRenderer element not found');
                }
              } else {
                console.log('Ignoring non-remote audio track:', track.kind, participant.isLocal);
              }
            });

            // Also handle existing tracks that might already be subscribed
            console.log('Checking existing remote participants...', state.voiceManager.room.remoteParticipants.length);
            state.voiceManager.room.remoteParticipants.forEach((participant, index) => {
              console.log(`Participant ${index}:`, {
                identity: participant.identity,
                isLocal: participant.isLocal,
                trackPublications: participant.trackPublications.length
              });

              participant.trackPublications.forEach((publication) => {
                console.log('Publication:', {
                  kind: publication.kind,
                  source: publication.source,
                  track: !!publication.track,
                  isLocal: publication.isLocal
                });

                if (publication.kind === 'audio' && publication.track && !publication.isLocal) {
                  console.log('Found existing remote audio track, attaching...');
                  const audioElement = document.getElementById('roomAudioRenderer');
                  if (audioElement) {
                    publication.track.attach(audioElement);
                    audioElement.play().then(() => {
                      console.log('Existing track audio started!');
                    }).catch(e => {
                      console.log('Play failed for existing track:', e);
                    });
                  } else {
                    console.error('Audio element not found for existing track');
                  }
                }
              });
            });
          }
        }
      });

      return state.voiceManager;
    } catch (error) {
      console.error('Failed to initialize voice manager:', error);
      throw error;
    }
  }

  function showLiveKitVoicePanel() {
    const panel = document.getElementById('livekitVoicePanel');
    console.log('[DEBUG] showLiveKitVoicePanel called, panel exists:', !!panel);
    if (!panel) {
      console.error('[ERROR] LiveKit panel not found in DOM!');
      return;
    }
    panel.style.display = 'flex';
    document.body.classList.add('livekit-panel-open');
    updateLiveKitState('disconnected');
  }

  function clearDerivedStateTimeout() {
    if (state.derivedStateTimeout) {
      clearTimeout(state.derivedStateTimeout);
      state.derivedStateTimeout = null;
    }
  }

  function isAgentParticipant(participant) {
    const identity = participant?.identity || '';
    return identity.includes('agent') || !!participant?.attributes?.['lk.agent.state'];
  }

  function syncAgentStateFromParticipant(participant) {
    if (!isAgentParticipant(participant)) return false;

    const agentState = participant?.attributes?.['lk.agent.state'] || null;
    state.agentAttributeState = agentState;

    if (agentState) {
      clearDerivedStateTimeout();
      updateLiveKitState(agentState);
      return true;
    }

    return false;
  }

  function syncAgentStateFromRoom(room) {
    if (!room || !room.remoteParticipants) return false;

    let found = false;
    room.remoteParticipants.forEach((participant) => {
      if (!found && syncAgentStateFromParticipant(participant)) {
        found = true;
      }
    });

    return found;
  }

  function bindAgentStateListeners(room) {
    if (!room || state.boundRoom === room || !state.RoomEvent) return;
    state.boundRoom = room;

    room.on(state.RoomEvent.ParticipantConnected, (participant) => {
      syncAgentStateFromParticipant(participant);
    });

    room.on(state.RoomEvent.ParticipantAttributesChanged, (changed, participant) => {
      if (!isAgentParticipant(participant)) return;
      if (Object.prototype.hasOwnProperty.call(changed, 'lk.agent.state')) {
        syncAgentStateFromParticipant(participant);
      }
    });
  }

  function getDefaultUiState() {
    if (!state.voiceManager || !state.voiceManager.isReady()) {
      return state.isLiveKitStarted ? 'connecting' : 'disconnected';
    }

    if (state.agentAttributeState) {
      return state.agentAttributeState;
    }

    if (state.isLiveKitMuted || !state.voiceManager.isRecordingActive()) {
      return 'idle';
    }

    return 'listening';
  }

  function applyDerivedState(stateName, resetAfterMs = null) {
    if (state.agentAttributeState && ['initializing', 'idle', 'listening', 'thinking', 'speaking'].includes(stateName)) {
      return;
    }

    clearDerivedStateTimeout();
    updateLiveKitState(stateName);

    if (resetAfterMs) {
      state.derivedStateTimeout = setTimeout(() => {
        state.derivedStateTimeout = null;
        updateLiveKitState(getDefaultUiState());
      }, resetAfterMs);
    }
  }

  function closeLiveKitVoicePanel() {
    document.getElementById('livekitVoicePanel').style.display = 'none';
    document.body.classList.remove('livekit-panel-open');
    if (state.voiceManager && state.voiceManager.isRecordingActive()) {
      state.voiceManager.stopRecording();
    }
  }

  function updateLiveKitState(stateName) {
    const uiStateName = stateName === 'connected' ? 'idle' : stateName;
    state.currentUiState = uiStateName;
    const { STATE_COLORS, STATE_LABELS } = window.STATE_COLORS ? window : { STATE_COLORS: {}, STATE_LABELS: {} };
    const colors = STATE_COLORS[uiStateName] || { dot: '#9CA3AF', glow: 'rgba(107,114,128,0.15)' };
    const label = STATE_LABELS[uiStateName] || uiStateName;
    const isPulsing = ['listening', 'connecting', 'thinking'].includes(uiStateName);

    const stateDot = document.getElementById('livekitStateDot');
    const stateLabel = document.getElementById('livekitStateLabel');

    if (stateDot) {
      stateDot.style.backgroundColor = colors.dot;
      stateDot.style.boxShadow = `0 0 8px ${colors.glow}`;
      stateDot.style.animation = isPulsing ? 'pulse 1.5s infinite' : 'none';
    }

    if (stateLabel) {
      stateLabel.textContent = label;
      stateLabel.style.color = colors.dot;
    }

    // Update orb
    const orb = document.getElementById('livekitOrb');
    if (orb) {
      orb.style.boxShadow = `0 0 60px 12px ${colors.glow}, 0 0 120px 24px ${colors.glow}`;
      orb.style.opacity = (uiStateName === 'speaking' || uiStateName === 'listening') ? 0.7 : 0.25;
    }
    window.assistantLiveKitPanel?.updateWelcomeSection(state.isLiveKitStarted);
  }

  async function initializeLiveKit() {
    try {
      console.log('[VoiceLedger] Starting voice session...');
      updateLiveKitState('connecting');

      // Initialize voice manager
      const vm = await initializeVoiceManager();

      // Connect to LiveKit room with agent
      await vm.connect(
        state.tg?.initDataUnsafe?.user?.id || 'anonymous',
        state.tg?.initDataUnsafe?.user?.first_name || 'Guest',
        'user'
      );

      syncAgentStateFromRoom(vm.room) || applyDerivedState(getDefaultUiState());

      console.log('[VoiceLedger] Connected to LiveKit room!');

    } catch (error) {
      console.error('[VoiceLedger] session.start() failed:', error);
      const errorEl = document.getElementById('livekitConnectError');
      if (errorEl) {
        errorEl.textContent = error.message || 'Failed to connect. Check microphone permissions.';
        errorEl.style.display = 'block';
      }
      updateLiveKitState('failed');
    }
  }

  function enableVoiceActivityDetection() {
    if (state.isVoiceDetectionEnabled || !state.voiceManager) return;

    state.isVoiceDetectionEnabled = true;
    console.log('Enabling continuous voice activity detection');

    // Start in listening mode
    updateLiveKitState('listening');

    // Set up voice activity monitoring (this would need to be implemented in LiveKitVoiceManager)
    // For now, we'll use the manual recording as a fallback
  }

  function disableVoiceActivityDetection() {
    state.isVoiceDetectionEnabled = false;
    if (state.voiceActivityTimeout) {
      clearTimeout(state.voiceActivityTimeout);
      state.voiceActivityTimeout = null;
    }
    console.log('Disabling voice activity detection');
  }

  async function toggleLiveKitRecording() {
    // Only initialize once
    if (!state.voiceManager) {
      await initializeLiveKit();
      return;
    }

    // If already connected, just toggle mute/unmute
    if (state.voiceManager.isReady()) {
      await toggleLiveKitMute();
      return;
    }
  }

  function initializeFallbackVoice() {
    console.log('Using fallback voice recording');
    state.voiceManager = window.VoiceManager; // Use original VoiceManager
  }

  async function toggleRecording() {
    console.log('[DEBUG] toggleRecording called');
    try {
      // For now, skip dependencies and just show the panel
      console.log('[DEBUG] Skipping dependencies, showing panel directly...');
      // Try haptic feedback
      try {
        state.tg?.HapticFeedback?.impactOccurred?.('light');
      } catch (hapticErr) {
        // Ignore haptic feedback errors
      }
      console.log('[DEBUG] About to call showLiveKitVoicePanel...');
      showLiveKitVoicePanel();
      
      // Load dependencies in background after showing panel
      ensureDependencies().then(() => {
        console.log('[DEBUG] Dependencies loaded in background');
      }).catch(err => {
        console.error('[DEBUG] Background dependency loading failed:', err);
      });
    } catch (err) {
      console.error('Error showing LiveKit panel:', err);
    }
  }

  function toggleTranscript() {
    const isStarted = state.voiceManager && state.voiceManager.state !== 'disconnected' && state.voiceManager.state !== 'connecting';
    if (!isStarted || state.agentTranscriptions.length === 0) return;

    state.transcriptVisible = !state.transcriptVisible;
    const content = document.getElementById('transcriptContent');
    const toggleText = document.getElementById('transcriptToggleText');
    if (!content || !toggleText) return;

    if (state.transcriptVisible) {
      state.transcriptManuallyHidden = false;
      content.style.display = 'block';
      toggleText.textContent = 'Hide transcript';
    } else {
      state.transcriptManuallyHidden = true;
      content.style.display = 'none';
      toggleText.textContent = 'Show transcript';
    }
  }

  function updateTranscriptVisibility() {
    const sectionElement = document.getElementById('livekitTranscriptSection');
    const content = document.getElementById('transcriptContent');
    const toggleText = document.getElementById('transcriptToggleText');
    const isStarted = state.voiceManager && state.voiceManager.state !== 'disconnected' && state.voiceManager.state !== 'connecting';
    const hasTranscriptions = state.agentTranscriptions.length > 0;

    // Show transcript section only when LiveKit is connected AND transcriptions exist
    if (sectionElement) {
      if (isStarted && hasTranscriptions) {
        sectionElement.style.display = 'flex';
      } else {
        sectionElement.style.display = 'none';
        state.transcriptVisible = false;
        if (content) content.style.display = 'none';
        if (toggleText) toggleText.textContent = 'Show transcript';
      }
    }
  }

  function resetTranscriptUI() {
    const content = document.getElementById('transcriptContent');
    const toggleText = document.getElementById('transcriptToggleText');

    state.agentTranscriptions = [];
    state.transcriptVisible = false;
    state.transcriptManuallyHidden = false;

    renderTranscriptions();
    updateTranscriptVisibility();

    if (content) content.style.display = 'none';
    if (toggleText) toggleText.textContent = 'Show transcript';
  }

  function toggleActionCards() {
    const content = document.getElementById('actionCardsContent');
    const toggleText = document.getElementById('actionCardsToggleText');
    
    if (!content || !toggleText) {
      console.error('[VoiceLedger] Action cards toggle elements not found');
      return;
    }
    
    const isVisible = content.style.display !== 'none';
    
    if (isVisible) {
      content.style.display = 'none';
      toggleText.textContent = 'Show actions';
    } else {
      content.style.display = 'block';
      toggleText.textContent = 'Hide actions';
    }
    
  }

  function updateTranscriptions(text, isUser, segmentId, isFinal) {

    // Update or add transcription segment
    const existingSegment = state.agentTranscriptions.find(seg => seg.segmentId === segmentId);

    if (existingSegment) {
      // Append to existing segment
      if (!existingSegment.accumulatedText) {
        existingSegment.accumulatedText = '';
      }

      // Check if this is a new word or continuation
      if (existingSegment.lastText && text.startsWith(existingSegment.lastText)) {
        // Continuation - append the new part
        const newPart = text.slice(existingSegment.lastText.length);
        existingSegment.accumulatedText += newPart;
      } else {
        // New word or different text - append with space if needed
        if (existingSegment.accumulatedText && !existingSegment.accumulatedText.endsWith(' ')) {
          existingSegment.accumulatedText += ' ';
        }
        existingSegment.accumulatedText += text;
      }

      existingSegment.text = existingSegment.accumulatedText;
      existingSegment.isFinal = isFinal;
      existingSegment.lastText = text;
    } else {
      // Add new segment with accumulated text tracking
      state.agentTranscriptions.push({
        id: segmentId || Date.now().toString(),
        text: text,
        accumulatedText: text,
        isUser: isUser,
        segmentId: segmentId,
        isFinal: isFinal,
        lastText: text
      });
    }

    // Render transcriptions
    renderTranscriptions();

    // Update transcript UI visibility
    updateTranscriptVisibility();

  }

  function renderTranscriptions() {
    const messagesContainer = document.getElementById('transcriptMessages');
    const countElement = document.getElementById('transcriptCount');
    if (!messagesContainer || !countElement) return;

    // Clear and re-render
    messagesContainer.innerHTML = '';

    state.agentTranscriptions.forEach((seg, i) => {
      const messageDiv = document.createElement('div');
      messageDiv.style.cssText = 'font-size: 12px; line-height: 1.4; color: rgba(16,185,129,0.6);';

      const label = document.createElement('span');
      label.style.cssText = 'font-family: monospace; font-size: 9px; color: rgba(255,255,255,0.15); margin-right: 6px;';
      label.textContent = seg.isUser ? 'USER' : 'AI';

      const textSpan = document.createElement('span');
      textSpan.style.cssText = seg.isFinal ? 'color: rgba(16,185,129,0.8);' : 'color: rgba(16,185,129,0.5);';
      textSpan.textContent = seg.text;

      messageDiv.appendChild(label);
      messageDiv.appendChild(textSpan);
      messagesContainer.appendChild(messageDiv);
    });

    // Update count
    countElement.textContent = `${state.agentTranscriptions.length} segment${state.agentTranscriptions.length !== 1 ? 's' : ''}`;

    // Auto-scroll to bottom
    messagesContainer.scrollTop = messagesContainer.scrollHeight;
  }

  function addTranscriptMessage(text, isUser = false) {
    const messagesContainer = document.getElementById('transcriptMessages');
    const countElement = document.getElementById('transcriptCount');
    const sectionElement = document.getElementById('livekitTranscriptSection');
    if (!messagesContainer || !countElement || !sectionElement) return;

    // Show transcript section if not visible
    if (sectionElement.style.display === 'none') {
      sectionElement.style.display = 'block';
    }

    // Add message
    const messageDiv = document.createElement('div');
    messageDiv.style.cssText = 'font-size: 12px; line-height: 1.4; color: rgba(16,185,129,0.6);';

    const label = document.createElement('span');
    label.style.cssText = 'font-family: monospace; font-size: 9px; color: rgba(255,255,255,0.15); margin-right: 6px;';
    label.textContent = isUser ? 'USER' : 'AI';

    const textSpan = document.createElement('span');
    textSpan.textContent = text;

    messageDiv.appendChild(label);
    messageDiv.appendChild(textSpan);
    messagesContainer.appendChild(messageDiv);

    // Update count
    transcriptMessages.push({ text, isUser, timestamp: Date.now() });
    countElement.textContent = `${transcriptMessages.length} segment${transcriptMessages.length !== 1 ? 's' : ''}`;

    // Auto-scroll to bottom
    messagesContainer.scrollTop = messagesContainer.scrollHeight;

    // Auto-show transcript if this is the first message
    if (transcriptMessages.length === 1 && !state.transcriptVisible) {
      toggleTranscript();
    }
  }

  async function toggleLiveKitMute() {
    if (!state.voiceManager || !state.voiceManager.isReady()) return;

    try {
      // Use Room-based recording toggle
      await state.voiceManager.toggleRecording();

      // Update muted state
      state.isLiveKitMuted = !state.voiceManager.isRecordingActive();
      console.log('[VoiceLedger] Microphone', state.isLiveKitMuted ? 'muted' : 'unmuted');

      // Update UI
      const muteBtn = document.getElementById('livekitMuteBtn');
      const mutedIndicator = document.getElementById('livekitMutedIndicator');
      if (muteBtn) {
        muteBtn.style.background = state.isLiveKitMuted ? 'rgba(245,158,11,0.2)' : 'rgba(255,255,255,0.08)';
        muteBtn.style.color = state.isLiveKitMuted ? '#F59E0B' : 'rgba(255,255,255,0.7)';
        muteBtn.title = state.isLiveKitMuted ? 'Unmute microphone' : 'Mute microphone';
      }
      if (mutedIndicator) {
        mutedIndicator.style.display = state.isLiveKitMuted ? 'block' : 'none';
      }
      applyDerivedState(getDefaultUiState());
    } catch (error) {
      console.error('Failed to toggle mute:', error);
    }
  }

  async function endLiveKitSession() {
    if (state.isDisconnecting) return; // Prevent recursive calls
    
    state.isDisconnecting = true;
    try {
      if (state.voiceManager) {
        // Reset transcription handler flag before disconnecting
        state.voiceManager.transcriptionHandlerRegistered = false;
        await state.voiceManager.disconnect();
        state.voiceManager = null;
      }
      state.isLiveKitStarted = false;
      state.isLiveKitMuted = false;
      state.agentAttributeState = null;
      state.boundRoom = null;
      clearDerivedStateTimeout();
      closeLiveKitVoicePanel();

      // Reset transcript state
      resetTranscriptUI();

      // Clear action cards
      window.assistantLiveKitPanel?.clearActionCards();
      
      // Reset panel UI to initial state
      window.assistantLiveKitPanel?.resetToInitialState();
    } finally {
      state.isDisconnecting = false;
    }
  }

  function init({ tg, micBtn }) {
    state.tg = tg;
    state.micBtn = micBtn;

    if (state.micBtn && !state.micBtn.dataset.livekitVoiceBound) {
      state.micBtn.addEventListener('click', toggleRecording);
      state.micBtn.dataset.livekitVoiceBound = 'true';
    }

    ensureDependencies().catch(error => {
      console.error('Failed to initialize LiveKit voice dependencies:', error);
    });
  }

  function isReady() {
    return !!(state.voiceManager && state.voiceManager.isReady());
  }

  function externalUpdateState(stateName) {
    if (!state.voiceManager || !state.voiceManager.isReady()) {
      updateLiveKitState(stateName);
      return;
    }

    if (['connecting', 'disconnected', 'failed'].includes(stateName)) {
      updateLiveKitState(stateName);
    }
  }

  window.closeLiveKitVoicePanel = closeLiveKitVoicePanel;
  window.initializeLiveKit = initializeLiveKit;
  window.toggleLiveKitMute = toggleLiveKitMute;
  window.endLiveKitSession = endLiveKitSession;
  window.toggleTranscript = toggleTranscript;
  window.toggleActionCards = toggleActionCards;

  window.AssistantLiveKitVoice = {
    init,
    isReady,
    updateState: externalUpdateState,
    toggleRecording,
    toggleMute: toggleLiveKitMute,
    toggleActionCards,
    endSession: endLiveKitSession,
  };
})();
