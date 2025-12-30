/**
 * Voice Controller for Bilingual Voice UI
 * 
 * Handles:
 * - Microphone recording using MediaRecorder API
 * - Audio upload to backend
 * - Real-time conversation display
 * - TTS audio playback
 * - Language switching
 * 
 * Date: December 24, 2025
 * Lab 17: Bilingual Voice UI - Track 2
 */

class VoiceController {
    constructor() {
        this.mediaRecorder = null;
        this.audioChunks = [];
        this.isRecording = false;
        this.stream = null;
        this.currentLanguage = 'en';
        this.conversationHistory = [];
        this.useWebSocket = true; // Try WebSocket first, fall back to HTTP
        this.ws = null;
        
        // DOM elements
        this.micButton = document.getElementById('mic-button');
        this.recordingIndicator = document.getElementById('recording-indicator');
        this.processingIndicator = document.getElementById('processing-indicator');
        this.processingText = document.getElementById('processing-text');
        this.conversationDiv = document.getElementById('conversation-history');
        this.statusMessage = document.getElementById('status-message');
        this.ttsPlayer = document.getElementById('tts-player');
        this.langEnBtn = document.getElementById('lang-en');
        this.langAmBtn = document.getElementById('lang-am');
        this.userNameSpan = document.getElementById('user-name');
        this.logoutBtn = document.getElementById('logout-btn');
        
        // Debug: Check if elements exist
        console.log('VoiceController initializing...');
        console.log('micButton:', this.micButton);
        console.log('conversationDiv:', this.conversationDiv);
        
        if (!this.micButton) {
            console.error('ERROR: mic-button element not found!');
            return;
        }
        
        this.init();
    }
    
    async init() {
        console.log('Running init()...');
        
        // Load user profile and set language
        await this.loadUserProfile();
        
        // Event listeners
        if (this.micButton) {
            this.micButton.addEventListener('click', () => {
                console.log('Microphone button clicked!');
                this.toggleRecording();
            });
            console.log('✅ Microphone click handler attached');
        }
        
        if (this.langEnBtn) {
            this.langEnBtn.addEventListener('click', () => this.switchLanguage('en'));
        }
        
        if (this.langAmBtn) {
            this.langAmBtn.addEventListener('click', () => this.switchLanguage('am'));
        }
        
        if (this.logoutBtn) {
            this.logoutBtn.addEventListener('click', () => this.logout());
        }
        
        // TTS player events
        if (this.ttsPlayer) {
            this.ttsPlayer.addEventListener('ended', () => {
                console.log('TTS playback finished');
            });
        }
        
        console.log('✅ VoiceController initialized successfully');
    }
    
    getToken() {
        return localStorage.getItem('jwt_token');
    }
    
    async loadUserProfile() {
        try {
            const token = this.getToken();
            
            if (!token) {
                // Anonymous user - use default settings
                this.userNameSpan.textContent = 'Guest';
                this.currentLanguage = localStorage.getItem('voice_language') || 'en';
                this.updateLanguageButtons();
                return;
            }
            
            const response = await fetch('/api/users/me/profile', {
                headers: {
                    'Authorization': `Bearer ${token}`
                }
            });
            
            if (!response.ok) {
                // If auth fails, treat as anonymous
                this.userNameSpan.textContent = 'Guest';
                this.currentLanguage = localStorage.getItem('voice_language') || 'en';
                this.updateLanguageButtons();
                return;
            }
            
            const user = await response.json();
            this.userNameSpan.textContent = user.name;
            this.currentLanguage = user.preferred_language;
            
            // Update language button states
            this.updateLanguageButtons();
            
        } catch (error) {
            console.error('Failed to load user profile:', error);
            // Treat as anonymous on error
            this.userNameSpan.textContent = 'Guest';
            this.currentLanguage = localStorage.getItem('voice_language') || 'en';
            this.updateLanguageButtons();
        }
    }
    
