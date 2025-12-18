"""
Voice Command Detector

Simple pattern matching to detect command keywords in voice transcripts.
Maps voice phrases to text commands (/start, /help, etc.)
"""

import logging
import re
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


def detect_voice_command(transcript: str, metadata: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Detect if transcript contains a voice command.
    
    Maps natural language phrases to bot commands:
    - "start" → /start
    - "help" → /help  
    - "register" → /register
    - "show my identity" → /myidentity
    - "show my batches" → /mybatches
    - "status" → /status
    - "export" → /export
    
    Args:
        transcript: The voice transcript from Whisper
        metadata: Request metadata (user_id, channel, etc.)
        
    Returns:
        Dict with command info if detected, None otherwise
    """
    if not transcript:
        return None
    
    # Normalize transcript for matching
    text = transcript.lower().strip()
    
    # Command patterns (order matters - check specific phrases first)
    command_patterns = [
        # Multi-word patterns first (most specific) - allow numbers in between
        (r'(show|display|get|view)\s+(my|me)\s+(my\s+)?(\d+\s+)?(identity|did)', 'myidentity'),
        (r'(show|display|get|list|view)\s+(my|me)\s+(my\s+)?(\d+\s+)?(batch(es)?)', 'mybatches'),
        (r'(show|display|get|list|view)\s+(my|me)\s+(my\s+)?(\d+\s+)?(coffee)', 'mybatches'),
        (r'(show|display|get|view)\s+(my|me)\s+(my\s+)?(\d+\s+)?(credential|credentials)', 'mycredentials'),
        (r'(what|where)\s+(is|are)\s+(my|me)\s*(\d+\s+)?(identity|did)', 'myidentity'),
        
        # Commands with context (I want to..., I need...)
        (r'(want|need|like)\s+(to\s+)?(register|signup|sign\s*up|join)', 'register'),
        (r'(need|want)\s+help', 'help'),
        (r'(check|show|view)\s+(the\s+)?(status|health)', 'status'),
        (r'help\s+me', 'help'),
        (r'what\s+can\s+you\s+do', 'help'),
        
        # Greetings with noise words
        (r'\b(hi|hello|hey|start)\s+(there|everyone)', 'start'),
        
        # Single word commands at start (with word boundary)
        (r'^(hi|hello|hey|start|begin|welcome)\b', 'start'),
        (r'^(help|assist|support|commands?)\b', 'help'),
        (r'^(register|signup|join|enroll)\b', 'register'),
        (r'^(status|health|check)\b', 'status'),
        (r'^(export|download)\b', 'export'),
        
        # Sign up variations
        (r'\bsign\s*up\b', 'register'),
        (r'\bsignup\b', 'register'),
        
        # Simple "my X" patterns (without verb)
        (r'\bmy\s+(batch(es)?|coffee)\b', 'mybatches'),
        (r'\bmy\s+(credential|credentials)\b', 'mycredentials'),
        (r'\bmy\s+(identity|did)\b', 'myidentity'),
        
        # Single words anywhere (fallback - use word boundaries)
        (r'\bregister\b', 'register'),
        (r'\bhelp\b', 'help'),
        (r'\bstatus\b', 'status'),
        (r'\bexport\b', 'export'),
    ]
    
    # Check each pattern
    for pattern, command in command_patterns:
        if re.search(pattern, text):
            logger.info(f"Voice command detected: '{text}' → /{command}")
            
            # Return command response structure
            return {
                "status": "voice_command",
                "command": command,
                "transcript": transcript,
                "metadata": metadata,
                "message": f"Voice command recognized: {command}"
            }
    
    # No command detected - continue to NLU for batch operations
    return None


def get_command_help_text() -> str:
    """
    Get help text showing voice command examples.
    
    Returns:
        Formatted help text
    """
    return """
🎙️ *Voice Commands*

You can say any of these:
• "start" or "hello" → Welcome message
• "help" → Show commands
• "register" → Start registration
• "show my identity" → Display your DID
• "show my batches" → List your batches
• "show my credentials" → View track record
• "export" → Get QR code
• "status" → Check system status

Or record a batch:
• "New batch of 50 kg Yirgacheffe from my farm"
• "Shipped batch ABC123 to warehouse"
    """.strip()
