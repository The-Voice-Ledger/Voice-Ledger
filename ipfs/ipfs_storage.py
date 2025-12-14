"""
IPFS Storage Module using Pinata

Provides functions to upload EPCIS events and DPP data to IPFS via Pinata.
Stores IPFS CIDs in database for retrieval.

Updated: December 14, 2025
"""

import json
import os
import requests
from typing import Dict, Any, Optional
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# Pinata Configuration
PINATA_JWT = os.getenv("PINATA_JWT")
PINATA_API_URL = "https://api.pinata.cloud"
PINATA_GATEWAY = "https://gateway.pinata.cloud/ipfs"


def pin_json_to_ipfs(data: Dict[str, Any], name: Optional[str] = None) -> Optional[str]:
    """
    Pin JSON data to IPFS via Pinata.
    
    Args:
        data: Dictionary to upload (EPCIS event, DPP, credential)
        name: Optional name for the pinned file
    
    Returns:
        IPFS CID (Content Identifier) or None if failed
    """
    if not PINATA_JWT:
        print("⚠️  PINATA_JWT not configured in .env")
        return None
    
    headers = {
        "Authorization": f"Bearer {PINATA_JWT}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "pinataContent": data,
        "pinataMetadata": {
            "name": name or "voice-ledger-data"
        }
    }
    
    try:
        response = requests.post(
            f"{PINATA_API_URL}/pinning/pinJSONToIPFS",
            json=payload,
            headers=headers,
            timeout=30
        )
        response.raise_for_status()
        
        result = response.json()
        ipfs_hash = result.get("IpfsHash")
        
        if ipfs_hash:
            print(f"✅ Pinned to IPFS: {ipfs_hash}")
            print(f"   Gateway URL: {PINATA_GATEWAY}/{ipfs_hash}")
            return ipfs_hash
        else:
            print("⚠️  No IPFS hash returned")
            return None
            
    except requests.exceptions.RequestException as e:
        print(f"❌ Pinata upload failed: {e}")
        return None


def pin_file_to_ipfs(file_path: Path, name: Optional[str] = None) -> Optional[str]:
    """
    Pin a file to IPFS via Pinata.
    
    Args:
        file_path: Path to file to upload
        name: Optional name for the pinned file
    
    Returns:
        IPFS CID or None if failed
    """
    if not PINATA_JWT:
        print("⚠️  PINATA_JWT not configured in .env")
        return None
    
    if not file_path.exists():
        print(f"❌ File not found: {file_path}")
        return None
    
    headers = {
        "Authorization": f"Bearer {PINATA_JWT}"
    }
    
    with open(file_path, 'rb') as f:
        files = {
            'file': (file_path.name, f)
        }
        
        data = {
            "pinataMetadata": json.dumps({
                "name": name or file_path.name
            })
        }
        
        try:
            response = requests.post(
                f"{PINATA_API_URL}/pinning/pinFileToIPFS",
                files=files,
                data=data,
                headers=headers,
                timeout=60
            )
            response.raise_for_status()
            
            result = response.json()
            ipfs_hash = result.get("IpfsHash")
            
            if ipfs_hash:
                print(f"✅ Pinned file to IPFS: {ipfs_hash}")
                print(f"   Gateway URL: {PINATA_GATEWAY}/{ipfs_hash}")
                return ipfs_hash
            else:
                print("⚠️  No IPFS hash returned")
                return None
                
        except requests.exceptions.RequestException as e:
            print(f"❌ Pinata file upload failed: {e}")
            return None


def get_from_ipfs(ipfs_hash: str) -> Optional[Dict[str, Any]]:
    """
    Retrieve JSON data from IPFS via Pinata gateway.
    
    Args:
        ipfs_hash: IPFS CID to retrieve
    
    Returns:
        Parsed JSON data or None if failed
    """
    try:
        url = f"{PINATA_GATEWAY}/{ipfs_hash}"
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"❌ IPFS retrieval failed for {ipfs_hash}: {e}")
        return None


def pin_epcis_event(event: Dict[str, Any], event_hash: str) -> Optional[str]:
    """
    Pin an EPCIS event to IPFS with descriptive name.
    
    Args:
        event: Complete EPCIS event JSON
        event_hash: SHA-256 hash of canonicalized event
    
    Returns:
        IPFS CID or None
    """
    event_type = event.get("type", "unknown")
    biz_step = event.get("bizStep", "unknown").split(":")[-1]
    name = f"epcis-{event_type}-{biz_step}-{event_hash[:8]}.json"
    
    return pin_json_to_ipfs(event, name=name)


def pin_dpp(dpp: Dict[str, Any], batch_id: str) -> Optional[str]:
    """
    Pin a Digital Product Passport to IPFS.
    
    Args:
        dpp: Complete DPP JSON
        batch_id: Batch identifier
    
    Returns:
        IPFS CID or None
    """
    name = f"dpp-{batch_id}.json"
    return pin_json_to_ipfs(dpp, name=name)


def pin_credential(credential: Dict[str, Any], credential_id: str) -> Optional[str]:
    """
    Pin a Verifiable Credential to IPFS.
    
    Args:
        credential: W3C Verifiable Credential JSON
        credential_id: Credential identifier
    
    Returns:
        IPFS CID or None
    """
    name = f"credential-{credential_id}.json"
    return pin_json_to_ipfs(credential, name=name)


def get_pinned_files() -> Optional[Dict[str, Any]]:
    """
    List all files pinned to this Pinata account.
    
    Returns:
        Dict with pinned file information or None
    """
    if not PINATA_JWT:
        print("⚠️  PINATA_JWT not configured in .env")
        return None
    
    headers = {
        "Authorization": f"Bearer {PINATA_JWT}"
    }
    
    try:
        response = requests.get(
            f"{PINATA_API_URL}/data/pinList",
            headers=headers,
            timeout=30
        )
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"❌ Failed to list pinned files: {e}")
        return None


if __name__ == "__main__":
    # Test Pinata connection
    print("🧪 Testing Pinata IPFS Integration...")
    
    test_data = {
        "test": "voice-ledger-pinata-test",
        "timestamp": "2025-12-14T00:00:00Z",
        "message": "Testing IPFS storage via Pinata"
    }
    
    print("\n1️⃣ Testing JSON upload...")
    cid = pin_json_to_ipfs(test_data, name="voice-ledger-test")
    
    if cid:
        print(f"\n2️⃣ Testing retrieval...")
        retrieved = get_from_ipfs(cid)
        if retrieved:
            print(f"✅ Retrieved data matches: {retrieved == test_data}")
        
        print(f"\n3️⃣ Listing pinned files...")
        pinned = get_pinned_files()
        if pinned:
            count = pinned.get("count", 0)
            print(f"✅ Total pinned files: {count}")
    
    print("\n✅ Pinata integration test complete!")
