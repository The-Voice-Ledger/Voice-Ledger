#!/usr/bin/env python3
"""
Test Global Forest Watch API Key

Verifies that your GFW API key is properly configured and working.

Usage:
    python scripts/test_gfw_api.py
"""

import os
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import requests
from dotenv import load_dotenv


def print_success(msg):
    print(f"✅ {msg}")

def print_error(msg):
    print(f"❌ {msg}")

def print_info(msg):
    print(f"ℹ️  {msg}")


def test_api_key():
    """Test the GFW API key"""
    
    # Load environment
    load_dotenv()
    
    api_key = os.getenv("GFW_API_KEY")
    
    print("\n" + "="*70)
    print("Global Forest Watch API Key Test".center(70))
    print("="*70 + "\n")
    
    # Check if key exists
    if not api_key:
        print_error("GFW_API_KEY not found in environment!")
        print_info("Run: python scripts/register_gfw_api.py")
        return False
    
    print_info(f"API Key found: {api_key[:8]}...{api_key[-8:]}")
    
    # Test 1: List datasets
    print("\n📋 Test 1: List Available Datasets")
    try:
        response = requests.get(
            "https://data-api.globalforestwatch.org/datasets",
            headers={"x-api-key": api_key},
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            datasets = data.get("data", [])
            print_success(f"Found {len(datasets)} datasets")
            
            # Show some interesting ones
            eudr_datasets = [d for d in datasets if 'tree' in d.get('dataset', '').lower() or 'forest' in d.get('dataset', '').lower()]
            if eudr_datasets:
                print_info(f"EUDR-relevant datasets: {len(eudr_datasets)}")
                for ds in eudr_datasets[:3]:
                    print(f"   - {ds.get('dataset', 'Unknown')}")
        else:
            print_error(f"Failed with status {response.status_code}")
            print(response.text[:200])
            return False
            
    except Exception as e:
        print_error(f"Request failed: {e}")
        return False
    
    # Test 2: Check specific dataset (UMD Tree Cover Loss)
    print("\n🌲 Test 2: Check UMD Tree Cover Loss Dataset")
    try:
        response = requests.get(
            "https://data-api.globalforestwatch.org/dataset/umd_tree_cover_loss/latest",
            headers={"x-api-key": api_key},
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            dataset_info = data.get("data", {})
            version = dataset_info.get("version", "Unknown")
            print_success(f"Dataset accessible - Version: {version}")
        else:
            print_error(f"Failed with status {response.status_code}")
            return False
            
    except Exception as e:
        print_error(f"Request failed: {e}")
        return False
    
    # Test 3: Test actual deforestation check (using our module)
    print("\n🛰️  Test 3: Deforestation Check (Real API Call)")
    try:
        from voice.verification.deforestation_checker import DeforestationChecker
        
        checker = DeforestationChecker(api_key=api_key)
        
        # Test coordinates (Addis Ababa - should be clean)
        result = checker.check_deforestation(
            latitude=9.0320,
            longitude=38.7469,
            radius_meters=1000
        )
        
        print_success("Deforestation check completed!")
        print(f"   Location: Addis Ababa test point")
        print(f"   Compliant: {'✅ YES' if result.compliant else '❌ NO'}")
        print(f"   Risk Level: {result.risk_level}")
        print(f"   Tree Loss: {result.tree_cover_loss_hectares:.4f} ha")
        print(f"   Confidence: {result.confidence * 100:.1f}%")
        
    except Exception as e:
        print_error(f"Deforestation check failed: {e}")
        print_info("This might be expected if you just registered (API needs time)")
        return False
    
    # Summary
    print("\n" + "="*70)
    print_success("All tests passed! API key is working correctly! 🎉")
    print("="*70 + "\n")
    
    print("Next steps:")
    print("  1. Run full test suite: pytest tests/test_deforestation_checker.py -v")
    print("  2. Test workflow: pytest tests/test_eudr_workflow.py -v")
    print("  3. Monitor in production logs")
    
    return True


if __name__ == "__main__":
    try:
        success = test_api_key()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\nTest cancelled by user.")
        sys.exit(0)
    except Exception as e:
        print_error(f"Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
