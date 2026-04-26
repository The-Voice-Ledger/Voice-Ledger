#!/usr/bin/env python3
import os
import subprocess
import sys
from dotenv import load_dotenv


def main() -> int:
    load_dotenv('/Users/manu/Voice-Ledger/.env')

    sets = [
        'LLM_FALLBACK_ENABLED=true',
        'GEMINI_OPENAI_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai/',
        'LIVEKIT_OPENAI_HEALTHCHECK=true',
        'LIVEKIT_OPENAI_HEALTHCHECK_MODEL=gpt-4o-mini',
        'LIVEKIT_OPENAI_MODEL=gpt-4o-mini',
        'LIVEKIT_GEMINI_MODEL=gemini-2.5-flash',
        'LIVEKIT_LLM_TEMPERATURE=0.2',
        'LIVEKIT_OPENAI_TTS_MODEL=tts-1',
        'LIVEKIT_OPENAI_TTS_VOICE=nova',
        'LIVEKIT_DEEPGRAM_TTS_MODEL=aura-2-andromeda-en',
    ]

    gemini_key = os.getenv('GEMINI_API_KEY')
    if gemini_key:
        sets.append(f'GEMINI_API_KEY={gemini_key}')

    cmd = ['railway', 'variables']
    for item in sets:
        cmd.extend(['--set', item])

    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.stdout.strip():
        print(res.stdout.strip())
    if res.returncode != 0:
        if res.stderr.strip():
            print(res.stderr.strip())
        return res.returncode

    print('SUCCESS: LiveKit fallback variables updated on Railway')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
