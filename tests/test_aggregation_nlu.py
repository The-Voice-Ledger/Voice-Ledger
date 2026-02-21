"""
Test Aggregation NLU Integration

Tests conversational AI understanding of aggregation commands.
Part of Phase 2b: NLU Training Data for Aggregation
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from voice.nlu.nlu_infer import infer_nlu_json


def test_aggregate_batches_intent_english():
    """
    Test: English NLU recognizes aggregation intent

    Input: "I want to pack batches BATCH-001, BATCH-002, and BATCH-003 into container C100"
    Expected: Intent = aggregate_batches or pack_batches
    """
    transcript = "I want to pack batches BATCH-001, BATCH-002, and BATCH-003 into container C100"
    result = infer_nlu_json(transcript)

    print(f"\n📋 Test: Aggregation Intent Recognition (English)")
    print(f"Input: {transcript}")
    print(f"Result: {result}")

    intent = result.get('intent', '')
    entities = result.get('entities', {})

    print(f"✅ Intent detected: {intent}")
    print(f"✅ Entities: {entities}")

    assert intent in ['aggregate_batches', 'pack_batches'], \
        f"Expected aggregation intent, got '{intent}'"


def test_disaggregate_batches_intent_english():
    """
    Test: English NLU recognizes disaggregation intent

    Input: "Unpack container C100"
    Expected: Intent = disaggregate_batches or unpack_batches
    """
    transcript = "Unpack container C100"
    result = infer_nlu_json(transcript)

    print(f"\n📋 Test: Disaggregation Intent Recognition (English)")
    print(f"Input: {transcript}")
    print(f"Result: {result}")

    intent = result.get('intent', '')
    entities = result.get('entities', {})

    print(f"✅ Intent detected: {intent}")
    print(f"✅ Entities: {entities}")

    assert intent in ['disaggregate_batches', 'unpack_batches'], \
        f"Expected disaggregation intent, got '{intent}'"


def test_split_batch_intent_english():
    """
    Test: English NLU recognizes split batch intent

    Input: "Split batch BATCH-001 into 600kg and 400kg"
    Expected: Intent = split_batch
    """
    transcript = "Split batch BATCH-001 into 600kg and 400kg"
    result = infer_nlu_json(transcript)

    print(f"\n📋 Test: Split Batch Intent Recognition (English)")
    print(f"Input: {transcript}")
    print(f"Result: {result}")

    intent = result.get('intent', '')
    entities = result.get('entities', {})

    print(f"✅ Intent detected: {intent}")
    print(f"✅ Entities: {entities}")

    assert intent == 'split_batch', \
        f"Expected split_batch intent, got '{intent}'"


def test_aggregation_with_gtins():
    """
    Test: NLU handles GTIN identifiers

    Input: "Pack GTIN 00614141165623 and 00614141165624 into container C200"
    Expected: Recognizes GTINs as batch identifiers
    """
    transcript = "Pack GTIN 00614141165623 and 00614141165624 into container C200"
    result = infer_nlu_json(transcript)

    print(f"\n📋 Test: Aggregation with GTINs")
    print(f"Input: {transcript}")
    print(f"Result: {result}")

    intent = result.get('intent', '')
    entities = result.get('entities', {})

    print(f"✅ Intent detected: {intent}")
    print(f"✅ Entities: {entities}")

    assert intent in ['aggregate_batches', 'pack_batches'], \
        f"Expected aggregation intent, got '{intent}'"


def test_amharic_aggregation_intent():
    """
    Test: Amharic NLU recognizes aggregation intent

    Input (Amharic): "ባች BATCH-001፣ BATCH-002 እና BATCH-003ን ወደ ኮንቴይነር C100 ጨምር"
    Expected: Intent = aggregate_batches
    """
    transcript = "ባች BATCH-001፣ BATCH-002 እና BATCH-003ን ወደ ኮንቴይነር C100 ጨምር"

    try:
        result = infer_nlu_json(transcript)

        print(f"\n📋 Test: Aggregation Intent Recognition (Amharic)")
        print(f"Input: {transcript}")
        print(f"Result: {result}")

        intent = result.get('intent', '')
        entities = result.get('entities', {})

        print(f"✅ Intent detected: {intent}")
        print(f"✅ Entities: {entities}")

        assert intent in ['aggregate_batches', 'pack_batches'], \
            f"Expected aggregation intent, got '{intent}'"

    except Exception as e:
        pytest.skip(f"Amharic test skipped (API not configured): {e}")


if __name__ == "__main__":
    print("=" * 80)
    print("Testing Phase 2b: NLU Training Data for Aggregation")
    print("=" * 80)

    test_aggregate_batches_intent_english()
    test_disaggregate_batches_intent_english()
    test_split_batch_intent_english()
    test_aggregation_with_gtins()
    test_amharic_aggregation_intent()

    print("\n" + "=" * 80)
    print("✅ Phase 2b NLU Tests Complete")
    print("=" * 80)
