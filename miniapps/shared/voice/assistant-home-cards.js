(() => {
  const styleId = 'assistant-home-cards-styles';

  function ensureStyles() {
    if (document.getElementById(styleId)) return;

    const style = document.createElement('style');
    style.id = styleId;
    style.textContent = `
      .home-cards-container {
        display: grid;
        grid-template-columns: 1fr;
        gap: 16px;
        padding: 16px;
        max-width: 400px;
        margin: 0 auto;
        width: 100%;
      }

      @media (min-width: 640px) {
        .home-cards-container {
          grid-template-columns: 1fr 1fr;
          gap: 12px;
          max-width: 600px;
        }
      }

      /* Voice Card */
      .voice-card {
        position: relative;
        overflow: hidden;
        border-radius: 16px;
        background: linear-gradient(135deg, #1f2937 0%, #111827 50%, #030712 100%);
        border: 1px solid rgba(255, 255, 255, 0.05);
        cursor: pointer;
        transition: all 0.3s ease;
        min-height: 200px;
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        text-align: center;
        padding: 20px;
        gap: 16px;
      }

      .voice-card:hover {
        transform: scale(1.02);
        box-shadow: 0 20px 40px rgba(16, 185, 129, 0.2);
        border-color: rgba(16, 185, 129, 0.2);
      }

      .voice-card:active {
        transform: scale(0.98);
      }

      .voice-card-bg {
        position: absolute;
        inset: 0;
        opacity: 0.4;
        pointer-events: none;
      }

      /* Floating orbs */
      .voice-orb-float-1 {
        position: absolute;
        top: -24px;
        right: -24px;
        width: 112px;
        height: 112px;
        border-radius: 50%;
        background: rgba(16, 185, 129, 0.1);
        filter: blur(32px);
        animation: floatSlow 8s ease-in-out infinite;
        pointer-events: none;
      }

      .voice-orb-float-2 {
        position: absolute;
        bottom: -16px;
        left: -16px;
        width: 80px;
        height: 80px;
        border-radius: 50%;
        background: rgba(6, 182, 212, 0.08);
        filter: blur(32px);
        animation: floatSlower 10s ease-in-out infinite;
        pointer-events: none;
      }

      @keyframes floatSlow {
        0%, 100% { transform: translateY(0px) rotate(0deg); }
        50% { transform: translateY(-10px) rotate(5deg); }
      }

      @keyframes floatSlower {
        0%, 100% { transform: translateY(0px) rotate(0deg); }
        50% { transform: translateY(-8px) rotate(-3deg); }
      }

      .voice-orb {
        position: relative;
        width: 96px;
        height: 96px;
        display: flex;
        align-items: center;
        justify-content: center;
        z-index: 1;
      }

      .voice-orb-svg {
        position: absolute;
        inset: 0;
        width: 100%;
        height: 100%;
        opacity: 0.4; /* Make rings much more subtle like web frontend */
      }

      .voice-orb-img {
        width: 40px;
        height: 40px;
        border-radius: 12px;
        object-fit: contain;
        transition: transform 0.3s ease;
        position: relative;
        z-index: 1;
      }

      .voice-card:hover .voice-orb img {
        transform: scale(1.1);
      }

      .voice-card-content {
        z-index: 1;
        display: flex;
        flex-direction: column;
        gap: 8px;
        align-items: center;
      }

      .voice-card-title {
        font-size: 14px;
        font-weight: 600;
        color: rgba(255, 255, 255, 0.9);
        margin: 0;
        line-height: 1.2;
      }

      .voice-card-subtitle {
        font-size: 11px;
        color: rgba(255, 255, 255, 0.35);
        margin: 0;
        line-height: 1.3;
      }

      .voice-card-cta {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        font-size: 10px;
        font-weight: 500;
        color: rgba(52, 211, 153, 0.8);
        text-transform: uppercase;
        letter-spacing: 0.05em;
        transition: color 0.2s ease;
        z-index: 1;
      }

      .voice-card:hover .voice-card-cta {
        color: rgba(52, 211, 153, 1);
      }

      .voice-card-pulse {
        width: 6px;
        height: 6px;
        border-radius: 50%;
        background: #34d399;
        animation: pulse 2s infinite;
      }

      @keyframes pulse {
        0%, 100% { opacity: 1; transform: scale(1); }
        50% { opacity: 0.5; transform: scale(1.2); }
      }

      /* Chat Card */
      .chat-card {
        position: relative;
        overflow: hidden;
        border-radius: 16px;
        background: white;
        border: 1px solid #e5e7eb;
        transition: all 0.2s ease;
        min-height: 200px;
        display: flex;
        flex-direction: column;
        padding: 20px;
      }

      .chat-card:hover {
        border-color: #d1d5db;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
      }

      .chat-card-bg {
        position: absolute;
        inset: 0;
        opacity: 0.04;
        pointer-events: none;
      }

      .chat-card-header {
        display: flex;
        align-items: center;
        gap: 10px;
        margin-bottom: 16px;
        position: relative;
        z-index: 1;
      }

      .chat-card-icon {
        width: 36px;
        height: 36px;
        border-radius: 12px;
        background: #f3f4f6;
        display: flex;
        align-items: center;
        justify-content: center;
        color: #6b7280;
        position: relative;
      }

      .chat-card-icon svg {
        width: 18px;
        height: 18px;
      }

      .chat-card-status {
        position: absolute;
        top: -2px;
        right: -2px;
        width: 8px;
        height: 8px;
        border-radius: 50%;
        background: #34d399;
        border: 2px solid white;
      }

      .chat-card-status::after {
        content: '';
        position: absolute;
        inset: -4px;
        border-radius: 50%;
        background: #34d399;
        opacity: 0.4;
        animation: ping 2s infinite;
      }

      @keyframes ping {
        0% { transform: scale(1); opacity: 0.4; }
        100% { transform: scale(1.5); opacity: 0; }
      }

      .chat-card-info {
        flex: 1;
      }

      .chat-card-title {
        font-size: 14px;
        font-weight: 600;
        color: #1f2937;
        margin: 0;
        line-height: 1.2;
      }

      .chat-card-subtitle {
        font-size: 11px;
        color: #9ca3af;
        margin: 2px 0 0 0;
        line-height: 1.3;
      }

      .chat-prompts {
        display: grid;
        grid-template-columns: 1fr;
        gap: 6px;
        flex: 1;
        position: relative;
        z-index: 1;
      }

      .chat-prompt {
        padding: 8px 12px;
        border-radius: 8px;
        background: #f9fafb;
        color: #6b7280;
        font-size: 11px;
        text-align: left;
        cursor: pointer;
        transition: all 0.15s ease;
        border: 1px solid transparent;
        line-height: 1.4;
      }

      .chat-prompt:hover {
        background: #f3f4f6;
        color: #374151;
        border-color: #e5e7eb;
      }

      .chat-prompt:active {
        background: #e5e7eb;
        transform: scale(0.97);
      }

      .chat-more {
        font-size: 10px;
        color: #d1d5db;
        text-align: center;
        margin-top: 12px;
        position: relative;
        z-index: 1;
      }

      /* Greeting Section */
      .greeting-section {
        text-align: center;
        margin-bottom: 24px;
        padding: 0 16px;
        animation: fadeInUp 0.6s ease-out;
      }

      .greeting-logo {
        display: inline-block;
        margin-bottom: 16px;
        position: relative;
      }

      .greeting-logo-ring {
        position: absolute;
        top: -10px;
        left: -10px;
        width: calc(100% + 20px);
        height: calc(100% + 20px);
      }

      .greeting-logo-img {
        width: 64px;
        height: 64px;
        border-radius: 16px;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
        position: relative;
        z-index: 1;
      }

      .greeting-title {
        font-size: 20px;
        font-weight: 600;
        color: #1f2937;
        margin: 0 0 4px 0;
        line-height: 1.2;
        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
      }

      .greeting-subtitle {
        font-size: 14px;
        color: #9ca3af;
        margin: 0;
        line-height: 1.4;
      }

      @keyframes fadeInUp {
        from {
          opacity: 0;
          transform: translateY(20px);
        }
        to {
          opacity: 1;
          transform: translateY(0);
        }
      }

      /* Responsive adjustments */
      @media (max-width: 639px) {
        .home-cards-container {
          padding: 12px;
          gap: 12px;
        }

        .greeting-section {
          margin-bottom: 20px;
          padding: 0 12px;
        }

        .greeting-logo-img {
          width: 56px;
          height: 56px;
        }

        .greeting-title {
          font-size: 18px;
        }

        .greeting-subtitle {
          font-size: 13px;
        }

        .voice-card, .chat-card {
          min-height: 180px;
          padding: 16px;
        }

        .voice-orb {
          width: 80px;
          height: 80px;
        }

        .voice-orb img {
          width: 32px;
          height: 32px;
        }

        .voice-card-title {
          font-size: 13px;
        }

        .chat-card-header {
          gap: 8px;
          margin-bottom: 12px;
        }

        .chat-card-icon {
          width: 32px;
          height: 32px;
        }

        .chat-card-icon svg {
          width: 16px;
          height: 16px;
        }
      }
    `;
    document.head.appendChild(style);
  }

  function createGreetingSection(options = {}) {
    const logoUrl = 'https://violet-rainy-toad-577.mypinata.cloud/ipfs/bafybeic6pclaqgbaaz6qqvlz2ssjgbzae4y7e76d2pobbwfxs2cviwgyqa';
    const { greetingTitle = 'Welcome to Voice Ledger', greetingSubtitle = 'Choose how you\'d like to interact' } = options;
    
    return `
      <div class="greeting-section">
        <div class="greeting-logo">
          <svg class="greeting-logo-ring" viewBox="0 0 84 84" fill="none">
            <rect x="2" y="2" width="80" height="80" rx="22" stroke="url(#logo-ring-grad)" stroke-width="0.7" stroke-dasharray="4 8" opacity="0.35">
              <animateTransform attributeName="transform" type="rotate" from="0 42 42" to="360 42 42" dur="20s" repeatCount="indefinite" />
            </rect>
            <circle cx="8" cy="8" r="1" fill="#10B981" opacity="0.3">
              <animate attributeName="opacity" values="0.2;0.5;0.2" dur="3s" repeatCount="indefinite" />
            </circle>
            <circle cx="76" cy="76" r="1" fill="#06B6D4" opacity="0.25">
              <animate attributeName="opacity" values="0.15;0.45;0.15" dur="4s" repeatCount="indefinite" />
            </circle>
            <defs>
              <linearGradient id="logo-ring-grad" x1="0" y1="0" x2="84" y2="84">
                <stop offset="0%" stopColor="#10B981" />
                <stop offset="100%" stopColor="#06B6D4" />
              </linearGradient>
            </defs>
          </svg>
          <img src="${logoUrl}" alt="WAGA" class="greeting-logo-img" />
        </div>
        <h2 class="greeting-title">${greetingTitle}</h2>
        <p class="greeting-subtitle">${greetingSubtitle}</p>
      </div>
    `;
  }

  function createVoiceCard(onClick) {
    const logoUrl = 'https://violet-rainy-toad-577.mypinata.cloud/ipfs/bafybeic6pclaqgbaaz6qqvlz2ssjgbzae4y7e76d2pobbwfxs2cviwgyqa';
    
    return `
      <div class="voice-card" onclick="window.AssistantHomeCards?.handleVoiceClick()">
        <!-- Floating orbs (miniature) -->
        <div class="voice-orb-float-1"></div>
        <div class="voice-orb-float-2"></div>

        <!-- Animated logo with orbital rings -->
        <div class="voice-orb">
          <svg class="voice-orb-svg" viewBox="0 0 96 96">
            <!-- Outer dashed orbit -->
            <circle cx="48" cy="48" r="44" fill="none" stroke="#10B981" stroke-width="0.5" stroke-dasharray="3 8" stroke-opacity="0.3">
              <animateTransform attributeName="transform" type="rotate" from="0 48 48" to="360 48 48" dur="16s" repeatCount="indefinite" />
            </circle>
            <!-- Inner counter-rotating ring -->
            <circle cx="48" cy="48" r="35" fill="none" stroke="#10B981" stroke-width="0.3" stroke-opacity="0.15">
              <animateTransform attributeName="transform" type="rotate" from="360 48 48" to="0 48 48" dur="12s" repeatCount="indefinite" />
            </circle>
            <!-- Breathing ring around logo -->
            <circle cx="48" cy="48" fill="none" stroke="#10B981" stroke-width="0.5" stroke-opacity="0.25">
              <animate attributeName="r" values="24;27;24" dur="3s" repeatCount="indefinite" />
            </circle>
            <!-- Orbital dot -->
            <circle r="1.2" fill="#34D399" opacity="0.5">
              <animateMotion dur="8s" repeatCount="indefinite" path="M48,4 A44,44 0 1,1 47.99,4" />
            </circle>
            <!-- Soft glow behind logo -->
            <circle cx="48" cy="48" r="18" fill="#10B981" opacity="0.06">
              <animate attributeName="r" values="16;20;16" dur="4s" repeatCount="indefinite" />
              <animate attributeName="opacity" values="0.04;0.08;0.04" dur="4s" repeatCount="indefinite" />
            </circle>
          </svg>
          <!-- Logo center -->
          <img src="${logoUrl}" alt="Voice Ledger" class="voice-orb-img" />
        </div>

        <div class="voice-card-content">
          <p class="voice-card-title">Speak to The Voice Ledger</p>
          <p class="voice-card-subtitle">Your Supply Chain Assistant</p>
          
          <span class="voice-card-cta">
            <span class="voice-card-pulse"></span>
            Tap to start
          </span>
        </div>
      </div>
    `;
  }

  function createChatCard(prompts, onPromptClick) {
    const promptList = prompts || [
      { text: 'Show my batches', key: 'prompt_1' },
      { text: 'What containers are available?', key: 'prompt_2' },
      { text: 'Check EUDR compliance for my last batch', key: 'prompt_3' },
      { text: 'Trace lineage for batch ETH-001', key: 'prompt_4' }
    ];

    return `
      <div class="chat-card">
        <!-- Subtle dot-grid pattern -->
        <div class="chat-card-bg">
          <svg viewBox="0 0 100 100" preserveAspectRatio="xMidYMid slice">
            ${Array.from({ length: 8 }, (_, row) =>
              Array.from({ length: 8 }, (_, col) =>
                `<circle cx="${8 + col * 12}" cy="${8 + row * 12}" r="0.8" fill="currentColor" />`
              ).join('')
            ).join('')}
          </svg>
        </div>

        <div class="chat-card-header">
          <div class="chat-card-icon">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
              <path d="M7.5 8.25h9m-9 3H12m-9.75 1.51c0 1.6 1.123 2.994 2.707 3.227 1.129.166 2.27.293 3.423.379.35.026.67.21.865.501L12 21l2.755-4.133a1.14 1.14 0 01.865-.501 48.172 48.172 0 003.423-.379c1.584-.233 2.707-1.626 2.707-3.228V6.741c0-1.602-1.123-2.995-2.707-3.228A48.394 48.394 0 0012 3c-2.392 0-4.744.175-7.043.513C3.373 3.746 2.25 5.14 2.25 6.741v6.018z" />
            </svg>
            <span class="chat-card-status"></span>
          </div>
          <div class="chat-card-info">
            <p class="chat-card-title">Type to ask</p>
            <p class="chat-card-subtitle">Chat with the assistant below</p>
          </div>
        </div>

        <div class="chat-prompts">
          ${promptList.map(prompt => `
            <div class="chat-prompt" data-prompt="${prompt.text}" data-i18n="${prompt.key}">
              ${prompt.text}
            </div>
          `).join('')}
        </div>

        <div class="chat-more">+ 4 more prompts, just start typing</div>
      </div>
    `;
  }

  function bindEvents(container, voiceCallback, promptCallback) {
    if (!container || container.dataset.homeCardsBound === 'true') return;

    container.addEventListener('click', (event) => {
      const voiceCard = event.target.closest('.voice-card');
      if (voiceCard && voiceCallback) {
        voiceCallback();
        return;
      }

      const prompt = event.target.closest('.chat-prompt');
      if (prompt && promptCallback) {
        const promptText = prompt.getAttribute('data-prompt') || prompt.textContent.trim();
        promptCallback(promptText);
        return;
      }
    });

    container.dataset.homeCardsBound = 'true';
  }

  ensureStyles();

  window.AssistantHomeCards = {
    render(container, options = {}) {
      if (!container) return;
      
      const { onVoiceClick, onPromptClick, prompts, greetingTitle, greetingSubtitle } = options;
      
      bindEvents(container, onVoiceClick, onPromptClick);
      
      container.innerHTML = `
        ${createGreetingSection({ greetingTitle, greetingSubtitle })}
        <div class="home-cards-container">
          ${createVoiceCard(onVoiceClick)}
          ${createChatCard(prompts, onPromptClick)}
        </div>
      `;
    },

    handleVoiceClick() {
      // Trigger the existing mic button click
      const micBtn = document.getElementById('micBtn');
      if (micBtn) {
        micBtn.click();
      }
    },

    clear(container) {
      if (!container) return;
      container.innerHTML = '';
      delete container.dataset.homeCardsBound;
    }
  };
})();
