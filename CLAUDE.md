# CLAUDE.md — AI Agent Instructions for Voice Ledger

## Project Overview

Voice Ledger is a voice-first blockchain traceability system for coffee supply chains.
Farmers speak in Amharic or English, an AI agent (GPT-4o with 37 tools) records events,
and data is anchored on-chain with IPFS storage.

## Architecture

- **Backend**: Python 3.9 + FastAPI + SQLAlchemy 2.0 + Celery + Redis
- **Database**: PostgreSQL (Neon serverless) — 23 tables
- **AI Agent**: GPT-4o tool-calling with 37 tools across 10 domains
- **Blockchain**: 7 Solidity contracts on Base Sepolia (Foundry)
- **Frontend**: React 19 SPA (`web-frontend/`) + Telegram Mini Apps (`miniapps/`)
- **Voice**: OpenAI Whisper (English) + local Amharic model + LiveKit real-time

## Key Files

- `voice/service/api.py` — Main FastAPI app (19 routers)
- `voice/agent/executor.py` — Agent loop (GPT-4o tool-calling)
- `voice/agent/registry.py` — 37 tool handlers (2400+ lines)
- `voice/agent/tools.py` — OpenAI function schemas
- `voice/telegram/telegram_api.py` — Telegram bot handlers (3641 lines)
- `database/models.py` — SQLAlchemy models (19 models, 886 lines)
- `database/connection.py` — Database engine and session factory
- `database/crud.py` — CRUD operations

## Commands

| Task | Command |
|------|---------|
| Run all tests | `pytest` |
| Run specific test | `pytest tests/test_agent.py` |
| Start API server | `uvicorn voice.service.api:app --port 8000` |
| Start Celery worker | `celery -A voice.tasks.celery_app worker --loglevel=info` |
| Run Solidity tests | `cd blockchain && forge test` |
| Type check (if configured) | `mypy voice/ --ignore-missing-imports` |

## Conventions

- **Error handling**: `VoiceCommandError` for domain errors, `HTTPException` for API errors
- **Logging**: `logger = logging.getLogger(__name__)`, never `print()` in production code
- **Database sessions**: Always use `get_db()` context manager
- **Async endpoints**: Wrap synchronous blocking calls in `await asyncio.to_thread()`
- **Tool handlers**: Return `(message: str, data: dict)` tuple from registry handlers
- **Imports**: Use absolute imports from project root; avoid `sys.path.insert` hacks

## Testing

- Fixtures in `tests/conftest.py`: `db_session`, `test_client`, `mock_redis`
- Use in-memory SQLite for database tests
- Mark integration tests with `@pytest.mark.integration`
- Mark slow tests with `@pytest.mark.slow`

## Deployment

- **Platform**: Railway (web + Celery worker + Redis)
- **Entry point**: `start.sh` routes by `SERVICE_TYPE` env var
- **Build**: Nixpacks (Python + Node.js 20 for web-frontend)
