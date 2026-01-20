/**
 * Shared Voice Recording and Processing Module for Mini Apps
 * 
 * Provides unified voice interface for all Telegram Mini Apps
 * Integrates with backend /api/voice/upload endpoint
 * 
 * VOICE-FIRST ARCHITECTURE:
 * - Context-aware: Sends app context to AI
 * - Action execution: Handles returned actions
 * - Workflow support: Multi-turn conversations for creation
 */

/**
 * Custom error class for voice operations (Priority 4: Error Handling)
 */
class VoiceError extends Error {
    constructor(message, category, context = {}) {
        super(message);
        this.name = 'VoiceError';
        this.category = category;
        this.context = context;
        this.timestamp = new Date().toISOString();
    }
    
    static CATEGORIES = {
        NETWORK: 'network',
        TIMEOUT: 'timeout',
        VALIDATION: 'validation',
        SERVER: 'server',
        PERMISSION: 'permission',
        UNKNOWN: 'unknown'
    };
    
    isRetryable() {
        return [
            VoiceError.CATEGORIES.NETWORK,
            VoiceError.CATEGORIES.TIMEOUT,
            VoiceError.CATEGORIES.SERVER
        ].includes(this.category);
    }
}

class VoiceInterface {
    constructor(telegram, options = {}) {
        this.tg = telegram;
        this.mediaRecorder = null;
        this.audioChunks = [];
        this.isRecording = false;
        this.userId = this.tg.initDataUnsafe.user?.id;
        this.language = 'en'; // Default, can be overridden
        
        // Context and workflow support
        this.context = options.context || {};
        this.sessionId = null;
        this.workflowActive = false;
        this.actionHandlers = {};
        this.workflowHandlers = {};
        
        // Audio validation settings (Priority 2: Input Validation)
        this.minRecordingDuration = 500; // ms
        this.maxRecordingDuration = 120000; // 2 minutes
        this.maxFileSize = 25 * 1024 * 1024; // 25MB
        this.recordingStartTime = null;
        
        // Retry settings (Priority 4: Enhanced Error Handling)
        this.maxRetries = 3;
        this.retryDelays = [1000, 2000, 4000]; // Exponential backoff: 1s, 2s, 4s
        this.currentRetryCount = 0;
        this.retryAborted = false;
        
        // TTS playback control (Priority 5: TTS Controls)
        this.currentAudio = null;
        this.isPlayingAudio = false;
        this.lastResponse = null; // Store last response for replay
        this.audioProgressInterval = null;
    }
    
    /**
     * Set or update app context (Priority 1: Context Precision)
     * Use this to dynamically update context as the user navigates
     */
    setContext(context) {
        this.context = { ...this.context, ...context };
        console.log('Voice context updated:', this.context);
    }
    
    /**
     * Completely replace the context (Priority 1: Context Precision)
     * Use when switching views entirely
     */
    replaceContext(context) {
        this.context = context;
        console.log('Voice context replaced:', this.context);
    }
    
    /**
     * Clear specific context keys (Priority 1: Context Precision)
     * Use when elements are no longer relevant
     */
    clearContextKeys(...keys) {
        keys.forEach(key => delete this.context[key]);
        console.log('Voice context keys cleared:', keys);
    }
    
    /**
     * Register action handler
     */
    onAction(actionType, handler) {
        this.actionHandlers[actionType] = handler;
    }
    
    /**
     * Register workflow handler
     */
    onWorkflow(workflowType, handler) {
        this.workflowHandlers[workflowType] = handler;
    }

    /**
     * Start recording audio from microphone
     * Enhanced with better audio settings and auto-stop (Priority 2)
     */
    async startRecording(voiceButton) {
        try {
            const stream = await navigator.mediaDevices.getUserMedia({ 
                audio: {
                    echoCancellation: true,
                    noiseSuppression: true,
                    autoGainControl: true
                }
            });
            this.mediaRecorder = new MediaRecorder(stream, {
                mimeType: 'audio/webm;codecs=opus'
            });
            
            this.audioChunks = [];
            this.recordingStartTime = Date.now();
            
            this.mediaRecorder.ondataavailable = (event) => {
                if (event.data.size > 0) {
                    this.audioChunks.push(event.data);
                }
            };
            
            this.mediaRecorder.onstop = async () => {
                const audioBlob = new Blob(this.audioChunks, { type: 'audio/webm' });
                await this.uploadAndProcess(audioBlob, voiceButton);
            };
            
            this.mediaRecorder.start();
            this.isRecording = true;
            
            if (voiceButton) {
                voiceButton.classList.add('recording');
            }
            
            // Auto-stop after max duration (Priority 2: Input Validation)
            setTimeout(() => {
                if (this.isRecording) {
                    console.log('Max recording duration reached, auto-stopping');
                    this.stopRecording(voiceButton);
                }
            }, this.maxRecordingDuration);
            
            this.tg.HapticFeedback.impactOccurred('medium');
            
            console.log('Voice recording started');
            return true;
            
        } catch (error) {
            this.handleMicrophoneError(error);
            return false;
        }
    }

