"""
Amharic Conversational AI using Addis AI

Provides conversational interface for Amharic-speaking users to register coffee batches
and perform supply chain operations through natural dialogue in Amharic.
"""

import os
import logging
import json
import httpx
from typing import Dict, Any
from dotenv import load_dotenv

from .conversation_manager import ConversationManager

load_dotenv()
logger = logging.getLogger(__name__)

# Addis AI configuration
ADDIS_AI_API_KEY = os.getenv("ADDIS_AI_API_KEY")
ADDIS_AI_URL = "https://api.addisassistant.com/api/v1/chat_generate"
ADDIS_TRANSLATE_URL = "https://api.addisassistant.com/api/v1/translate"

# System prompt for Amharic coffee supply chain assistant
SYSTEM_PROMPT_AM = """አንተ ለኢትዮጵያ የቡና ገበሬዎች እና የአቅርቦት ሰንሰለት ተዋናዮች የምትረዳ ረዳት ነህ። የቡና ባች ምዝገባና የአቅርቦት ሰንሰለት ክስተቶችን በተፈጥሮ ውይይት እንዲመዘግቡ ታግዛለህ።

የአንተ ሚና:
1. በአማርኛ ተፈጥሯዊ፣ ወዳጃዊ ውይይቶችን መደረግ
2. ለአቅርቦት ሰንሰለት ስራዎች የሚያስፈልገውን መረጃ መሰብሰብ
3. መረጃ ጉድለት ወይም ግልጽ ያልሆነ ሲሆን ግልጽ ጥያቄዎችን መጠየቅ
4. ትዕዛዞችን ከመፈጸም በፊት የተሰበሰበውን መረጃ ማረጋገጥ
5. ለተጠቃሚዎች ማበረታቻ እና መመሪያ መስጠት

የአቅርቦት ሰንሰለት ስራዎች:

1. **record_commission** (አዲስ የቡና ባች መፍጠር):
   የሚያስፈልግ: ብዛት (ኪ.ግ), ምንጭ (እርሻ/ክልል), ምርት (ዓይነት)
   ምሳሌ: "50 ኪሎግራም የሲዳማ ቡና አጨድኩ"

2. **record_shipment** (ያለውን ባች መላክ):
   የሚያስፈልግ: batch_id ወይም GTIN, መድረሻ
   ምሳሌ: "ባች ABC123ን ወደ አዲስ መጋዘን ላክ"

3. **record_receipt** (ባች መቀበል):
   የሚያስፈልግ: batch_id ወይም GTIN, ሁኔታ (አማራጭ)
   ምሳሌ: "ባች ABC123ን በጥሩ ሁኔታ ተቀብያለሁ"

4. **record_transformation** (ቡና ማቀነባበር):
   የሚያስፈልግ: batch_id ወይም GTIN, transformation_type (ማብሰል/መፍጨት/ማድረቅ), output_quantity_kg
   ምሳሌ: "ባች ABC123ን አብስያለሁ፣ ውጤት 850ኪ.ግ"

5. **aggregate_batches** (በርካታ ባችዎችን ወደ ኮንቴይነር ማስገባት - EPCIS AggregationEvent):
   የሚያስፈልግ: batch_ids (የGTINs ወይም batch_ids ዝርዝር), parent_container_id (SSCC)
   ቁልፍ ቃላት: ማሸግ, ማጣመር, መጫን, ወደ ኮንቴይነር ማስገባት, ፓሌት መሙላት
   ምሳሌ: "ባች BATCH-001፣ BATCH-002 እና BATCH-003ን ወደ ኮንቴይነር C100 ጨምር"
   ምሳሌ: "ባችዎችን ወደ የመላኪያ ኮንቴይነር SSCC-306141411234567892 ጫን"
   ማስታወሻ: GTINs (እንደ 00614141165623 ያሉ 14-አሃዝ) ወይም batch_ids (እንደ BATCH-001) ይቀበላል

6. **disaggregate_batches** (ኮንቴይነርን ማፍታት - EPCIS AggregationEvent action=DELETE ጋር):
   የሚያስፈልግ: parent_container_id (SSCC ወይም container_id)
   ቁልፍ ቃላት: ማፍታት, ማውረድ, ከኮንቴይነር ማስወገድ, ፓሌት ማጥፋት
   ምሳሌ: "ኮንቴይነር C100ን ፍታ"
   ምሳሌ: "ባችዎችን ከፓሌት P001 አውጣ"

7. **split_batch** (ባችን ወደ ንዑስ-ባችዎች መከፋፈል - EPCIS TransformationEvent):
   የሚያስፈልግ: parent_batch_id (GTIN ወይም batch_id), child_quantities (የኪ.ግ መጠኖች ዝርዝር)
   ቁልፍ ቃላት: መክፈል, መከፋፈል, መለየት, መሰባበር
   ምሳሌ: "ባች ABCን ወደ 600ኪ.ግ እና 400ኪ.ግ ክፈል"
   ምሳሌ: "GTIN 00614141165623ን ወደ ሶስት ክፍሎች ከፋፍል: 2000ኪ.ግ, 1500ኪ.ግ, 500ኪ.ግ"

የውይይት መመሪያዎች:
- ሞቅ ያለ፣ አበረታች እና ትዕግስተኛ ሁን
- ቀላል እና ግልጽ ቋንቋ ተጠቀም
- በአንድ ጊዜ አንድ ጥያቄ ጠይቅ
- ከመቀጠል በፊት ግንዛቤን አረጋግጥ
- ተጠቃሚው ግራ የተጋባ ከሆነ ምሳሌዎችን አቅርብ
- ስኬታማ ማጠናቀቂያዎችን አስብ

ወሳኝ: ምላሽህ ትክክለኛ JSON ብቻ መሆን አለበት። ከ JSON በፊት ወይም በኋላ ተጨማሪ ጽሑፍ የለም።

ምላሽ ቅርጸት:

ተጨማሪ መረጃ ሲያስፈልግ፣ ይህንን JSON ብቻ መልስ:
{
  "amharic_response": "ተከታይ ጥያቄህ እዚህ",
  "ready_to_execute": false
}

ሁሉንም የሚያስፈልገውን መረጃ ሲኖርህ፣ ይህንን JSON ብቻ መልስ:
{
  "amharic_response": "የመጨረሻ የማረጋገጫ መልእክትህ ለተጠቃሚው",
  "ready_to_execute": true,
  "intent": "operation_name",
  "entities": {
    "quantity": 50,
    "unit": "kg",
    "origin": "Gedeo",
    "product": "Sidama"
  }
}

ከ JSON መዋቅር ውጭ ምንም ጽሑፍ አትጨምር። markdown code blocks አትጨምር። ንጹህ JSON ብቻ።
"""


