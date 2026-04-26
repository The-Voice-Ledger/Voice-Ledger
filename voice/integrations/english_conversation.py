"""
English Conversational AI using OpenAI GPT-4

Provides conversational interface for English-speaking users to register coffee batches
and perform supply chain operations through natural dialogue.

Lab 18 Enhancement: RAG (Retrieval-Augmented Generation) integration for knowledge-grounded responses.
"""

import os
import logging
import json
from typing import Dict, Any, Optional
from openai import OpenAI
from dotenv import load_dotenv
from voice.providers.llm_fallback import chat_completion_with_fallback

from .conversation_manager import ConversationManager

# Lab 18: RAG integration (optional - graceful fallback if not available)
try:
    from voice.rag import enhance_query_with_rag, classify_query
    RAG_AVAILABLE = True
    logger = logging.getLogger(__name__)
    logger.info("RAG module loaded - conversational AI will use knowledge base")
except ImportError:
    RAG_AVAILABLE = False
    logger = logging.getLogger(__name__)
    logger.info("RAG module not available - conversational AI will use static prompts only")

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

CRITICAL COMMUNICATION GUIDELINES:
- Speak conversationally and naturally, as if talking to a farmer or supply chain worker
- Your knowledge base (vector database) IS your brain - present information as if you know it directly
- NEVER cite sources, mention documentation, file paths, lab numbers, or reference materials
- NEVER say: "according to...", "as per Lab X", "the documentation shows", "based on the files", "in the system", etc.
- Simply state facts confidently: "Here's how it works:", "The process is:", "You can do this by:"
- Focus on WHAT happens and HOW to use it
- Use everyday language, not technical jargon unless absolutely necessary

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

5. **aggregate_batches** (Pack multiple batches into container - EPCIS AggregationEvent):
   Required: batch_ids (list of GTINs or batch_ids), parent_container_id (SSCC)
   Keywords: pack, combine, load, aggregate, put into container, fill pallet
   Example: "Pack batches BATCH-001, BATCH-002, and BATCH-003 into container C100"
   Example: "Load batches into shipping container SSCC-306141411234567892"
   Note: Accepts GTINs (14-digit like 00614141165623) or batch_ids (like BATCH-001)

6. **disaggregate_batches** (Unpack container - EPCIS AggregationEvent with action=DELETE):
   Required: parent_container_id (SSCC or container_id)
   Keywords: unpack, unload, remove from container, empty pallet
   Example: "Unpack container C100"
   Example: "Remove batches from pallet P001"

7. **split_batch** (Divide batch into sub-batches - EPCIS TransformationEvent):
   Required: parent_batch_id (GTIN or batch_id), child_quantities (list of kg amounts)
   Keywords: split, divide, separate, break up
   Example: "Split batch ABC into 600kg and 400kg"
   Example: "Divide GTIN 00614141165623 into three lots: 2000kg, 1500kg, 500kg"

CONVERSATION GUIDELINES:
- Be warm, encouraging, and patient
- Use simple, clear language
- Ask ONE question at a time
- Confirm understanding before proceeding
- If user seems confused, offer examples
- Celebrate successful completions

AUTHENTICATION AWARENESS:
- If user_id is 0, they are ANONYMOUS (not logged in)
- For transactional operations (record_commission, record_shipment, etc.), anonymous users MUST be guided to register
- For informational queries (prices, how-to, etc.), anonymous users get full answers

CRITICAL: You MUST ONLY respond with valid JSON. No extra text before or after the JSON.

RESPONSE FORMAT:

When you need more information, respond with ONLY this JSON:
{
  "message_text": "Your follow-up question (can include emojis, formatting)",
  "message_spoken": "Natural spoken version of the same question",
  "ready_to_execute": false
}