    /**
     * Stop recording audio
     * Enhanced with duration validation (Priority 2)
     */
    async stopRecording(voiceButton) {
        if (this.mediaRecorder && this.mediaRecorder.state !== 'inactive') {
            const recordingDuration = Date.now() - this.recordingStartTime;
            
            // Check minimum duration (Priority 2: Input Validation)
            if (recordingDuration < this.minRecordingDuration) {
                this.tg.showAlert('Recording too short. Please speak for at least 1 second.');
                this.cleanupRecording(voiceButton);
                return;
            }
            
            this.mediaRecorder.stop();
            this.mediaRecorder.stream.getTracks().forEach(track => track.stop());
            this.isRecording = false;
            
            if (voiceButton) {
                voiceButton.classList.remove('recording');
            }
            
            this.tg.HapticFeedback.impactOccurred('light');
            console.log(`Voice recording stopped (${recordingDuration}ms)`);
        }
    }

    /**
     * Upload audio to backend and process with voice AI
     * Enhanced with validation and error handling (Priority 2 & 4)
     */
    async uploadAndProcess(audioBlob, voiceButton) {
        // Reset retry state
        this.currentRetryCount = 0;
        this.retryAborted = false;
        
        return await this.attemptUpload(audioBlob, voiceButton);
    }
    