async def process_amharic_conversation(user_id: int, transcript: str) -> Dict[str, Any]:
    """
    Process Amharic voice transcript using Addis AI conversational model.
    
    This function:
    1. Retrieves conversation history
    2. Sends transcript + history to Addis AI
    3. Parses Addis AI response
    4. Translates entities to English if needed
    5. Updates conversation state
    6. Returns result
    
    Args:
        user_id: Database user ID
        transcript: Transcribed Amharic text from user's voice message
        
    Returns:
        {
            "message": str,  # Amharic response to send to user
            "ready_to_execute": bool,  # Whether we can execute command
            "intent": str,  # Operation name (if ready)
            "entities": dict,  # Collected entities in English (if ready)
            "needs_clarification": bool  # Whether we need more info
        }
    """
    try:
        # Get conversation history
        history = ConversationManager.get_history(user_id)
        ConversationManager.set_language(user_id, 'am')
        
        # Add user's message to history
        ConversationManager.add_message(user_id, 'user', transcript)
        
        # Format conversation history for Addis AI
        conversation_history = [
            {"role": msg['role'], "content": msg['content']}
            for msg in history[:-1]  # Exclude the message we just added (it's in prompt)
        ]
        
        logger.info(f"Sending Amharic conversation to Addis AI for user {user_id}, turn {ConversationManager.get_turn_count(user_id)}")
        
        # Call Addis AI
        async with httpx.AsyncClient(timeout=30.0) as client_http:
            response = await client_http.post(
                ADDIS_AI_URL,
                headers={
                    "X-API-Key": ADDIS_AI_API_KEY,
                    "Content-Type": "application/json"
                },
                json={
                    "prompt": transcript,
                    "target_language": "am",
                    "conversation_history": conversation_history,
                    "generation_config": {
                        "temperature": 0.7,
                        "max_output_tokens": 500
                    }
                }
            )
            response.raise_for_status()
            addis_response = response.json()
        
        # Extract response text
        assistant_response = addis_response.get("response_text", "").strip()
        
        # Clean up response - remove markdown code blocks if present
        if assistant_response.startswith('```'):
            # Remove markdown code blocks
            lines = assistant_response.split('\n')
            # Remove first line (```json or ```) and last line (```)
            if len(lines) > 2:
                assistant_response = '\n'.join(lines[1:-1]).strip()
        
        # Try to parse as JSON (if Addis AI outputs structured data)
        try:
            result = json.loads(assistant_response)
            amharic_message = result.get('amharic_response', assistant_response)
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse Addis AI response as JSON: {e}")
            logger.warning(f"Response was: {assistant_response[:200]}")
            
            # Try to extract JSON from within the text
            try:
                # Look for JSON object in the text
                start_idx = assistant_response.find('{')
                end_idx = assistant_response.rfind('}')
                if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
                    json_str = assistant_response[start_idx:end_idx + 1]
                    result = json.loads(json_str)
                    amharic_message = result.get('amharic_response', assistant_response)
                    logger.info(f"Successfully extracted JSON from text")
                else:
                    raise ValueError("No JSON object found in response")
            except (json.JSONDecodeError, ValueError) as e2:
                logger.error(f"Could not extract JSON: {e2}")
                # If not JSON, treat as pure Amharic conversational response
                result = {
                    "amharic_response": assistant_response,
                    "ready_to_execute": False
                }
                amharic_message = assistant_response
        
        # Add assistant's response to history
        ConversationManager.add_message(user_id, 'assistant', amharic_message)
        
        # If ready to execute, extract or translate entities
        if result.get('ready_to_execute'):
            intent = result.get('intent')
            entities = result.get('entities', {})
            
            # If entities are in Amharic, translate them
            if not entities or any(contains_amharic(str(v)) for v in entities.values()):
                logger.info(f"Translating Amharic entities for user {user_id}")
                entities = await translate_entities(amharic_message)
            
            ConversationManager.set_intent(user_id, intent)
            ConversationManager.update_entities(user_id, entities)
            
            logger.info(f"Amharic conversation ready for user {user_id}: intent={intent}, entities={entities}")
            
            return {
                "message": amharic_message,
                "ready_to_execute": True,
                "intent": intent,
                "entities": entities
            }
        
        return {
            "message": amharic_message,
            "ready_to_execute": False
        }
        
    except Exception as e:
        logger.error(f"Error in Amharic conversation for user {user_id}: {e}", exc_info=True)
        return {
            "message": "ይቅርታ፣ መልእክትዎን በማቀናበር ላይ ስህተት ተፈጥሯል። እባክዎን እንደገና ይሞክሩ።",
            "ready_to_execute": False,
            "error": str(e)
        }


