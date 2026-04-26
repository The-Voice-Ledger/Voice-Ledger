#!/usr/bin/env python3
import json
import subprocess

required = {
    'SERVICE_TYPE',
    'NIXPACKS_INSTALL_CMD',
    'NIXPACKS_START_CMD',
    'GEMINI_API_KEY',
    'OPENAI_API_KEY',
    'DEEPGRAM_API_KEY',
    'LLM_FALLBACK_ENABLED',
    'GEMINI_OPENAI_BASE_URL',
    'LIVEKIT_OPENAI_HEALTHCHECK',
    'LIVEKIT_OPENAI_HEALTHCHECK_MODEL',
    'LIVEKIT_OPENAI_MODEL',
    'LIVEKIT_GEMINI_MODEL',
    'LIVEKIT_LLM_TEMPERATURE',
    'LIVEKIT_OPENAI_TTS_MODEL',
    'LIVEKIT_OPENAI_TTS_VOICE',
    'LIVEKIT_DEEPGRAM_TTS_MODEL',
}

res = subprocess.run(
    ['railway', 'variables', '--service', 'Livekit-Voice-Agent', '--json'],
    capture_output=True,
    text=True,
)
if res.returncode != 0:
    print('ERROR:', res.stderr.strip())
    raise SystemExit(res.returncode)

obj = json.loads(res.stdout)
present = set(obj.keys())
missing = sorted(required - present)

print('service=', obj.get('RAILWAY_SERVICE_NAME'))
print('missing_count=', len(missing))
print('missing_keys=', ','.join(missing) if missing else '(none)')
print('service_type=', obj.get('SERVICE_TYPE'))
print('has_install_cmd=', 'NIXPACKS_INSTALL_CMD' in obj)
print('has_start_cmd=', 'NIXPACKS_START_CMD' in obj)
