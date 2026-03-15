"""
Shared service layer for Voice Ledger.

Business logic lives here — both the Telegram/Mini App path (via registry.py)
and the LiveKit web agent (via livekit_agent.py) call these same functions.

Each service module returns structured dicts. Formatting for speech, text,
or action cards happens in the caller's wrapper.
"""
