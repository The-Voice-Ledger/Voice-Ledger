#!/usr/bin/env python3
"""
Extract ABIs from Foundry build artifacts and save to blockchain_abis/ directory.
"""
import json
import os
from pathlib import Path

def extract_abis():
    """Extract ABIs from out/ folder to blockchain_abis/"""
    
    # Paths
    out_dir = Path(__file__).parent / "out"
    abi_dir = Path(__file__).parent / "blockchain_abis"
    
    # Create blockchain_abis directory if it doesn't exist
    abi_dir.mkdir(exist_ok=True)
    
    # Contracts to extract
    contracts = {
        "EPCISEventAnchor": "EPCISEventAnchor.sol/EPCISEventAnchor.json",
        "CoffeeBatchToken": "CoffeeBatchToken.sol/CoffeeBatchToken.json",
        "SettlementContract": "SettlementContract.sol/SettlementContract.json"
    }
    
    print("Extracting ABIs from Foundry build artifacts...\n")
    
    for contract_name, artifact_path in contracts.items():
        full_path = out_dir / artifact_path
        
        if not full_path.exists():
            print(f"❌ {contract_name}: Artifact not found at {full_path}")
            continue
        
        try:
            # Read the Foundry artifact
            with open(full_path, 'r') as f:
                artifact = json.load(f)
            
            # Extract just the ABI
            abi = artifact.get('abi', [])
            
            if not abi:
                print(f"⚠️  {contract_name}: No ABI found in artifact")
                continue
            
            # Save to blockchain_abis/
            output_path = abi_dir / f"{contract_name}.json"
            with open(output_path, 'w') as f:
                json.dump(abi, f, indent=2)
            
            print(f"✅ {contract_name}: Extracted {len(abi)} ABI entries → {output_path}")
        
        except Exception as e:
            print(f"❌ {contract_name}: Error - {e}")
    
    print(f"\n✅ ABI extraction complete. Files saved to: {abi_dir}")

if __name__ == "__main__":
    extract_abis()
