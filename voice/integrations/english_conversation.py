"""
English Conversational AI using OpenAI GPT-4

Provides conversational interface for English-speaking users to register coffee batches
and perform supply chain operations through natural dialogue.
"""

import os
import logging
import json
from typing import Dict, Any
from openai import OpenAI
from dotenv import load_dotenv

from .conversation_manager import ConversationManager

load_dotenv()
logger = logging.getLogger(__name__)

# Initialize OpenAI client
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# System prompt for coffee supply chain assistant
SYSTEM_PROMPT = """You are a helpful assistant for Ethiopian coffee farmers and supply chain actors. You help them record coffee batches and supply chain events through natural conversation.

Your role is to:
1. Have natural, friendly conversations in English
2. Collect required information for supply chain operations
3. Ask clarifying questions when information is missing or unclear
4. Confirm collected information before executing commands
5. Provide encouragement and guidance to users

SUPPLY CHAIN OPERATIONS:

1. **record_commission** (Create new coffee batch):
   Required: quantity (kg), origin (farm/region), product (variety)
   Example: "I harvested 50 kg of Sidama coffee"

2. **record_shipment** (Ship existing batch):
   Required: batch_id or GTIN, destination
   Example: "Ship batch ABC123 to Addis warehouse"

3. **record_receipt** (Receive batch):
   Required: batch_id or GTIN, condition (optional)
   Example: "Received batch ABC123 in good condition"

4. **record_transformation** (Process coffee):
   Required: batch_id or GTIN, transformation_type (roasting/milling/drying), output_quantity_kg
   Example: "Roasted batch ABC123, output 850kg"

5. **pack_batches** (Aggregate multiple batches):
   Required: batch_ids (list), container_id
   Example: "Pack batches A B C into pallet P001"

6. **unpack_batches** (Disaggregate container):
   Required: container_id
   Example: "Unpack container P001"

7. **split_batch** (Divide batch):
   Required: parent_batch_id, splits (list of quantities)
   Example: "Split batch ABC into 600kg and 400kg"

CONVERSATION GUIDELINES:
- Be warm, encouraging, and patient
- Use simple, clear language
- Ask ONE question at a time
- Confirm understanding before proceeding
- If user seems confused, offer examples
- Celebrate successful completions

CRITICAL: You MUST ONLY respond with valid JSON. No extra text before or after the JSON.

RESPONSE FORMAT:

When you need more information, respond with ONLY this JSON:
{
  "message": "Your follow-up question here",
  "ready_to_execute": false
}

When you have ALL required information, respond with ONLY this JSON:
{
  "message": "Your final confirmation message to the user",
  "ready_to_execute": true,
  "intent": "operation_name",
  "entities": {
    "quantity": 50,
    "unit": "kg",
    "origin": "Gedeo",
    "product": "Sidama"
  }
}

DO NOT include any text outside the JSON structure. DO NOT include markdown code blocks. Just pure JSON.
"""


def process_english_conversation(user_id: int, transcript: str) -> Dict[str, Any]:
    """
    Process English voice transcript using GPT-4 conversational AI.
    
    This function:
    1. Retrieves conversation history
    2. Sends transcript + history to GPT-4
    3. Parses GPT-4 response
    4. Updates conversation state
    5. Returns result (ready to execute or needs more info)
    
    Args:
        user_id: Database user ID
        transcript: Transcribed text from user's voice message
        
    Returns:
        {
            "message": str,  # Response to send to user
            "ready_to_execute": bool,  # Whether we can execute command
            "intent": str,  # Operation name (if ready)
            "entities": dict,  # Collected entities (if ready)
            "needs_clarification": bool  # Whether we need more info
        }
    """
    try:
        # Get conversation history
        history = ConversationManager.get_history(user_id)
        ConversationManager.set_language(user_id, 'en')
        
        # Add user's message to history
        ConversationManager.add_message(user_id, 'user', transcript)
        
        # Build messages for GPT-4
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        messages.extend(history)
        
        logger.info(f"Sending English conversation to GPT-4 for user {user_id}, turn {ConversationManager.get_turn_count(user_id)}")
        
        # Call GPT-4
        response = client.chat.completions.create(
            model="gpt-4",
            messages=messages,
            temperature=0.7,
            max_tokens=500
        )
        
        assistant_response = response.choices[0].message.content.strip()
        
        # Clean up response - remove markdown code blocks if present
        if assistant_response.startswith('```'):
            # Remove markdown code blocks
            lines = assistant_response.split('\n')
            # Remove first line (```json or ```) and last line (```)
            if len(lines) > 2:
                assistant_response = '\n'.join(lines[1:-1]).strip()
        
        # Try to parse as JSON
        try:
            result = json.loads(assistant_response)
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse GPT-4 response as JSON: {e}")
            logger.warning(f"Response was: {assistant_response[:200]}")
            
            # Try to extract JSON from within the text
            try:
                # Look for JSON object in the text
                start_idx = assistant_response.find('{')
                end_idx = assistant_response.rfind('}')
                if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
                    json_str = assistant_response[start_idx:end_idx + 1]
                    result = json.loads(json_str)
                    logger.info(f"Successfully extracted JSON from text")
                else:
                    raise ValueError("No JSON object found in response")
            except (json.JSONDecodeError, ValueError) as e2:
                logger.error(f"Could not extract JSON: {e2}")
                # If not JSON, treat as conversational response
                result = {
                    "message": assistant_response,
                    "ready_to_execute": False
                }
        
        # Add assistant's response to history
        ConversationManager.add_message(user_id, 'assistant', result.get('message', assistant_response))
        
        # If ready to execute, update entities and intent
        if result.get('ready_to_execute'):
            intent = result.get('intent')
            entities = result.get('entities', {})
            
            ConversationManager.set_intent(user_id, intent)
            ConversationManager.update_entities(user_id, entities)
            
            logger.info(f"English conversation ready for user {user_id}: intent={intent}, entities={entities}")
        
        return result
        
    except Exception as e:
        logger.error(f"Error in English conversation for user {user_id}: {e}", exc_info=True)
        return {
            "message": "Sorry, I encountered an error processing your message. Please try again.",
            "ready_to_execute": False,
            "error": str(e)
        }


def format_success_message(intent: str, entities: Dict[str, Any], batch_id: str = None) -> str:
    """
    Format success message after command execution.
    
    Args:
        intent: Operation that was performed
        entities: Entities that were collected
        batch_id: Batch ID if created/modified
        
    Returns:
        Formatted success message
    """
    if intent == 'record_commission':
        return (
            f"✅ Success! Registered new coffee batch:\n\n"
            f"• Quantity: {entities.get('quantity')} {entities.get('unit', 'kg')}\n"
            f"• Origin: {entities.get('origin')}\n"
            f"• Variety: {entities.get('product', 'coffee')}\n"
            f"• Batch ID: {batch_id}\n\n"
            f"You can now ship this batch or perform other operations. "
            f"Just send me another voice message!"
        )
    elif intent == 'record_shipment':
        return (
            f"✅ Shipment recorded successfully!\n\n"
            f"• Batch: {entities.get('batch_id')}\n"
            f"• Destination: {entities.get('destination')}\n\n"
            f"The batch is now in transit."
        )
    elif intent == 'record_receipt':
        return (
            f"✅ Receipt confirmed!\n\n"
            f"• Batch: {entities.get('batch_id')}\n"
            f"• Condition: {entities.get('condition', 'Good')}\n\n"
            f"Batch has been received."
        )
    else:
        return f"✅ Operation completed successfully!\nBatch ID: {batch_id if batch_id else 'N/A'}"
