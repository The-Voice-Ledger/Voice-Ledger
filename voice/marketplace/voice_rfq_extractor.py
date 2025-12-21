"""
Voice RFQ Extraction Module
Lab 15 Extension - Extract RFQ details from voice messages

Uses OpenAI GPT to extract structured RFQ data from natural voice input.
Supports multilingual input (English, Amharic).
"""

import os
import json
import logging
from typing import Dict, Any, Optional
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

# Initialize OpenAI client
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


def extract_rfq_from_voice(transcript: str, language: str = "en") -> Dict[str, Any]:
    """
    Extract RFQ details from voice transcript using GPT-4.
    
    Args:
        transcript: Voice message transcript (English or Amharic)
        language: Detected language code ("en", "am")
        
    Returns:
        {
            "confidence": float,  # 0.0-1.0, how confident we are
            "extracted_fields": {
                "quantity_kg": float or None,
                "variety": str or None,  # Arabica, Sidama, Yirgacheffe, etc.
                "grade": str or None,  # Grade 1, Grade 2, etc.
                "processing_method": str or None,  # Washed, Natural, Honey
                "delivery_location": str or None,  # Addis Ababa, Djibouti, etc.
                "deadline_days": int or None  # Days from now
            },
            "missing_fields": List[str],  # Fields that couldn't be extracted
            "suggested_question": str or None,  # Question to ask user for missing info
            "raw_interpretation": str  # Human-readable interpretation
        }
    """
    
    system_prompt = """You are an AI assistant for a coffee marketplace. Extract Request for Quote (RFQ) details from buyer voice messages.

**Your Task:**
Analyze the buyer's message and extract these fields:
1. quantity_kg (float): How many kilograms of coffee they want (accept kg, tons, bags)
2. variety (string): Coffee variety (Arabica, Sidama, Yirgacheffe, Guji, Limu, Harrar, etc.)
3. grade (string): Quality grade (Grade 1, Grade 2, etc.)
4. processing_method (string): Processing type (Washed, Natural, Honey, Pulped Natural)
5. delivery_location (string): Where they want delivery (city/port name)
6. deadline_days (int): Deadline in days from now (if they say "2 weeks" = 14 days)

**Rules:**
- Only extract explicitly mentioned information
- Set missing fields to null
- Convert units: 1 ton = 1000 kg, 1 bag = 60 kg
- Infer reasonable defaults only for variety (default: Arabica) and processing (default: Washed)
- delivery_location: Accept any Ethiopian city or nearby ports (Djibouti, Berbera, Mombasa)
- Be strict about grade - only extract if explicitly mentioned
- Calculate deadline_days from relative time phrases ("in 2 weeks" = 14, "by end of month" = estimate)

**Confidence Scoring:**
- 1.0: All 6 fields extracted clearly
- 0.8: 4-5 fields extracted
- 0.6: 2-3 fields extracted  
- 0.4: Only 1 field extracted
- 0.2: Vague request, minimal info

**Response Format (JSON only):**
```json
{
  "confidence": 0.0-1.0,
  "extracted_fields": {
    "quantity_kg": float or null,
    "variety": "string" or null,
    "grade": "string" or null,
    "processing_method": "string" or null,
    "delivery_location": "string" or null,
    "deadline_days": int or null
  },
  "missing_fields": ["field1", "field2"],
  "suggested_question": "What grade are you looking for?",
  "raw_interpretation": "Buyer wants 5000kg of Yirgacheffe Grade 1 washed coffee delivered to Addis Ababa in 3 weeks"
}
```

**Examples:**

Input: "I want to buy 5000 kilograms of Yirgacheffe Grade 1 washed coffee, delivered to Addis Ababa in 3 weeks"
Output: {"confidence": 1.0, "extracted_fields": {"quantity_kg": 5000.0, "variety": "Yirgacheffe", "grade": "Grade 1", "processing_method": "Washed", "delivery_location": "Addis Ababa", "deadline_days": 21}, "missing_fields": [], "suggested_question": null, "raw_interpretation": "Buyer wants 5000kg of Yirgacheffe Grade 1 washed coffee delivered to Addis Ababa in 3 weeks"}

Input: "Need 2 tons of Sidama coffee by end of January"
Output: {"confidence": 0.6, "extracted_fields": {"quantity_kg": 2000.0, "variety": "Sidama", "grade": null, "processing_method": "Washed", "delivery_location": null, "deadline_days": 30}, "missing_fields": ["grade", "delivery_location"], "suggested_question": "What grade are you looking for? And where should it be delivered?", "raw_interpretation": "Buyer wants 2000kg of Sidama coffee (processing not specified, defaulting to washed) by end of January"}

Input: "Looking for high quality coffee"
Output: {"confidence": 0.2, "extracted_fields": {"quantity_kg": null, "variety": "Arabica", "grade": null, "processing_method": null, "delivery_location": null, "deadline_days": null}, "missing_fields": ["quantity_kg", "grade", "processing_method", "delivery_location", "deadline_days"], "suggested_question": "How many kilograms do you need?", "raw_interpretation": "Very vague request - only knows they want quality coffee"}

Now analyze the user's message."""

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",  # Cheaper and faster than gpt-4
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Language: {language}\nMessage: {transcript}"}
            ],
            temperature=0.3,  # Lower temperature for more consistent extraction
            response_format={"type": "json_object"}  # Force JSON response
        )
        
        result_text = response.choices[0].message.content
        result = json.loads(result_text)
        
        logger.info(f"Voice RFQ extraction: confidence={result.get('confidence')}, fields={len([f for f in result.get('extracted_fields', {}).values() if f is not None])}/6")
        
        return result
        
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse GPT response as JSON: {e}")
        logger.error(f"Response text: {result_text}")
        return {
            "confidence": 0.0,
            "extracted_fields": {
                "quantity_kg": None,
                "variety": None,
                "grade": None,
                "processing_method": None,
                "delivery_location": None,
                "deadline_days": None
            },
            "missing_fields": ["quantity_kg", "variety", "grade", "processing_method", "delivery_location", "deadline_days"],
            "suggested_question": "I couldn't understand your request. Can you tell me how many kilograms of coffee you need?",
            "raw_interpretation": "Failed to parse response"
        }
        
    except Exception as e:
        logger.error(f"Error extracting RFQ from voice: {e}", exc_info=True)
        return {
            "confidence": 0.0,
            "extracted_fields": {
                "quantity_kg": None,
                "variety": None,
                "grade": None,
                "processing_method": None,
                "delivery_location": None,
                "deadline_days": None
            },
            "missing_fields": ["quantity_kg", "variety", "grade", "processing_method", "delivery_location", "deadline_days"],
            "suggested_question": "Sorry, I had trouble processing your message. Could you please try again?",
            "raw_interpretation": f"Error: {str(e)}"
        }