    updateLanguageButtons() {
        if (this.currentLanguage === 'en') {
            this.langEnBtn.classList.add('active');
            this.langAmBtn.classList.remove('active');
        } else {
            this.langEnBtn.classList.remove('active');
            this.langAmBtn.classList.add('active');
        }
    }
    
    async switchLanguage(lang) {
        if (lang === this.currentLanguage) return;
        
        try {
            const token = this.getToken();
            
            if (token) {
                // Authenticated user - update on server
                const response = await fetch('/api/users/me/language', {
                    method: 'PATCH',
                    headers: {
                        'Authorization': `Bearer ${token}`,
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({ language: lang })
                });
                
                if (!response.ok) {
                    throw new Error('Failed to update language');
                }
            } else {
                // Anonymous user - store locally
                localStorage.setItem('voice_language', lang);
            }
            
            this.currentLanguage = lang;
            this.updateLanguageButtons();
            
            const langName = lang === 'en' ? 'English' : 'Amharic (አማርኛ)';
            this.showStatus(`Language switched to ${langName}`, 'success');
            
            // Clear conversation history (fresh start with new language)
            this.conversationHistory = [];
            this.conversationDiv.innerHTML = `
                <div class="message system">
                    <div class="message-content">
                        Language switched to ${langName}. Start speaking!
                    </div>
                </div>
            `;
            
        } catch (error) {
            console.error('Failed to switch language:', error);
            // Still switch locally even if server update fails
            this.currentLanguage = lang;
            localStorage.setItem('voice_language', lang);
            this.updateLanguageButtons();
        }
    }
    
    async toggleRecording() {
        if (this.isRecording) {
            this.stopRecording();
        } else {
            await this.startRecording();
        }
    }
    
    async startRecording() {
        try {
            // Request microphone access
            this.stream = await navigator.mediaDevices.getUserMedia({ 
                audio: {
                    channelCount: 1,
                    sampleRate: 16000,
                    echoCancellation: true,
                    noiseSuppression: true
                }
            });
            
            // Create MediaRecorder
            const options = { mimeType: 'audio/webm' };
            if (!MediaRecorder.isTypeSupported(options.mimeType)) {
                options.mimeType = 'audio/ogg';
            }
            
            this.mediaRecorder = new MediaRecorder(this.stream, options);
            this.audioChunks = [];
            
            this.mediaRecorder.ondataavailable = (event) => {
                if (event.data.size > 0) {
                    this.audioChunks.push(event.data);
                }
            };
            
            this.mediaRecorder.onstop = async () => {
                await this.processRecording();
            };
            
            // Start recording
            this.mediaRecorder.start();
            this.isRecording = true;
            
            // Update UI
            this.micButton.classList.add('recording');
            this.recordingIndicator.classList.remove('hidden');
            this.showStatus('🎤 Recording... Click again to stop', 'info');
            
        } catch (error) {
            console.error('Error accessing microphone:', error);
            this.showStatus(
                'Error accessing microphone. Please check permissions.',
                'error'
            );
        }
    }
    
    stopRecording() {
        if (this.mediaRecorder && this.mediaRecorder.state !== 'inactive') {
            this.mediaRecorder.stop();
            this.isRecording = false;
            
            // Stop all tracks
            if (this.stream) {
                this.stream.getTracks().forEach(track => track.stop());
            }
            
            // Update UI
            this.micButton.classList.remove('recording');
            this.recordingIndicator.classList.add('hidden');
        }
    }
    
    async processRecording() {
        try {
            // Create audio blob
            const audioBlob = new Blob(this.audioChunks, { 
                type: this.mediaRecorder.mimeType 
            });
            
            console.log(`Audio recorded: ${audioBlob.size} bytes, type: ${audioBlob.type}`);
            
            // Show processing indicator
            this.processingIndicator.classList.remove('hidden');
            this.processingText.textContent = 'Uploading...';
            
            // Try WebSocket first, fall back to HTTP
            if (this.useWebSocket) {
                try {
                    await this.uploadAudioWebSocket(audioBlob);
                } catch (wsError) {
                    console.warn('WebSocket failed, falling back to HTTP:', wsError);
                    this.useWebSocket = false;
                    await this.uploadAudio(audioBlob);
                }
            } else {
                await this.uploadAudio(audioBlob);
            }
            
        } catch (error) {
            console.error('Error processing recording:', error);
            this.showStatus(`Error: ${error.message}`, 'error');
            this.processingIndicator.classList.add('hidden');
        }
    }
    
    async uploadAudioWebSocket(audioBlob) {
        return new Promise((resolve, reject) => {
            const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
            const token = this.getToken();
            const wsUrl = `${protocol}//${window.location.host}/api/voice/ws/voice${token ? '?token=' + token : ''}`;
            
            console.log('Connecting to WebSocket:', wsUrl);
            
            const ws = new WebSocket(wsUrl);
            let resolved = false;
            
            ws.onopen = () => {
                console.log('✅ WebSocket connected');
                
                // Send language preference
                ws.send(JSON.stringify({ language: this.currentLanguage }));
            };
            
            ws.onmessage = async (event) => {
                try {
                    const message = JSON.parse(event.data);
                    console.log('WebSocket message:', message.status);
                    
                    switch (message.status) {
                        case 'ready':
                            // Server ready, send audio
                            console.log('Sending audio data...');
                            const arrayBuffer = await audioBlob.arrayBuffer();
                            ws.send(arrayBuffer);
                            break;
                            
                        case 'transcribing':
                            this.processingText.textContent = '🎤 Transcribing...';
                            break;
                            
                        case 'transcribed':
                            this.processingText.textContent = '💭 Processing...';
                            this.addMessage(message.transcript, 'user');
                            break;
                            
                        case 'processing':
                            this.processingText.textContent = '🤔 Thinking...';
                            break;
                            
                        case 'generating_audio':
                            this.processingText.textContent = '🔊 Generating audio...';
                            break;
                            
                        case 'complete':
                            const data = message.data;
                            
                            // Display message
                            const messageToDisplay = data.message_text || data.message;
                            this.addMessage(messageToDisplay, 'assistant');
                            
                            // Show registration prompt if needed
                            if (data.needs_auth && data.telegram_bot_url) {
                                this.showRegistrationPrompt(data.telegram_bot_url);
                            }
                            
                            // Play TTS
                            if (data.audio_url) {
                                await this.playTTS(data.audio_url);
                            }
                            
                            // Hide processing indicator
                            this.processingIndicator.classList.add('hidden');
                            
                            // Show status
                            if (data.ready_to_execute) {
                                this.showStatus('✅ Command executed successfully!', 'success');
                            }
                            
                            ws.close();
                            resolved = true;
                            resolve();
                            break;
                            
                        case 'error':
                            throw new Error(message.error || 'Unknown error');
                    }
                } catch (error) {
                    console.error('WebSocket message error:', error);
                    if (!resolved) {
                        ws.close();
                        reject(error);
                    }
                }
            };
            
            ws.onerror = (error) => {
                console.error('WebSocket error:', error);
                if (!resolved) {
                    reject(new Error('WebSocket connection failed'));
                }
            };
            
            ws.onclose = () => {
                console.log('WebSocket closed');
                if (!resolved) {
                    reject(new Error('WebSocket closed unexpectedly'));
                }
            };
            
            // Timeout after 60 seconds
            setTimeout(() => {
                if (!resolved) {
                    ws.close();
                    reject(new Error('WebSocket timeout'));
                }
            }, 60000);
        });
    }
    
    async uploadAudio(audioBlob) {
        try {
            const formData = new FormData();
            formData.append('file', audioBlob, 'voice.webm');
            
            const response = await fetch('/api/voice/upload', {
                method: 'POST',
                headers: {
                    'Authorization': `Bearer ${this.getToken()}`
                },
                body: formData
            });
            
            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.detail || 'Upload failed');
            }
            
            const data = await response.json();
            console.log('Voice response:', data);
            
            // Update processing stage
            this.processingText.textContent = 'Processing...';
            
            // Display transcript
            this.addMessage(data.transcript, 'user');
            
            // Display message_text (with links/emojis) or fallback to message
            const messageToDisplay = data.message_text || data.message;
            this.addMessage(messageToDisplay, 'assistant');
            
            // Show registration prompt if auth needed
            if (data.needs_auth && data.telegram_bot_url) {
                this.showRegistrationPrompt(data.telegram_bot_url);
            }
            
            // Play TTS audio if available (uses message_spoken)
            if (data.audio_url) {
                await this.playTTS(data.audio_url);
            }
            
            // Hide processing indicator
            this.processingIndicator.classList.add('hidden');
            
            // Show status
            if (data.status === 'success') {
                this.showStatus('✅ Command executed successfully!', 'success');
            } else if (data.needs_clarification) {
                this.showStatus('🤔 Please provide more information', 'info');
            }
            
        } catch (error) {
            console.error('Upload failed:', error);
            this.showStatus(`Error: ${error.message}`, 'error');
            this.processingIndicator.classList.add('hidden');
        }
    }
    
    async playTTS(audioUrl) {
        try {
            const headers = {};
            const token = this.getToken();
            if (token) {
                headers['Authorization'] = `Bearer ${token}`;
            }
            
            const response = await fetch(audioUrl, {
                headers: headers
            });
            
            if (!response.ok) {
                throw new Error('Failed to load audio');
            }
            
            const audioBlob = await response.blob();
            const audioObjectUrl = URL.createObjectURL(audioBlob);
            
            this.ttsPlayer.src = audioObjectUrl;
            await this.ttsPlayer.play();
            
            console.log('Playing TTS audio');
            
        } catch (error) {
            console.error('TTS playback failed:', error);
            // Non-fatal - user can still read the text
        }
    }
    
    addMessage(text, role) {
        const messageDiv = document.createElement('div');
        messageDiv.className = `message ${role}`;
        
        const contentDiv = document.createElement('div');
        contentDiv.className = 'message-content';
        contentDiv.textContent = text;
        
        messageDiv.appendChild(contentDiv);
        this.conversationDiv.appendChild(messageDiv);
        
        // Scroll to bottom
        this.conversationDiv.scrollTop = this.conversationDiv.scrollHeight;
        
        // Add to history
        this.conversationHistory.push({ role, text });
    }
    
    showStatus(message, type = 'info') {
        this.statusMessage.textContent = message;
        this.statusMessage.className = `status-message ${type}`;
        this.statusMessage.classList.remove('hidden');
        
        // Auto-hide after 5 seconds
        setTimeout(() => {
            this.statusMessage.classList.add('hidden');
        }, 5000);
    }
    
    showRegistrationPrompt(telegramBotUrl) {
        // Check if prompt already exists
        if (document.querySelector('.auth-prompt')) {
            return;
        }
        
        const prompt = document.createElement('div');
        prompt.className = 'auth-prompt';
        prompt.innerHTML = `
            <div class="auth-banner">
                <p><strong>🔒 Registration Required</strong></p>
                <p>To save batches and use full features, please register:</p>
                <a href="${telegramBotUrl}" class="btn-register" target="_blank" rel="noopener">
                    📱 Register on Telegram (2 min)
                </a>
                <button class="btn-dismiss" onclick="this.closest('.auth-prompt').remove()">×</button>
            </div>
        `;
        
        // Insert after conversation display
        const conversationDiv = document.getElementById('conversation');
        if (conversationDiv && conversationDiv.parentNode) {
            conversationDiv.parentNode.insertBefore(prompt, conversationDiv.nextSibling);
        }
    }
    
    logout() {
        localStorage.removeItem('jwt_token');
        window.location.href = '/login.html';
    }
}

// Note: VoiceController is instantiated in voice-ui.html
// to allow access via window.voiceController