async def translate_entities(amharic_text: str) -> Dict[str, Any]:
    """
    Translate Amharic summary to English entities using Addis AI Translation API.
    
    Args:
        amharic_text: Amharic text containing entity information
        
    Returns:
        Dict of entities in English
    """
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(
                ADDIS_TRANSLATE_URL,
                headers={
                    "X-API-Key": ADDIS_AI_API_KEY,
                    "Content-Type": "application/json"
                },
                json={
                    "text": amharic_text,
                    "source_language": "am",
                    "target_language": "en"
                }
            )
            response.raise_for_status()
            translation = response.json()
        
        english_text = translation.get("translated_text", "")
        logger.debug(f"Translated: {amharic_text[:50]}... → {english_text[:50]}...")
        
        # Parse English text to extract entities (simple keyword extraction)
        entities = parse_english_entities(english_text)
        return entities
        
    except Exception as e:
        logger.error(f"Translation failed: {e}")
        return {}


def parse_english_entities(text: str) -> Dict[str, Any]:
    """
    Simple parser to extract entities from English text.
    
    Args:
        text: English text
        
    Returns:
        Dict of extracted entities
    """
    import re
    
    entities = {}
    text_lower = text.lower()
    
    # Extract quantity (numbers followed by kg/kilos/bags)
    quantity_match = re.search(r'(\d+)\s*(kg|kilos?|kilograms?|bags?)', text_lower)
    if quantity_match:
        entities['quantity'] = int(quantity_match.group(1))
        entities['unit'] = 'kg' if 'kg' in quantity_match.group(2) else quantity_match.group(2)
    
    # Extract origin (common Ethiopian regions)
    regions = ['gedeo', 'sidama', 'yirgacheffe', 'harar', 'kaffa', 'jimma', 'limu']
    for region in regions:
        if region in text_lower:
            entities['origin'] = region.capitalize()
            break
    
    # Extract product
    if 'coffee' in text_lower or 'bunna' in text_lower:
        entities['product'] = 'coffee'
    
    logger.debug(f"Parsed entities: {entities}")
    return entities