    /**
     * Attempt upload with exponential backoff retry
     * Priority 4: Enhanced Error Handling
     */
    async attemptUpload(audioBlob, voiceButton, isRetry = false) {
        try {
            // Check network connectivity first (Priority 4: Error Handling)
            if (!navigator.onLine) {
                throw new VoiceError(
                    'No internet connection',
                    VoiceError.CATEGORIES.NETWORK,
                    { retryCount: this.currentRetryCount }
                );
            }
            
            // Validate file size (Priority 2: Input Validation)
            if (audioBlob.size > this.maxFileSize) {
                throw new VoiceError(
                    `Recording too large (${(audioBlob.size / 1024 / 1024).toFixed(1)}MB). Maximum is 25MB.`,
                    VoiceError.CATEGORIES.VALIDATION,
                    { fileSize: audioBlob.size }
                );
            }
            
            // Check if audio has content (Priority 2: Input Validation)
            if (!isRetry) {
                const soundCheck = await this.checkAudioHasSound(audioBlob);
                if (!soundCheck.hasSound) {
                    throw new VoiceError(
                        'No audio detected. Please check your microphone and try again.',
                        VoiceError.CATEGORIES.VALIDATION,
                        { maxAmplitude: soundCheck.maxAmplitude }
                    );
                }
                console.log(`Audio validated: ${soundCheck.duration.toFixed(1)}s, max amplitude: ${soundCheck.maxAmplitude.toFixed(3)}`);
            }
            
            // Show processing indicator
            const statusText = isRetry 
                ? `Retrying... (${this.currentRetryCount + 1}/${this.maxRetries})`
                : 'Processing voice...';
            this.tg.MainButton.setText(statusText);
            this.tg.MainButton.show();
            this.tg.MainButton.showProgress();
            
            // Sanitize context before sending (Priority 2: Input Validation)
            const sanitizedContext = this.sanitizeContext(this.context);
            
            // Create form data
            const formData = new FormData();
            formData.append('file', audioBlob, 'voice_message.webm');
            formData.append('language', this.language);
            formData.append('context', JSON.stringify(sanitizedContext));
            
            // Add session ID if in active workflow
            if (this.sessionId) {
                formData.append('session_id', this.sessionId);
            }
            
            // Upload to backend with timeout (Priority 4: Error Handling)
            const controller = new AbortController();
            const timeoutId = setTimeout(() => controller.abort(), 60000); // 60s timeout
            
            try {
                const response = await fetch('/api/voice/upload', {
                    method: 'POST',
                    headers: {
                        'X-Telegram-User-Id': String(this.userId)
                    },
                    body: formData,
                    signal: controller.signal
                });
                
                clearTimeout(timeoutId);
                
                if (!response.ok) {
                    const errorText = await response.text();
                    
                    // Categorize HTTP errors
                    let category = VoiceError.CATEGORIES.SERVER;
                    if (response.status >= 500) {
                        category = VoiceError.CATEGORIES.SERVER;
                    } else if (response.status === 413) {
                        category = VoiceError.CATEGORIES.VALIDATION;
                    } else if (response.status === 408 || response.status === 504) {
                        category = VoiceError.CATEGORIES.TIMEOUT;
                    }
                    
                    throw new VoiceError(
                        `Upload failed (${response.status}): ${errorText}`,
                        category,
                        { status: response.status, responseText: errorText }
                    );
                }
                
                const result = await response.json();
                
                // Success - reset retry count
                this.currentRetryCount = 0;
                
                // Hide progress
                this.tg.MainButton.hideProgress();
                this.tg.MainButton.hide();
            
            // Handle workflow state
            if (result.workflow_state) {
                this.sessionId = result.session_id;
                this.workflowActive = true;
                console.log('Workflow started:', result.workflow_state);
            }
            
            if (result.workflow_completed) {
                this.sessionId = null;
                this.workflowActive = false;
                console.log('Workflow completed');
            }
            
            // Execute actions if present
            if (result.action) {
                await this.executeAction(result.action);
            }
            
            // Trigger workflow handlers if workflow started
            if (result.workflow && result.workflow.type) {
                const handler = this.workflowHandlers[result.workflow.type];
                if (handler) {
                    await handler(result.workflow);
                }
            }
            
            // Show response to user
            await this.displayResponse(result);
            
            return result;
            
            } catch (fetchError) {
                clearTimeout(timeoutId);
                
                // Handle specific fetch errors (Priority 4: Error Handling)
                if (fetchError.name === 'AbortError') {
                    throw new VoiceError(
                        'Request timeout - server took too long to respond',
                        VoiceError.CATEGORIES.TIMEOUT,
                        { retryCount: this.currentRetryCount }
                    );
                }
                
                // Network errors
                if (fetchError.message.includes('Failed to fetch') || fetchError.message.includes('NetworkError')) {
                    throw new VoiceError(
                        'Network error - could not reach server',
                        VoiceError.CATEGORIES.NETWORK,
                        { originalError: fetchError.message }
                    );
                }
                
                throw fetchError;
            }
            
        } catch (error) {
            console.error('Error uploading voice:', error);
            this.tg.MainButton.hideProgress();
            this.tg.MainButton.hide();
            
            // Check if we should retry (Priority 4: Exponential Backoff)
            if (error instanceof VoiceError && error.isRetryable() && 
                this.currentRetryCount < this.maxRetries && !this.retryAborted) {
                
                const delay = this.retryDelays[this.currentRetryCount];
                this.currentRetryCount++;
                
                // Show retry notification with countdown
                await this.showRetryNotification(delay, this.currentRetryCount, this.maxRetries);
                
                // Wait for backoff delay
                await new Promise(resolve => setTimeout(resolve, delay));
                
                // Check if user aborted during delay
                if (this.retryAborted) {
                    throw error;
                }
                
                // Retry the upload
                return await this.attemptUpload(audioBlob, voiceButton, true);
            }
            
            // Enhanced error handling with categorization (Priority 4)
            await this.handleUploadError(error, audioBlob, voiceButton);
            throw error;
        }
    }
    
    /**
     * Show retry notification with countdown (Priority 4: Enhanced Error Handling)
     */
    async showRetryNotification(delayMs, attemptNumber, maxAttempts) {
        const delaySec = delayMs / 1000;
        
        return new Promise(resolve => {
            this.tg.showPopup({
                title: '🔄 Retrying...',
                message: `Attempt ${attemptNumber} of ${maxAttempts}\n\nRetrying in ${delaySec} seconds...`,
                buttons: [
                    { id: 'cancel', type: 'cancel', text: 'Cancel' }
                ]
            }, (buttonId) => {
                if (buttonId === 'cancel') {
                    this.retryAborted = true;
                }
                resolve();
            });
        });
    }
    
