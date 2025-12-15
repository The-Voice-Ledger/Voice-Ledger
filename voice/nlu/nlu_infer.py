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
    
    system_prompt = """You are an AI assistant specialized in extracting structured information from coffee supply chain voice commands spoken by Ethiopian coffee farmers.

Your task: Identify the INTENT (action) and extract ENTITIES (details) from voice transcripts.

=== INTENT CLASSIFICATION RULES ===

1. record_commission - Creating a NEW batch (farmer harvesting/producing):
   Indicators: "new batch", "harvested", "picked", "produced", "commission", "I have", "from my farm"
   Examples:
   - "New batch of 50 kilograms Sidama variety from Manufam"
   - "I harvested 100 kilos of Yirgacheffe today"
   - "50 bags from Gedeo farm"
   - "Picked 75 kg of washed Sidama"
   NO batch_id is mentioned (farmer creating it now)

2. record_receipt - RECEIVING an existing batch:
   Indicators: "received", "got", "accepted", "arrived from", "delivery from"
   Examples:
   - "Received batch ABC123 from Abebe"
   - "Got 50 kilos, batch number 456"
   - "Accepted delivery of batch XYZ"
   MUST mention receiving FROM someone/somewhere OR reference a batch_id

3. record_shipment - SENDING an existing batch:
   Indicators: "sent", "shipped", "delivered", "dispatched", "sending to"
   Examples:
   - "Shipped batch ABC123 to Addis warehouse"
   - "Sent 50 bags to the cooperative"
   - "Delivered batch 789 to export station"
   MUST mention sending TO someone/somewhere AND reference a batch_id

4. record_transformation - PROCESSING coffee:
   Indicators: "washed", "dried", "hulled", "roasted", "milled", "processed"
   Examples:
   - "Washed batch ABC123"
   - "Dried the coffee from yesterday"
   MUST reference processing activity AND batch_id

=== DECISION LOGIC ===
- If speaker says "new batch" OR describes harvesting/picking → record_commission
- If no batch_id mentioned AND describes quantity from a location → record_commission (farmer listing what they have)
- If "received" or "got" or "arrived" → record_receipt
- If "sent" or "shipped" or "delivered to" → record_shipment
- If describes processing activity → record_transformation

=== ENTITY EXTRACTION ===
Extract these entities:
- quantity: Number (e.g., 50, 100)
- unit: "kilograms", "kg", "bags", "kilos", etc.
- product: Coffee variety/type (e.g., "Sidama", "Yirgacheffe", "washed coffee", "arabica")
- origin: Farm name, location, or farmer name where coffee came FROM
- destination: Where coffee is going TO (for shipments)
- batch_id: Existing batch identifier (for receipt/shipment/transformation)

=== OUTPUT FORMAT ===
Return ONLY valid JSON:
{
  "intent": "record_commission",
  "entities": {
    "quantity": 50,
    "unit": "kilograms",
    "product": "Sidama variety",
    "origin": "Manufam",
    "destination": null,
    "batch_id": null
  }
}

If a field is not mentioned, set it to null. Do NOT add explanations, only JSON."""

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
