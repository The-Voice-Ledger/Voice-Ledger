(() => {
  const styleId = 'assistant-livekit-panel-styles';

  if (!document.getElementById(styleId)) {
    const style = document.createElement('style');
    style.id = styleId;
    style.textContent = `
    /* Override body constraints when LiveKit panel is shown */
    body.livekit-panel-open {
      padding: 0 !important;
      overflow: hidden !important;
    }
    
    .livekit-voice-panel {
      position: fixed !important;
      top: 0 !important;
      left: 0 !important;
      right: 0 !important;
      bottom: 0 !important;
      width: 100vw !important;
      height: 100vh !important;
      max-width: none !important;
      max-height: none !important;
      z-index: 99999 !important;
      overflow: hidden !important;
      display: none !important;
      flex: none !important;
      margin: 0 !important;
      padding: 0 !important;
      border-radius: 0 !important;
    }
    
    .livekit-voice-panel[style*="display: flex"] {
      display: flex !important;
    }
    
    /* Override body constraints when LiveKit panel is open */
    body.livekit-panel-open {
      padding: 0 !important;
      overflow: hidden !important;
      display: block !important;
      height: 100vh !important;
    }
    
    /* Ensure main content container is also overridden */
    body.livekit-panel-open > * {
      display: none !important;
    }
    
    body.livekit-panel-open .livekit-voice-panel {
      display: flex !important;
    }`;
    document.head.appendChild(style);
  }

  function injectLiveKitPanel() {
    if (document.getElementById('livekitVoicePanel')) return;

    document.body.insertAdjacentHTML('beforeend', `
  <!-- LiveKit Voice Panel - Popup overlay -->
  <div class="livekit-voice-panel" id="livekitVoicePanel" style="display: none;">
    <!-- Background -->
    <div style="position: absolute; inset: 0; background: linear-gradient(to bottom right, #1a1a1a, #2d2d2d, #0a0a0a);"></div>
    
    <!-- Audio renderer for agent playback -->
    <audio id="roomAudioRenderer" style="position: absolute; inset: 0;" autoplay playsinline></audio>
    
    <!-- Main content -->
    <div style="position: relative; z-index: 10; width: 100vw; height: 100vh; display: flex; flex-direction: column;">
      <!-- Top bar -->
      <div style="display: flex; align-items: center; justify-content: space-between; padding: 20px;">
        <div style="display: flex; align-items: center; gap: 12px;">
          <img src="https://violet-rainy-toad-577.mypinata.cloud/ipfs/bafybeic6pclaqgbaaz6qqvlz2ssjgbzae4y7e76d2pobbwfxs2cviwgyqa" alt="WAGA" style="height: 32px; width: auto; border-radius: 8px;">
          <div>
            <div style="color: rgba(255,255,255,0.85); font-size: 14px; font-weight: 600;">The Voice Ledger</div>
            <div style="color: rgba(255,255,255,0.3); font-size: 10px; font-family: monospace;">voice assistant</div>
          </div>
        </div>
        <button onclick="closeLiveKitVoicePanel()" style="width: 36px; height: 36px; border-radius: 8px; border: none; background: transparent; color: rgba(255,255,255,0.3); cursor: pointer; display: flex; align-items: center; justify-content: center; transition: all 0.2s;" onmouseover="this.style.color='rgba(255,255,255,0.7)'; this.style.background='rgba(255,255,255,0.05)'" onmouseout="this.style.color='rgba(255,255,255,0.3)'; this.style.background='transparent'">
          <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round">
            <path d="M4 4l8 8M12 4l-8 8"></path>
          </svg>
        </button>
      </div>

      <!-- Split Panel Content -->
      <div style="flex: 1; display: flex; min-height: 0;">
        <!-- LEFT PANEL: Central Orb and Controls (45% width) -->
        <div style="width: 45%; display: flex; flex-direction: column; align-items: center; justify-content: center; position: relative;">
          <!-- Central glowing orb with state -->
          <div id="livekitOrb" style="width: 200px; height: 200px; border-radius: 50%; background: radial-gradient(circle, rgba(16,185,129,0.3) 0%, rgba(16,185,129,0.1) 50%, transparent 70%); display: flex; align-items: center; justify-content: center; position: relative; transition: all 0.3s ease;">
            <!-- Inner orb -->
            <div style="width: 120px; height: 120px; border-radius: 50%; background: radial-gradient(circle, rgba(16,185,129,0.5) 0%, rgba(16,185,129,0.2) 50%, transparent 70%); display: flex; align-items: center; justify-content: center;">
              <!-- State indicator -->
              <div id="livekitStateDot" style="width: 16px; height: 16px; border-radius: 50%; background: #10B981; box-shadow: 0 0 12px rgba(16,185,129,0.4);"></div>
            </div>
            
            <!-- Pulsing ring animation -->
            <div style="position: absolute; inset: 0; border-radius: 50%; border: 2px solid rgba(16,185,129,0.3); animation: pulse-ring 2s infinite;"></div>
          </div>
          
          <!-- State label + dot (mt-6 = 24px spacing -->
          <div style="margin-top: 24px; display: flex; flex-direction: column; align-items: center; gap: 6px;">
            <div style="display: flex; align-items: center; gap: 8px;">
              <div id="livekitStateDot" style="width: 8px; height: 8px; border-radius: 50%; background: #10B981; box-shadow: 0 0 8px rgba(16,185,129,0.4);"></div>
              <span id="livekitStateLabel" style="color: rgba(255,255,255,0.8); font-size: 14px; font-weight: 500; text-transform: uppercase; letter-spacing: 1px;">Ready</span>
            </div>
          </div>

          <!-- Controls (mt-8 = 32px spacing  -->
          <div style="margin-top: 32px; display: flex; flex-direction: column; align-items: center; gap: 12px;">
            <div id="livekitConnectError" style="display: none; padding: 12px 16px; border-radius: 12px; background: rgba(239,68,68,0.1); border: 1px solid rgba(239,68,68,0.2); color: #FCA5A5; font-size: 12px; text-align: center; max-width: 300px;"></div>
            
            <button id="livekitStartBtn" onclick="initializeLiveKit()" style="padding: 16px 32px; border-radius: 16px; border: none; background: linear-gradient(to bottom right, #10B981, #059669); color: white; font-weight: 600; font-size: 14px; cursor: pointer; transition: all 0.2s; box-shadow: 0 4px 12px rgba(16,185,129,0.3);" onmouseover="this.style.transform='scale(1.05)'; this.style.boxShadow='0 6px 16px rgba(16,185,129,0.4)'" onmouseout="this.style.transform='scale(1)'; this.style.boxShadow='0 4px 12px rgba(16,185,129,0.3)'">
              Start Voice Session
            </button>
            
            <div id="livekitActiveControls" style="display: none; gap: 16px;">
              <button id="livekitMuteBtn" onclick="toggleLiveKitMute()" style="width: 56px; height: 56px; border-radius: 50%; border: none; background: rgba(255,255,255,0.08); color: rgba(255,255,255,0.7); cursor: pointer; display: flex; align-items: center; justify-content: center; transition: all 0.2s;" title="Mute microphone">
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
                  <rect x="9" y="2" width="6" height="11" rx="3"></rect>
                  <path d="M5 12a7 7 0 0014 0"></path>
                  <line x1="12" y1="19" x2="12" y2="23"></line>
                  <line x1="8" y1="23" x2="16" y2="23"></line>
                </svg>
              </button>
              <button onclick="endLiveKitSession()" style="width: 56px; height: 56px; border-radius: 50%; border: none; background: rgba(239,68,68,0.15); color: #F87171; cursor: pointer; display: flex; align-items: center; justify-content: center; transition: all 0.2s; border: 1px solid rgba(239,68,68,0.1);" title="End voice session">
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
                  <path d="M10.68 13.31a16 16 0 003.41 2.6l1.27-1.27a2 2 0 012.11-.45 12.84 12.84 0 002.73.8 2 2 0 011.72 2v3a2 2 0 01-2.18 2 19.79 19.79 0 01-8.63-3.07 19.42 19.42 0 01-6-6A19.79 19.79 0 012 4.18 2 2 2 0 014 2h3a2 2 0 012 1.72 12.84 12.84 0 00.7 2.81 2 2 0 01-.45 2.11L8.09 9.91a16 16 0 002.59 3.4z"></path>
                  <line x1="1" y1="1" x2="23" y2="23"></line>
                </svg>
              </button>
            </div>
            
            <!-- Footer -->
            <div style="margin-top: 24px; display: flex; flex-direction: column; align-items: center; gap: 4px;">
              <span style="font-size: 9px; color: rgba(255,255,255,0.15); font-family: 'Display', sans-serif; letter-spacing: 0.05em;">The Voice Ledger</span>
              <span style="font-size: 8px; color: rgba(255,255,255,0.08); font-family: 'Mono', monospace; letter-spacing: 0.025em;">Powered by LiveKit â€¢ Deepgram â€¢ OpenAI</span>
            </div>
          </div>
        </div>

        <!-- RIGHT PANEL: Transcript (55% width) -->
        <div style="width: 55%; display: flex; flex-direction: column; min-height: 0; overflow-y: auto; padding: 20px;">
          
          <!-- Welcome Cards-->
          <div id="welcomeCards" style="width: 100%;">
            <!-- Section header with tech accent -->
            <div style="display: flex; align-items: center; gap: 12px; margin-bottom: 16px;">
              <div style="position: relative;">
                <div style="width: 4px; height: 20px; border-radius: 2px; background: linear-gradient(to bottom, #10B981, #06B6D4, #8B5CF6);"></div>
                <div style="position: absolute; inset: -4px; width: 12px; height: 28px; border-radius: 6px; background: rgba(16,185,129,0.1); filter: blur(4px);"></div>
              </div>
              <div style="display: flex; align-items: center; gap: 8px;">
                <span id="welcomeHeaderText" style="color: rgba(255,255,255,0.6); font-size: 11px; font-weight: 600; text-transform: uppercase; letter-spacing: 1px;">What I can do</span>
                <svg width="40" height="1" style="color: rgba(255,255,255,0.1);">
                  <line x1="0" y1="0.5" x2="40" y2="0.5" stroke="currentColor" stroke-width="1" stroke-dasharray="2 3" />
                </svg>
              </div>
            </div>

            <!-- Welcome card-->
            <div id="welcomeCard" style="margin-bottom: 16px; position: relative; border-radius: 12px; overflow: hidden; background: rgba(255,255,255,0.02); border: 1px solid rgba(255,255,255,0.04);">
              <svg style="position: absolute; inset: 0; width: 100%; height: 100%; pointer-events: none;" viewBox="0 0 300 40" preserveAspectRatio="none" fill="none">
                <path d="M0 20h80 M80 20v-10 M80 10h40 M120 10v10 M120 20h60 M180 20v-8 M180 12h120" stroke="#10B981" stroke-width="0.3" opacity="0.08" />
                <circle cx="80" cy="20" r="1.5" fill="#10B981" opacity="0.1" />
                <circle cx="120" cy="20" r="1.5" fill="#06B6D4" opacity="0.1" />
                <circle cx="180" cy="20" r="1.5" fill="#8B5CF6" opacity="0.08" />
              </svg>
              <p style="position: relative; z-index: 10; color: rgba(255,255,255,0.3); font-size: 11px; padding: 10px; line-height: 1.5;">
                Start a voice session and ask me anything about your Ethiopian coffee supply chain.
              </p>
            </div>
          </div>

          <!-- Transcript Section -->
          <div id="livekitTranscriptSection" style="display: none; flex-direction: column; gap: 12px;">
            <!-- Transcript Header -->
            <button id="transcriptToggleBtn" onclick="toggleTranscript()" style="display: flex; align-items: center; gap: 6px; padding: 8px 12px; border: none; background: rgba(255,255,255,0.04); border-radius: 8px; color: rgba(255,255,255,0.25); font-size: 11px; cursor: pointer; transition: all 0.2s; backdrop-filter: blur(8px); width: fit-content;">
              <svg width="12" height="12" viewBox="0 0 12 12" fill="none" stroke="currentColor" stroke-width="1">
                <path d="M2 4h8M2 6h6M2 8h7" />
              </svg>
              <span id="transcriptToggleText">Show transcript</span>
              <span id="transcriptCount" style="margin-left: auto; font-size: 9px; color: rgba(255,255,255,0.15);">0 segments</span>
            </button>
            
            <!-- Transcript Content -->
            <div id="transcriptContent" style="display: none; overflow: hidden; border-radius: 12px; padding: 16px; background: rgba(255,255,255,0.04); border: 1px solid rgba(255,255,255,0.06); backdrop-filter: blur(8px);">
              <div id="transcriptMessages" style="display: flex; flex-direction: column; gap: 8px;">
                <!-- Transcript messages will be added here -->
              </div>
            </div>
          </div>
        </div>
      </div>
      
      <!-- Footer -->
      <div style="display: flex; justify-content: center; align-items: center; gap: 4px; padding: 20px; color: rgba(255,255,255,0.15); font-size: 9px;">
        <span>The Voice Ledger</span>
        <span>Â·</span>
        <span style="font-family: monospace;">Powered by LiveKit</span>
      </div>
    </div>
    
    <!-- Audio renderer for agent playback -->
    <audio id="roomAudioRenderer" style="position: absolute; inset: 0;" autoplay playsinline></audio>
  </div>`);
  }

  if (!document.getElementById('livekitVoicePanel')) {
    if (document.body) {
      injectLiveKitPanel();
    } else {
      document.addEventListener('DOMContentLoaded', injectLiveKitPanel, { once: true });
    }
  }

  window.assistantLiveKitPanel = {
    updateWelcomeSection(isLiveKitStarted) {
      const welcomeCards = document.getElementById('welcomeCards');
      if (!welcomeCards) return;

      if (isLiveKitStarted) {
        welcomeCards.style.display = 'none';
      } else {
        welcomeCards.style.display = 'block';
      }
    }
  };
})();