    /**
     * Handle upload errors with specific messages
     * Priority 4: Enhanced Error Handling with VoiceError categorization
     */
    async handleUploadError(error, audioBlob, voiceButton) {
        let errorTitle = '❌ Error';
        let errorMessage = error.message || 'An unexpected error occurred';
        let showRetry = false;
        
        // Use VoiceError categorization if available
        if (error instanceof VoiceError) {
            switch (error.category) {
                case VoiceError.CATEGORIES.NETWORK:
                    errorTitle = '📡 Network Error';
                    errorMessage = 'Could not reach the server. Please check your internet connection.';
                    showRetry = false; // Already retried with exponential backoff
                    break;
                case VoiceError.CATEGORIES.TIMEOUT:
                    errorTitle = '⏱️ Timeout';
                    errorMessage = 'The server took too long to respond. The request has been retried automatically.';
                    showRetry = false; // Already retried
                    break;
                case VoiceError.CATEGORIES.VALIDATION:
                    errorTitle = '⚠️ Validation Error';
                    errorMessage = error.message;
                    showRetry = false; // Validation errors are not retryable
                    break;
                case VoiceError.CATEGORIES.SERVER:
                    errorTitle = '🔧 Server Error';
                    errorMessage = 'Server error occurred. The request has been retried automatically.';
                    showRetry = false; // Already retried
                    break;
                case VoiceError.CATEGORIES.PERMISSION:
                    errorTitle = '🔒 Permission Error';
                    errorMessage = error.message;
                    showRetry = false;
                    break;
                default:
                    errorTitle = '❌ Error';
                    errorMessage = error.message;
            }
            
            // Log error for analytics
            this.logError(error);
        } else {
            // Fallback for non-VoiceError errors
            if (!navigator.onLine || error.message.includes('network')) {
                errorTitle = '📡 Network Error';
                errorMessage = 'Could not reach the server. Please check your internet connection.';
            } else if (error.message.includes('timeout')) {
                errorTitle = '⏱️ Timeout';
                errorMessage = 'The server is taking too long to respond.';
            }
        }
        
        const buttons = [];
        
        if (showRetry && audioBlob) {
            buttons.push({ id: 'retry', type: 'default', text: '🔄 Retry' });
        }
        
        buttons.push({ id: 'record_again', type: 'default', text: '🎤 Record Again' });
        buttons.push({ id: 'close', type: 'cancel' });
        
        return new Promise(resolve => {
            this.tg.showPopup({
                title: errorTitle,
                message: errorMessage,
                buttons: buttons
            }, async (buttonId) => {
                if (buttonId === 'retry' && audioBlob) {
                    try {
                        this.tg.MainButton.setText('Retrying...');
                        this.tg.MainButton.show();
                        this.tg.MainButton.showProgress();
                        
                        // Manual retry starts fresh
                        this.currentRetryCount = 0;
                        this.retryAborted = false;
                        
                        // Retry upload
                        await this.uploadAndProcess(audioBlob, voiceButton);
                        resolve();
                    } catch (retryError) {
                        // If retry fails, just log it
                        console.error('Retry failed:', retryError);
                        this.tg.MainButton.hideProgress();
                        this.tg.MainButton.hide();
                    }
                }
                resolve();
            });
        });
    }
    
    /**
     * Log error for analytics (Priority 4: Error Analytics)
     */
    logError(error) {
        const errorLog = {
            timestamp: error.timestamp || new Date().toISOString(),
            category: error.category || 'unknown',
            message: error.message,
            context: error.context || {},
            userId: this.userId,
            sessionId: this.sessionId
        };
        
        console.error('VoiceError logged:', errorLog);
        
        // TODO: Send to backend analytics endpoint
        // fetch('/api/analytics/voice-error', {
        //     method: 'POST',
        //     headers: { 'Content-Type': 'application/json' },
        //     body: JSON.stringify(errorLog)
        // }).catch(e => console.error('Failed to log error:', e));
    }
    
    /**
     * Execute action returned by AI
     */
    async executeAction(action) {
        if (!action || !action.type) {
            return;
        }
        
        console.log('Executing action:', action);
        
        const handler = this.actionHandlers[action.type];
        if (handler) {
            try {
                await handler(action.params || action);
            } catch (error) {
                console.error('Action handler error:', error);
                this.tg.showAlert(`Failed to execute action: ${error.message}`);
            }
        } else {
            console.warn('No handler registered for action type:', action.type);
        }
    }

