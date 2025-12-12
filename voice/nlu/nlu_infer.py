"""
Natural Language Understanding (NLU) Module

This module extracts intents and entities from transcribed text using OpenAI's GPT API.
It identifies supply chain actions (intents) and key information (entities) from voice commands.
"""

import os
import json
from openai import OpenAI
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Initialize OpenAI client
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


def infer_nlu_json(transcript: str) -> dict:
    """
    Extract intent and entities from a transcript using GPT.
    
    Args:
        transcript: Text transcription from ASR
        
    Returns:
        Dictionary with structure:
        {
            "transcript": str,
            "intent": str,  # e.g., "record_shipment", "record_commission", "record_receipt"
            "entities": {
                "quantity": int,
                "unit": str,
                "product": str,
                "origin": str,
                "destination": str,
                # ... other relevant entities
            }
        }
        
    Example:
        >>> result = infer_nlu_json("Deliver 50 bags of washed coffee from station Abebe to Addis")
        >>> print(result["intent"])
        "record_shipment"
        >>> print(result["entities"]["quantity"])
        50
    """
    
    system_prompt = """You are an AI assistant that extracts structured information from supply chain voice commands.

Extract the following:
1. Intent: The action being described (record_shipment, record_commission, record_receipt, record_transformation)
2. Entities: Key information like quantity, unit, product, origin, destination, batch_id, etc.

Return ONLY a JSON object with this structure:
{
  "intent": "intent_name",
  "entities": {
    "quantity": number or null,
    "unit": "string or null",
    "product": "string or null",
    "origin": "string or null",
    "destination": "string or null",
    "batch_id": "string or null"
  }
}

If a field is not mentioned, set it to null."""

    try:
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": transcript}
            ],
            temperature=0.1,
            max_tokens=300
        )
        
        # Parse the GPT response
        content = response.choices[0].message.content.strip()
        nlu_data = json.loads(content)
        
        # Return complete structure
        return {
            "transcript": transcript,
            "intent": nlu_data.get("intent", "unknown"),
            "entities": nlu_data.get("entities", {})
        }
        
    except Exception as e:
        # Fallback if NLU fails
        return {
            "transcript": transcript,
            "intent": "unknown",
            "entities": {},
            "error": str(e)
        }


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python -m voice.nlu.nlu_infer '<transcript text>'")
        sys.exit(1)
    
    text = " ".join(sys.argv[1:])
    result = infer_nlu_json(text)
    print(json.dumps(result, indent=2))
