"""
Unit tests for the Share Location button feature in farmer registration.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import asyncio
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from datetime import datetime

# ---------------------------------------------------------------------------
# Test 1: prompt_for_location_share returns reply_keyboard
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_prompt_for_location_share_returns_keyboard():
    """Verify that prompt_for_location_share sets the correct state and returns a keyboard."""
    from voice.telegram.register_handler import (
        prompt_for_location_share,
        STATE_SHARE_LOCATION
    )

    user_id = 12345
    session_data = {
        'state': 19, # STATE_VERIFY_GPS
        'data': {
            'preferred_language': 'en',
            'role': 'FARMER'
        }
    }

    with patch('voice.telegram.register_handler.conversation_states', {user_id: session_data}), \
         patch('voice.telegram.register_handler.set_session'):
        
        response = await prompt_for_location_share(user_id)
        
        assert session_data['state'] == STATE_SHARE_LOCATION
        assert 'reply_keyboard' in response
        assert response['reply_keyboard'][0][0]['request_location'] is True
        assert 'Share My Location' in response['reply_keyboard'][0][0]['text']

# ---------------------------------------------------------------------------
# Test 2: handle_location_shared stores coordinates and completes registration
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_handle_location_shared_stores_data():
    """Verify that handle_location_shared correctly stores coordinates."""
    from voice.telegram.register_handler import (
        handle_location_shared,
        STATE_SHARE_LOCATION
    )

    user_id = 12345
    session_data = {
        'state': STATE_SHARE_LOCATION,
        'data': {
            'preferred_language': 'en'
        }
    }

    with patch('voice.telegram.register_handler.conversation_states', {user_id: session_data}), \
         patch('voice.telegram.register_handler.complete_farmer_registration', new_callable=AsyncMock) as mock_complete:
        
        lat, lon = 9.02, 38.74 # Addis Ababa
        await handle_location_shared(user_id, lat, lon)
        
        assert 'shared_location' in session_data['data']
        assert session_data['data']['shared_location']['latitude'] == lat
        assert session_data['data']['shared_location']['longitude'] == lon
        mock_complete.assert_called_once_with(user_id, skip_location=False)

# ---------------------------------------------------------------------------
# Test 3: complete_farmer_registration saves shared coordinates
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_complete_farmer_registration_saves_coords():
    """Verify that complete_farmer_registration saves shared location to FarmerIdentity."""
    from voice.telegram.register_handler import complete_farmer_registration
    from database.models import UserIdentity, FarmerIdentity

    user_id = 12345
    session_data = {
        'state': 20, # STATE_SHARE_LOCATION
        'data': {
            'preferred_language': 'en',
            'shared_location': {
                'latitude': 9.5,
                'longitude': 39.5
            }
        }
    }

    mock_db = MagicMock()
    mock_user = UserIdentity(telegram_user_id=str(user_id), role='FARMER')
    mock_user.id = 101
    mock_farmer = FarmerIdentity(farmer_id="F-12345")
    
    # Mock database queries - robust model-based return
    def mock_query_robust(model):
        m = MagicMock()
        model_str = str(model)
        if 'UserIdentity' in model_str:
            m.filter_by.return_value.first.return_value = mock_user
        else:
            m.filter_by.return_value.first.return_value = mock_farmer
        return m
    mock_db.query.side_effect = mock_query_robust
    
    mock_cs = MagicMock()
    mock_cs.__contains__.return_value = True
    mock_cs.__getitem__.return_value = session_data

    with patch('voice.telegram.register_handler.conversation_states', mock_cs), \
         patch('voice.telegram.register_handler.SessionLocal', return_value=mock_db), \
         patch('ssi.user_identity.get_or_create_user_identity', return_value={'user_id': 1, 'did': 'did:123'}), \
         patch('voice.telegram.register_handler.set_session'):
        
        await complete_farmer_registration(user_id, skip_location=False)
        
        assert mock_farmer.latitude == 9.5
        assert mock_farmer.longitude == 39.5
        assert mock_user.is_approved is True
        mock_db.commit.assert_called()

if __name__ == "__main__":
    asyncio.run(test_prompt_for_location_share_returns_keyboard())
    print("PASS: test_prompt_for_location_share_returns_keyboard")
    asyncio.run(test_handle_location_shared_stores_data())
    print("PASS: test_handle_location_shared_stores_data")
    asyncio.run(test_complete_farmer_registration_saves_coords())
    print("PASS: test_complete_farmer_registration_saves_coords")
    print("SUCCESS: All unit tests passed!")
