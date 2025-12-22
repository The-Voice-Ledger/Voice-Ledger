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

4. record_transformation - PROCESSING coffee (changes physical/chemical properties):
   Indicators: "roasted", "roasting", "milled", "milling", "dried", "drying", "hulled", "hulling", "processed", "transform"
   Examples:
   - "Roast batch ABC123 producing 850 kilograms"
   - "Record transformation roasting batch ABC123"
   - "Milled batch 456 output 500kg"
   MUST reference processing activity AND batch_id AND output quantity

5. pack_batches - AGGREGATING multiple batches into a container:
   Indicators: "pack", "packing", "aggregate", "combine", "put into container", "load into pallet", "consolidate"
   Examples:
   - "Pack batches ABC123 and DEF456 into pallet PALLET-001"
   - "Aggregate batches into container CTN-789"
   - "Combine batches XYZ and QRS into container"
   MUST reference multiple batch_ids AND container_id

6. unpack_batches - DISAGGREGATING container into batches:
   Indicators: "unpack", "unpacking", "disaggregate", "unload", "break down container", "open container"
   Examples:
   - "Unpack container PALLET-001"
   - "Disaggregate pallet CTN-789"
   - "Unload container XYZ"
   MUST reference container_id

7. split_batch - DIVIDING one batch into multiple smaller portions:
   Indicators: "split", "divide", "separate", "break up", "portion into"
   Examples:
   - "Split batch ABC123 into 600kg for Europe and 400kg for Asia"
   - "Divide batch 456 into three portions"
   - "Separate batch XYZ into 500kg and 300kg"
   MUST reference single parent batch_id AND multiple output quantities/destinations

=== DECISION LOGIC ===
- If speaker says "new batch" OR describes harvesting/picking → record_commission
- If no batch_id mentioned AND describes quantity from a location → record_commission (farmer listing what they have)
- If "received" or "got" or "arrived" → record_receipt
- If "sent" or "shipped" or "delivered to" → record_shipment
- If describes processing activity (roasting, milling, drying) → record_transformation
- If describes packing/aggregating multiple batches into container → pack_batches
- If describes unpacking/disaggregating a container → unpack_batches
- If describes splitting one batch into multiple portions → split_batch

=== ENTITY EXTRACTION ===
Extract these entities based on intent:

Common entities (all intents):
- quantity: Number (e.g., 50, 100)
- unit: "kilograms", "kg", "bags", "kilos", etc.
- product: Coffee variety/type (e.g., "Sidama", "Yirgacheffe", "washed coffee", "arabica")
- origin: Farm name, location, or farmer name where coffee came FROM
- destination: Where coffee is going TO (for shipments/splits)
- batch_id: Existing batch identifier (string or list of strings for pack_batches)

Additional entities for specific intents:
- transformation_type: "roasting", "milling", "drying" (for record_transformation)
- output_quantity: Output quantity in kg (for record_transformation)
- container_id: Container/pallet identifier (for pack_batches, unpack_batches)
- child_batches: List of batch IDs being packed (for pack_batches)
- parent_batch_id: Source batch being split (for split_batch)
- splits: List of {quantity_kg, destination} for split portions (for split_batch)

=== OUTPUT FORMAT ===
Return ONLY valid JSON:

For record_commission:
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

For pack_batches:
{
  "intent": "pack_batches",
  "entities": {
    "batch_id": ["ABC123", "DEF456"],
    "container_id": "PALLET-001",
    "quantity": null,
    "unit": null,
    "product": null,
    "origin": null,
    "destination": null
  }
}

For split_batch:
{
  "intent": "split_batch",
  "entities": {
    "batch_id": "ABC123",
    "quantity": 600,
    "unit": "kilograms",
    "destination": "Europe",
    "product": null,
    "origin": null
  }
}

If a field is not mentioned, set it to null. Do NOT add explanations, only JSON."""

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",  # Upgraded from gpt-3.5-turbo for better intent accuracy
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