    /**
     * Display AI response with text and audio playback (Priority 5: Enhanced TTS)
     */
    async displayResponse(result) {
        // Store for replay functionality
        this.lastResponse = result;
        
        // Show replay button if it exists
        const replayBtn = document.getElementById('voiceReplayButton');
        if (replayBtn && result.audio_url) {
            replayBtn.style.display = 'block';
        }
        
        // Show transcript and response
        const message = `🎙️ You said: "${result.transcript || 'N/A'}"\n\n` +
                       `🤖 Response: ${result.message || 'No response'}`;
        
        const buttons = [];
        
        if (result.audio_url) {
            buttons.push({ id: 'play', type: 'default', text: '🔊 Play Audio' });
        }
        
        buttons.push({ id: 'close', type: 'close' });
        
        this.tg.showPopup({
            title: 'Voice Assistant',
            message: message,
            buttons: buttons
        }, (buttonId) => {
            if (buttonId === 'play' && result.audio_url) {
                this.playAudioWithControls(result.audio_url, result.message);
            }
        });
    }

    /**
     * Play TTS audio with full controls (Priority 5: TTS Controls)
     * Includes pause, resume, stop, and progress indicator
     */
    async playAudioWithControls(audioUrl, responseText = '') {
        try {
            // Stop any currently playing audio
            this.stopCurrentAudio();
            
            // Create new audio instance
            this.currentAudio = new Audio(audioUrl);
            this.isPlayingAudio = true;
            
            // Show initial playing state
            this.tg.MainButton.setText('🔊 Playing...');
            this.tg.MainButton.show();
            this.tg.MainButton.showProgress(false);
            
            // Setup audio event listeners
            this.currentAudio.addEventListener('loadedmetadata', () => {
                console.log(`Audio duration: ${this.currentAudio.duration}s`);
                
                // Show progress for long responses (>5s)
                if (this.currentAudio.duration > 5) {
                    this.startProgressIndicator();
                }
            });
            
            this.currentAudio.addEventListener('timeupdate', () => {
                // Update progress
                if (this.currentAudio.duration > 5) {
                    const progress = (this.currentAudio.currentTime / this.currentAudio.duration) * 100;
                    const elapsed = Math.floor(this.currentAudio.currentTime);
                    const total = Math.floor(this.currentAudio.duration);
                    this.tg.MainButton.setText(`🔊 Playing... ${elapsed}s / ${total}s`);
                }
            });
            
            this.currentAudio.addEventListener('ended', () => {
                this.stopCurrentAudio();
                this.tg.HapticFeedback.notificationOccurred('success');
            });
            
            this.currentAudio.addEventListener('error', (e) => {
                console.error('Audio playback error:', e);
                this.stopCurrentAudio();
                this.tg.showAlert('Audio playback failed');
            });
            
            // Setup MainButton as pause/stop control
            this.tg.MainButton.onClick(() => {
                if (this.isPlayingAudio) {
                    if (this.currentAudio.paused) {
                        this.resumeAudio();
                    } else {
                        this.pauseAudio();
                    }
                }
            });
            
            // Play audio
            await this.currentAudio.play();
            this.tg.HapticFeedback.impactOccurred('light');
            
        } catch (error) {
            console.error('Error playing audio:', error);
            this.stopCurrentAudio();
            this.tg.showAlert('Could not play audio response');
        }
    }

    /**
     * Pause current audio playback (Priority 5: TTS Controls)
     */
    pauseAudio() {
        if (this.currentAudio && !this.currentAudio.paused) {
            this.currentAudio.pause();
            this.tg.MainButton.setText('⏸️ Paused - Tap to Resume');
            this.tg.HapticFeedback.impactOccurred('light');
            console.log('Audio paused');
        }
    }
    
    /**
     * Resume paused audio playback (Priority 5: TTS Controls)
     */
    resumeAudio() {
        if (this.currentAudio && this.currentAudio.paused) {
            this.currentAudio.play();
            this.tg.MainButton.setText('🔊 Playing...');
            this.tg.HapticFeedback.impactOccurred('light');
            console.log('Audio resumed');
        }
    }
    
    /**
     * Stop current audio and cleanup (Priority 5: TTS Controls)
     */
    stopCurrentAudio() {
        if (this.currentAudio) {
            this.currentAudio.pause();
            this.currentAudio.currentTime = 0;
            this.currentAudio = null;
        }
        
        this.isPlayingAudio = false;
        this.stopProgressIndicator();
        this.tg.MainButton.hide();
        this.tg.MainButton.offClick();
    }
    
    /**
     * Start progress indicator for long audio (Priority 5: TTS Controls)
     */
    startProgressIndicator() {
        this.stopProgressIndicator(); // Clear any existing interval
        
        this.audioProgressInterval = setInterval(() => {
            if (!this.currentAudio || this.currentAudio.ended) {
                this.stopProgressIndicator();
            }
        }, 500);
    }
    