def format_rfq_preview(extracted_data: Dict[str, Any]) -> str:
    """
    Format extracted RFQ data into human-readable preview.
    
    Args:
        extracted_data: Result from extract_rfq_from_voice()
        
    Returns:
        Formatted string for Telegram message
    """
    fields = extracted_data.get('extracted_fields', {})
    missing = extracted_data.get('missing_fields', [])
    confidence = extracted_data.get('confidence', 0.0)
    
    # Build preview message
    message = "📋 *RFQ Preview*\n\n"
    
    # Show extracted fields
    if fields.get('quantity_kg'):
        message += f"📦 Quantity: {fields['quantity_kg']:,.0f} kg\n"
    if fields.get('variety'):
        message += f"☕ Variety: {fields['variety']}\n"
    if fields.get('grade'):
        message += f"⭐ Grade: {fields['grade']}\n"
    if fields.get('processing_method'):
        message += f"🔧 Processing: {fields['processing_method']}\n"
    if fields.get('delivery_location'):
        message += f"📍 Delivery: {fields['delivery_location']}\n"
    if fields.get('deadline_days'):
        from datetime import datetime, timedelta
        deadline = datetime.utcnow() + timedelta(days=fields['deadline_days'])
        message += f"⏰ Deadline: {deadline.strftime('%Y-%m-%d')} ({fields['deadline_days']} days)\n"
    
    # Show confidence
    if confidence >= 0.8:
        message += f"\n✅ Confidence: High ({confidence:.0%})\n"
    elif confidence >= 0.5:
        message += f"\n⚠️ Confidence: Medium ({confidence:.0%})\n"
    else:
        message += f"\n❌ Confidence: Low ({confidence:.0%})\n"
    
    # Show missing fields
    if missing:
        message += f"\n❓ Missing information:\n"
        field_names = {
            'quantity_kg': 'Quantity',
            'variety': 'Coffee variety',
            'grade': 'Quality grade',
            'processing_method': 'Processing method',
            'delivery_location': 'Delivery location',
            'deadline_days': 'Deadline'
        }
        for field in missing:
            message += f"  • {field_names.get(field, field)}\n"
    
    return message