When ANONYMOUS user tries transactional operation:
{
  "message_text": "I'd love to help you record that! 📦\n\nHowever, batch recording requires registration.\n\nYou can:\n1. Click Login above\n2. Register via Telegram: https://t.me/VoiceLedgerBot",
  "message_spoken": "I'd love to help you record that batch! However, batch recording requires a registered account. You can click the login button shown on screen, or register via our Telegram bot - there's a registration link displayed below. In the meantime, I can answer questions about prices or EUDR compliance.",
  "ready_to_execute": false,
  "needs_auth": true,
  "telegram_bot_url": "https://t.me/VoiceLedgerBot"
}

When you have ALL required information, respond with ONLY this JSON:
{
  "message_text": "Your final confirmation message to the user",
  "message_spoken": "Natural spoken version of the same message",
  "ready_to_execute": true,
  "intent": "operation_name",
  "entities": {
    "quantity": 50,
    "unit": "kg",
    "origin": "Gedeo",
    "product": "Sidama"
  }
}

IMPORTANT: message_spoken should NEVER include URLs or emojis. Use phrases like 'shown on screen', 'displayed below', 'the link above' instead of reading URLs.

DO NOT include any text outside the JSON structure. DO NOT include markdown code blocks. Just pure JSON.
"""


def process_english_conversation(
    user_id: int, 
    transcript: str, 
    use_rag: bool = True,
    context: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Process English voice transcript using GPT-4 conversational AI.
    
    VOICE-FIRST ARCHITECTURE:
    - Context-aware: Uses app context to resolve references and determine intent
    - Action-oriented: Returns executable actions when user confirms
    - Workflow-enabled: Manages multi-turn conversations
    
    This function:
    1. Retrieves conversation history
    2. (Lab 18) Enhances prompt with RAG-retrieved context if applicable
    3. Adds app context to system prompt (which app, visible data, etc.)
    4. Sends transcript + history to GPT-4
    5. Parses GPT-4 response
    6. Updates conversation state
    7. Returns result (ready to execute or needs more info)
    
    Args:
        user_id: Database user ID
        transcript: Transcribed text from user's voice message
        use_rag: Whether to use RAG enhancement (default: True)
        context: App context dict with structure:
            {
                'app': 'batch_browser',
                'visible_batches': [{id, origin, quantity, ...}],
                'user_role': 'farmer',
                'can_create': True,
                'view': 'list'
            }
        
    Returns:
        {
            "message": str,  # Response to send to user
            "ready_to_execute": bool,  # Whether we can execute command
            "intent": str,  # Operation name (if ready)
            "entities": dict,  # Collected entities (if ready)
            "needs_clarification": bool,  # Whether we need more info
            "action": dict,  # Executable action (if ready)
            "workflow_state": str,  # Current workflow state
            "workflow_type": str,  # Type of workflow
            "session_id": str  # Workflow session ID
        }
    """
    try:
        # LAB 20: Check for workflow triggers FIRST (batch recording, shipment tracking)
        from voice.workflows.state_machine import StateManager, ConversationState
        from voice.workflows.batch_recording import BatchRecordingWorkflow
        from voice.workflows.shipment_tracking import ShipmentTrackingWorkflow
        
        # Check if user is in active workflow
        state_data = StateManager.get_user_state(user_id)
        if state_data:
            workflow_name = state_data.get('workflow')
            current_state_str = state_data.get('state')
            
            try:
                current_state = ConversationState(current_state_str)
            except ValueError:
                logger.warning(f"Unknown state {current_state_str}, clearing")
                StateManager.clear_user_state(user_id)
                state_data = None
            
            if state_data and workflow_name:
                # Route to appropriate workflow
                logger.info(f"User {user_id} in active workflow: {workflow_name}, state: {current_state_str}")
                
                if workflow_name == 'batch_recording':
                    workflow = BatchRecordingWorkflow()
                    import asyncio
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    try:
                        result = loop.run_until_complete(
                            workflow.handle_message(user_id, transcript, current_state)
                        )
                    finally:
                        loop.close()
                    
                    return {
                        'message': result.get('message', ''),
                        'ready_to_execute': False,  # Workflows handle their own execution
                        'intent': None,
                        'entities': {},
                        'needs_clarification': result.get('keep_state', True)
                    }
                
                elif workflow_name == 'shipment_tracking':
                    workflow = ShipmentTrackingWorkflow()
                    import asyncio
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    try:
                        result = loop.run_until_complete(
                            workflow.handle_message(user_id, transcript, current_state)
                        )
                    finally:
                        loop.close()
                    
                    return {
                        'message': result.get('message', ''),
                        'ready_to_execute': False,
                        'intent': None,
                        'entities': {},
                        'needs_clarification': result.get('keep_state', True)
                    }
        
        # Check for workflow trigger keywords
        text_lower = transcript.lower()
        
        # Batch recording triggers (English)
        batch_triggers = ['record batch', 'new batch', 'record harvest', 'create batch', 'log batch', 'record coffee']
        if any(trigger in text_lower for trigger in batch_triggers):
            logger.info(f"Batch recording workflow triggered for user {user_id}")
            workflow = BatchRecordingWorkflow()
            import asyncio
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                result = loop.run_until_complete(workflow.start(user_id))
            finally:
                loop.close()
            
            return {
                'message': result.get('message', ''),
                'ready_to_execute': False,
                'intent': None,
                'entities': {},
                'needs_clarification': True
            }
        
        # Shipment tracking triggers (English)
        shipment_triggers = ['track shipment', 'my shipments', 'where is my coffee', 'check shipment', 'track my']
        if any(trigger in text_lower for trigger in shipment_triggers):
            logger.info(f"Shipment tracking workflow triggered for user {user_id}")
            workflow = ShipmentTrackingWorkflow()
            import asyncio
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                result = loop.run_until_complete(workflow.start(user_id))
            finally:
                loop.close()
            
            return {
                'message': result.get('message', ''),
                'ready_to_execute': False,
                'intent': None,
                'entities': {},
                'needs_clarification': True
            }
        
        # Get conversation history
        history = ConversationManager.get_history(user_id)
        ConversationManager.set_language(user_id, 'en')
        
        # Add user's message to history
        ConversationManager.add_message(user_id, 'user', transcript)
        
        # Lab 18: Enhance system prompt with RAG if available and enabled
        system_prompt = SYSTEM_PROMPT
        
        # VOICE-FIRST: Add app context to system prompt
        if context:
            context_prompt = f"""

CURRENT CONTEXT (Mini App):
App: {context.get('app', 'unknown')}
User Role: {context.get('user_role', 'unknown')}
View: {context.get('view', 'unknown')}

"""
            # Add visible data context
            if context.get('visible_batches'):
                batches_summary = []
                for b in context.get('visible_batches', [])[:5]:  # First 5 for context
                    batches_summary.append(
                        f"- {b.get('batch_id', b.get('id'))}: {b.get('origin', 'unknown')} "
                        f"{b.get('quantity_kg', 0)}kg, {b.get('status', 'unknown')}"
                    )
                context_prompt += "Visible Batches:\n" + "\n".join(batches_summary) + "\n\n"
            
            if context.get('visible_rfqs'):
                rfqs_summary = []
                for r in context.get('visible_rfqs', [])[:5]:
                    rfqs_summary.append(
                        f"- RFQ#{r.get('id')}: {r.get('quantity_kg')}kg {r.get('origin')} "
                        f"at ${r.get('price_per_kg', 0)}/kg"
                    )
                context_prompt += "Visible RFQs:\n" + "\n".join(rfqs_summary) + "\n\n"
            
            if context.get('visible_offers'):
                offers_summary = []
                for o in context.get('visible_offers', [])[:5]:
                    offers_summary.append(
                        f"- Offer#{o.get('id')}: {o.get('quantity_kg')}kg {o.get('origin')} "
                        f"at ${o.get('price_per_kg', 0)}/kg"
                    )
                context_prompt += "Visible Offers:\n" + "\n".join(offers_summary) + "\n\n"
            
            if context.get('current_batch'):
                batch = context['current_batch']
                context_prompt += f"""Current Batch Being Viewed:
- ID: {batch.get('batch_id', batch.get('id'))}
- Origin: {batch.get('origin_region', 'unknown')}
- Quantity: {batch.get('quantity_kg', 0)}kg
- Grade: {batch.get('grade', 'unknown')}
- Status: {batch.get('status', 'unknown')}

"""
            
            if context.get('user_data'):
                user = context['user_data']
                context_prompt += f"""User Profile:
- Name: {user.get('name', 'unknown')}
- Role: {user.get('role', 'unknown')}
- Language: {user.get('language', 'en')}
- Batch Count: {user.get('stats', {}).get('batch_count', 0)}

"""
            
            context_prompt += """Use this context to:
1. Resolve references like "this batch", "the top one", "my latest"
2. Determine if user wants to CREATE something or VIEW/FILTER existing data
3. Extract specific IDs/values from visible data when user references them
4. Return executable actions when user confirms operations

When user says "this" or "that", refer to the current/visible data above.
When user wants to create (batch, RFQ, offer), start appropriate workflow.
"""
            
            system_prompt = SYSTEM_PROMPT + context_prompt
        
        if use_rag and RAG_AVAILABLE:
            try:
                system_prompt = enhance_query_with_rag(
                    query=transcript,
                    base_prompt=system_prompt,
                    max_context_tokens=2000
                )
                logger.info(f"Enhanced prompt with RAG for user {user_id}")
            except Exception as rag_error:
                logger.warning(f"RAG enhancement failed, using base prompt: {rag_error}")
        
        # Build messages for GPT-4
        messages = [{"role": "system", "content": system_prompt}]
        messages.extend(history)
        
        logger.info(f"Sending English conversation to GPT-4 for user {user_id}, turn {ConversationManager.get_turn_count(user_id)}")
        
        # Call GPT-4
        response, provider_used = chat_completion_with_fallback(
            primary_client=client,
            model=os.getenv("ENGLISH_CONVERSATION_MODEL", "gpt-4"),
            messages=messages,
            temperature=0.7,
            max_tokens=500,
        )
        logger.info(f"English conversation provider: {provider_used}")
        
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
        
        # Handle backward compatibility - normalise all three keys so every
        # caller can use whichever key it prefers.
        if 'message' in result and 'message_text' not in result:
            # Old-format response: only 'message' present
            result['message_text'] = result['message']
            result['message_spoken'] = result['message']
        elif 'message_text' in result and 'message' not in result:
            # New-format response: 'message_text'/'message_spoken' but no 'message'
            result['message'] = result['message_text']
        if 'message_spoken' not in result:
            result['message_spoken'] = result.get('message_text') or result.get('message', '')
        
        # Add assistant's response to history (use text version)
        message_to_save = result.get('message_text') or result.get('message', assistant_response)
        ConversationManager.add_message(user_id, 'assistant', message_to_save)
        
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
    elif intent == 'aggregate_batches' or intent == 'pack_batches':
        batch_count = len(entities.get('batch_ids', []))
        container = entities.get('container_id', 'container')
        return (
            f"✅ Aggregation successful!\n\n"
            f"• Packed {batch_count} batches into {container}\n"
            f"• Batches: {', '.join(entities.get('batch_ids', []))}\n\n"
            f"Container is ready for shipment. EPCIS AggregationEvent recorded on blockchain."
        )
    elif intent == 'disaggregate_batches' or intent == 'unpack_batches':
        container = entities.get('container_id', 'container')
        return (
            f"✅ Disaggregation successful!\n\n"
            f"• Unpacked container {container}\n\n"
            f"Batches are now available individually."
        )
    elif intent == 'split_batch':
        splits = entities.get('child_quantities', [])
        parent = entities.get('parent_batch_id', 'batch')
        return (
            f"✅ Batch split successful!\n\n"
            f"• Original batch: {parent}\n"
            f"• Split into {len(splits)} sub-batches\n"
            f"• Quantities: {', '.join(f'{q}kg' for q in splits)}\n\n"
            f"EPCIS TransformationEvent recorded on blockchain."
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