    /**
     * Stop progress indicator (Priority 5: TTS Controls)
     */
    stopProgressIndicator() {
        if (this.audioProgressInterval) {
            clearInterval(this.audioProgressInterval);
            this.audioProgressInterval = null;
        }
    }
    
    /**
     * Replay last response (Priority 5: TTS Controls)
     */
    replayLastResponse() {
        if (this.lastResponse && this.lastResponse.audio_url) {
            this.playAudioWithControls(this.lastResponse.audio_url, this.lastResponse.message);
            this.tg.HapticFeedback.impactOccurred('medium');
        } else {
            this.tg.showAlert('No previous response to replay');
        }
    }

    /**
     * Legacy play audio method (kept for backward compatibility)
     */
    async playAudio(audioUrl) {
        return this.playAudioWithControls(audioUrl);
    }

    /**
     * Set language for voice processing
     */
    setLanguage(lang) {
        this.language = lang;
        console.log(`Voice language set to: ${lang}`);
    }
    
    /**
     * Check if audio has sound (not silent)
     * Priority 2: Input Validation
     */
    async checkAudioHasSound(audioBlob) {
        try {
            const audioContext = new (window.AudioContext || window.webkitAudioContext)();
            const arrayBuffer = await audioBlob.arrayBuffer();
            const audioBuffer = await audioContext.decodeAudioData(arrayBuffer);
            
            // Get first channel data
            const channelData = audioBuffer.getChannelData(0);
            
            // Check for any significant amplitude
            let maxAmplitude = 0;
            for (let i = 0; i < channelData.length; i++) {
                maxAmplitude = Math.max(maxAmplitude, Math.abs(channelData[i]));
            }
            
            // Threshold: 0.01 (1% of max amplitude)
            const hasSound = maxAmplitude > 0.01;
            
            audioContext.close();
            
            return { 
                hasSound, 
                maxAmplitude,
                duration: audioBuffer.duration
            };
        } catch (error) {
            console.error('Error checking audio:', error);
            // If we can't check, assume it has sound
            return { hasSound: true };
        }
    }
    
    /**
     * Sanitize context before sending to backend
     * Priority 2: Input Validation
     */
    sanitizeContext(context) {
        const sanitized = { ...context };
        
        // Remove potentially sensitive fields
        delete sanitized.auth_token;
        delete sanitized.api_key;
        delete sanitized.password;
        
        // Limit visible_batches to prevent huge payloads
        if (sanitized.visible_batches && sanitized.visible_batches.length > 10) {
            sanitized.visible_batches = sanitized.visible_batches.slice(0, 10);
        }
        
        // Remove circular references
        return JSON.parse(JSON.stringify(sanitized));
    }
    
    /**
     * Cleanup recording state
     * Priority 2: Input Validation
     */
    cleanupRecording(voiceButton) {
        if (this.mediaRecorder) {
            if (this.mediaRecorder.state !== 'inactive') {
                this.mediaRecorder.stop();
            }
            this.mediaRecorder.stream.getTracks().forEach(track => track.stop());
        }
        this.isRecording = false;
        this.audioChunks = [];
        this.recordingStartTime = null;
        
        if (voiceButton) {
            voiceButton.classList.remove('recording');
        }
    }
    
    /**
     * Handle microphone errors with specific messages
     * Priority 4: Error Handling
     */
    handleMicrophoneError(error) {
        console.error('Microphone error:', error);
        
        let message = 'Microphone access denied.';
        
        if (error.name === 'NotAllowedError') {
            message = 'Microphone permission denied. Please enable microphone access in your browser settings.';
        } else if (error.name === 'NotFoundError') {
            message = 'No microphone found. Please connect a microphone and try again.';
        } else if (error.name === 'NotReadableError') {
            message = 'Microphone is in use by another app. Please close other apps using the microphone.';
        } else if (error.name === 'OverconstrainedError') {
            message = 'Could not satisfy audio constraints. Try restarting your browser.';
        }
        
        this.tg.showAlert(message);
    }
    
    /**
     * Stop currently playing audio
     * Priority 5: TTS Controls
     */
    stopCurrentAudio() {
        if (this.currentAudio && this.isPlayingAudio) {
            this.currentAudio.pause();
            this.currentAudio.currentTime = 0;
            this.currentAudio = null;
            this.isPlayingAudio = false;
        }
    }
}

// Export for use in mini apps
window.VoiceInterface = VoiceInterface;