def contains_amharic(text: str) -> bool:
    """
    Check if text contains Amharic characters.
    
    Args:
        text: Text to check
        
    Returns:
        True if contains Amharic
    """
    # Amharic Unicode range: U+1200 to U+137F
    return any('\u1200' <= char <= '\u137F' for char in text)


def format_success_message_am(intent: str, entities: Dict[str, Any], batch_id: str = None) -> str:
    """
    Format success message in Amharic after command execution.
    
    Args:
        intent: Operation that was performed
        entities: Entities that were collected
        batch_id: Batch ID if created/modified
        
    Returns:
        Formatted Amharic success message
    """
    if intent == 'record_commission':
        return (
            f"✅ ተሳክቷል! አዲስ የቡና ባች ተመዝግቧል:\n\n"
            f"• ብዛት: {entities.get('quantity')} {entities.get('unit', 'ኪ.ግ')}\n"
            f"• ምንጭ: {entities.get('origin')}\n"
            f"• ዓይነት: {entities.get('product', 'ቡና')}\n"
            f"• ባች መታወቂያ: {batch_id}\n\n"
            f"አሁን ይህን ባች መላክ ወይም ሌሎች ስራዎችን ማከናወን ይችላሉ። "
            f"ሌላ የድምፅ መልእክት ብቻ ይላኩልኝ!"
        )
    elif intent == 'record_shipment':
        return (
            f"✅ ማጓጓዣ በተሳካ ሁኔታ ተመዝግቧል!\n\n"
            f"• ባች: {entities.get('batch_id')}\n"
            f"• መድረሻ: {entities.get('destination')}\n\n"
            f"ባቹ አሁን በጉዞ ላይ ነው።"
        )
    elif intent == 'aggregate_batches' or intent == 'pack_batches':
        batch_count = len(entities.get('batch_ids', []))
        container = entities.get('container_id', 'ኮንቴይነር')
        return (
            f"✅ ማሸግ በተሳካ ሁኔታ ተጠናቀቀ!\n\n"
            f"• {batch_count} ባችዎች ወደ {container} ተሸግተዋል\n"
            f"• ባችዎች: {', '.join(entities.get('batch_ids', []))}\n\n"
            f"ኮንቴይነሩ ለማጓጓዣ ዝግጁ ነው። EPCIS AggregationEvent በብሎክቼይን ተመዝግቧል።"
        )
    elif intent == 'disaggregate_batches' or intent == 'unpack_batches':
        container = entities.get('container_id', 'ኮንቴይነር')
        return (
            f"✅ ማፍታት በተሳካ ሁኔታ ተጠናቀቀ!\n\n"
            f"• ኮንቴይነር {container} ተፈታል\n\n"
            f"ባችዎች አሁን በተናጠል ይገኛሉ።"
        )
    elif intent == 'split_batch':
        splits = entities.get('child_quantities', [])
        parent = entities.get('parent_batch_id', 'ባች')
        return (
            f"✅ ባች መከፋፈል በተሳካ ሁኔታ ተጠናቀቀ!\n\n"
            f"• ዋና ባች: {parent}\n"
            f"• ወደ {len(splits)} ንዑስ-ባችዎች ተከፋፍሏል\n"
            f"• ብዛቶች: {', '.join(f'{q}ኪ.ግ' for q in splits)}\n\n"
            f"EPCIS TransformationEvent በብሎክቼይን ተመዝግቧል።"
        )
    elif intent == 'record_receipt':
        return (
            f"✅ ደረሰኝ ተረጋግጧል!\n\n"
            f"• ባች: {entities.get('batch_id')}\n"
            f"• ሁኔታ: {entities.get('condition', 'ጥሩ')}\n\n"
            f"ባቹ ተቀብሏል።"
        )
    else:
        return f"✅ ስራው በተሳካ ሁኔታ ተጠናቅቋል!\nባች መታወቂያ: {batch_id if batch_id else 'ምንም'}"
