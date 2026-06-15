# Contributing to Voice Ledger

Thank you for your interest in contributing to Voice Ledger!

## Development Setup

1. Clone the repository:
   ```bash
   git clone https://github.com/The-Voice-Ledger/Voice-Ledger.git
   cd Voice-Ledger
   ```

2. Create a virtual environment:
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Copy environment variables:
   ```bash
   cp .env.example .env
   # Edit .env with your API keys
   ```

5. Run tests:
   ```bash
   pytest
   ```

## Code Style

- Python: Follow PEP 8, use type hints where practical
- Error handling: Use `VoiceCommandError` for domain errors, generic `Exception` for unexpected failures
- Logging: Use `logging.getLogger(__name__)`, not `print()`
- Database: Use the `get_db()` context manager, never raw `SessionLocal()`
- Tests: Write tests for new features, use `pytest` fixtures from `tests/conftest.py`

## Pull Request Process

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/your-feature`
3. Make your changes
4. Add tests for new functionality
5. Run `pytest` to ensure all tests pass
6. Submit a pull request with a clear description of changes

## Reporting Issues

Use GitHub Issues with the provided templates for bug reports and feature requests.