def create_missing_field_question(missing_field: str) -> Dict[str, Any]:
    """
    Generate appropriate question for a missing field.
    
    Args:
        missing_field: Name of the missing field
        
    Returns:
        Dict with 'message' and optional 'keyboard'
    """
    questions = {
        'quantity_kg': {
            'message': "📦 How many kilograms of coffee do you need?",
            'keyboard': None
        },
        'variety': {
            'message': "☕ Which variety are you looking for?",
            'keyboard': {
                'inline_keyboard': [[
                    {'text': 'Arabica', 'callback_data': 'rfq_variety_Arabica'},
                    {'text': 'Sidama', 'callback_data': 'rfq_variety_Sidama'}
                ], [
                    {'text': 'Yirgacheffe', 'callback_data': 'rfq_variety_Yirgacheffe'},
                    {'text': 'Guji', 'callback_data': 'rfq_variety_Guji'}
                ], [
                    {'text': 'Limu', 'callback_data': 'rfq_variety_Limu'},
                    {'text': 'Harrar', 'callback_data': 'rfq_variety_Harrar'}
                ]]
            }
        },
        'grade': {
            'message': "⭐ What quality grade?",
            'keyboard': {
                'inline_keyboard': [[
                    {'text': 'Grade 1', 'callback_data': 'rfq_grade_Grade 1'},
                    {'text': 'Grade 2', 'callback_data': 'rfq_grade_Grade 2'}
                ], [
                    {'text': 'Grade 3', 'callback_data': 'rfq_grade_Grade 3'},
                    {'text': 'Any Grade', 'callback_data': 'rfq_grade_Any'}
                ]]
            }
        },
        'processing_method': {
            'message': "🔧 Which processing method?",
            'keyboard': {
                'inline_keyboard': [[
                    {'text': 'Washed', 'callback_data': 'rfq_processing_Washed'},
                    {'text': 'Natural', 'callback_data': 'rfq_processing_Natural'}
                ], [
                    {'text': 'Honey', 'callback_data': 'rfq_processing_Honey'},
                    {'text': 'Pulped Natural', 'callback_data': 'rfq_processing_Pulped Natural'}
                ]]
            }
        },
        'delivery_location': {
            'message': "📍 Where should it be delivered?",
            'keyboard': {
                'inline_keyboard': [[
                    {'text': 'Addis Ababa', 'callback_data': 'rfq_location_Addis Ababa'},
                    {'text': 'Djibouti Port', 'callback_data': 'rfq_location_Djibouti'}
                ], [
                    {'text': 'Dire Dawa', 'callback_data': 'rfq_location_Dire Dawa'},
                    {'text': 'Mombasa Port', 'callback_data': 'rfq_location_Mombasa'}
                ]]
            }
        },
        'deadline_days': {
            'message': "⏰ When do you need it delivered?",
            'keyboard': {
                'inline_keyboard': [[
                    {'text': '1 week', 'callback_data': 'rfq_deadline_7'},
                    {'text': '2 weeks', 'callback_data': 'rfq_deadline_14'}
                ], [
                    {'text': '1 month', 'callback_data': 'rfq_deadline_30'},
                    {'text': '2 months', 'callback_data': 'rfq_deadline_60'}
                ]]
            }
        }
    }
    
    return questions.get(missing_field, {
        'message': f"Please provide: {missing_field}",
        'keyboard': None
    })


if __name__ == "__main__":
    # Test the extractor
    test_cases = [
        "I want to buy 5000 kilograms of Yirgacheffe Grade 1 washed coffee, delivered to Addis Ababa in 3 weeks",
        "Need 2 tons of Sidama coffee",
        "Looking for high quality coffee for my roastery",
        "የ5ሺ ኪሎግራም የሲዳማ ቡና ፈለግ አደርጋለሁ",  # Amharic: "I need 5000kg of Sidama coffee"
    ]
    
    print("\n" + "="*70)
    print("VOICE RFQ EXTRACTION TEST")
    print("="*70)
    
    for i, test_input in enumerate(test_cases, 1):
        print(f"\n--- Test {i} ---")
        print(f"Input: {test_input}")
        
        result = extract_rfq_from_voice(test_input, language="am" if i == 4 else "en")
        
        print(f"\nResult:")
        print(f"  Confidence: {result['confidence']:.0%}")
        print(f"  Extracted: {json.dumps(result['extracted_fields'], indent=4)}")
        print(f"  Missing: {result['missing_fields']}")
        print(f"  Interpretation: {result['raw_interpretation']}")
        
        if result['suggested_question']:
            print(f"  Next Question: {result['suggested_question']}")
        
        print(f"\nFormatted Preview:")
        print(format_rfq_preview(result))
