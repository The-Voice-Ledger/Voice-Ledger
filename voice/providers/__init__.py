"""
AddisAI Provider Package

Provides access to AddisAI API capabilities including STT, TTS, and conversational AI.
"""

from .addis_ai import (
    AddisAIProvider,
    AddisAIError,
    transcribe_sync,
    text_to_speech_sync,
    chat_sync,
    get_provider
)

__all__ = [
    "AddisAIProvider",
    "AddisAIError",
    "transcribe_sync",
    "text_to_speech_sync",
    "chat_sync",
    "get_provider"
]
