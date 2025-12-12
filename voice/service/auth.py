"""
API Key Authentication Module

This module implements API key-based authentication for the Voice Ledger API.
All requests to protected endpoints must include a valid API key in the X-API-Key header.
"""

import os
from fastapi import HTTPException, Security
from fastapi.security.api_key import APIKeyHeader

API_KEY_NAME = "X-API-Key"
_api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=False)


def get_expected_api_key() -> str:
    """
    Retrieve the expected API key from environment variables.
    
    Returns:
        The API key from VOICE_LEDGER_API_KEY environment variable
    """
    return os.getenv("VOICE_LEDGER_API_KEY", "")


async def verify_api_key(
    api_key: str = Security(_api_key_header),
):
    """
    Verify that the provided API key matches the expected key.
    
    Args:
        api_key: API key from request header
        
    Returns:
        True if valid
        
    Raises:
        HTTPException: If API key is missing, invalid, or not configured
    """
    expected = get_expected_api_key()
    if not expected:
        # API key not configured, reject requests
        raise HTTPException(status_code=500, detail="API key not configured")
    if api_key != expected:
        raise HTTPException(status_code=401, detail="Invalid API key")
    return True
