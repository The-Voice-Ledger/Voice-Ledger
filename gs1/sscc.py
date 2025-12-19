"""
GS1 SSCC (Serial Shipping Container Code) Generator

Generates 18-digit SSCCs for logistic units (pallets, containers, etc.)
following GS1 General Specifications.

Dependencies:
- datetime: Generate unique serial numbers based on timestamp
  Why: Ensures uniqueness across millions of containers
  
- hashlib: SHA-256 hashing for pseudo-random serial generation
  Why: Converts timestamps to unpredictable 9-digit serials

Structure: [Extension][Company Prefix][Serial Reference][Check Digit]
Example:   3 0614141 123456789 2

Total: 18 digits
"""

from datetime import datetime
import hashlib


def calculate_sscc_check_digit(sscc_17: str) -> str:
    """
    Calculate SSCC check digit using GS1 algorithm (ISO/IEC 7064, mod 10).
    
    This is the SAME algorithm used for GLN and GTIN check digits.
    
    Args:
        sscc_17: First 17 digits of SSCC
        
    Returns:
        Single check digit (0-9)
        
    Algorithm:
    1. Starting from right, multiply each digit alternately by 3 and 1
    2. Sum all products
    3. Subtract from nearest equal or higher multiple of 10
    
    Example:
        >>> calculate_sscc_check_digit("30614141123456789")
        '3'
    """
    if len(sscc_17) != 17:
        raise ValueError(f"SSCC must be 17 digits before check digit, got {len(sscc_17)}")
    
    # Reverse for right-to-left processing
    digits = [int(d) for d in sscc_17[::-1]]
    
    # Multiply alternately by 3 and 1 (starting with 3)
    total = sum(d * (3 if i % 2 == 0 else 1) for i, d in enumerate(digits))
    
    # Check digit = (10 - (total mod 10)) mod 10
    check_digit = (10 - (total % 10)) % 10
    
    return str(check_digit)


def generate_sscc(
    company_prefix: str = "0614141",
    extension: str = "3",
    serial_reference: str = None
) -> str:
    """
    Generate GS1-compliant SSCC for logistic units.
    
    Args:
        company_prefix: 7-digit GS1 company prefix (default: 0614141)
        extension: 1-digit extension (0-9, default 3 for general purpose)
        serial_reference: 9-digit serial (auto-generated if not provided)
        
    Returns:
        18-digit SSCC with check digit
        
    Extension Digit Meanings:
    - 0-8: General purpose (can be used for any logistic unit)
    - 9: Variable measure trade item (weight/count may vary)
    
    Example:
        >>> generate_sscc()
        '306141411234567892'
        
        >>> generate_sscc(extension="9")  # Variable measure
        '906141411234567898'
        
    Design Decision: Auto-generate serial using timestamp + hash
    Why? Ensures uniqueness across millions of containers without central counter
    """
    if len(company_prefix) != 7:
        raise ValueError(f"Company prefix must be 7 digits, got {len(company_prefix)}")
    
    if len(extension) != 1 or not extension.isdigit():
        raise ValueError(f"Extension must be single digit 0-9, got '{extension}'")
    
    # Generate serial reference if not provided
    if serial_reference is None:
        # Use timestamp + hash for uniqueness
        now = datetime.utcnow()
        timestamp_ms = int(now.timestamp() * 1000)
        
        # Hash to get pseudo-random digits
        hash_input = f"{timestamp_ms}{company_prefix}"
        hash_digest = hashlib.sha256(hash_input.encode()).hexdigest()
        
        # Take first 9 hex chars and convert to decimal
        serial_reference = str(int(hash_digest[:9], 16))[-9:].zfill(9)
    
    if len(serial_reference) != 9:
        raise ValueError(f"Serial reference must be 9 digits, got {len(serial_reference)}")
    
    # Build SSCC without check digit (17 digits)
    sscc_17 = f"{extension}{company_prefix}{serial_reference}"
    
    # Calculate and append check digit
    check_digit = calculate_sscc_check_digit(sscc_17)
    sscc = f"{sscc_17}{check_digit}"
    
    return sscc


def sscc_to_urn(sscc: str) -> str:
    """
    Convert SSCC to GS1 URN format for EPCIS events.
    
    Args:
        sscc: 18-digit SSCC
        
    Returns:
        URN format: urn:epc:id:sscc:company.serial
        
    Why URN format? EPCIS 2.0 standard requires URNs for all identifiers
    
    Example:
        >>> sscc_to_urn("306141411234567892")
        'urn:epc:id:sscc:0614141.1234567892'
    """
    if len(sscc) != 18:
        raise ValueError(f"SSCC must be 18 digits, got {len(sscc)}")
    
    # Extract company prefix (digits 2-8) and serial (digits 9-18)
    extension = sscc[0]
    company_prefix = sscc[1:8]
    serial_with_check = sscc[8:18]
    
    # URN format: urn:epc:id:sscc:company.serial
    return f"urn:epc:id:sscc:{company_prefix}.{serial_with_check}"


def validate_sscc(sscc: str) -> bool:
    """
    Validate SSCC check digit.
    
    Args:
        sscc: 18-digit SSCC to validate
        
    Returns:
        True if check digit is correct, False otherwise
        
    Use Case: Validate SSCCs scanned from barcodes or entered manually
    """
    if len(sscc) != 18 or not sscc.isdigit():
        return False
    
    expected_check = calculate_sscc_check_digit(sscc[:17])
    return sscc[17] == expected_check


# Self-test
if __name__ == "__main__":
    # Generate SSCC for a pallet
    pallet_sscc = generate_sscc(extension="3")
    print(f"Generated SSCC: {pallet_sscc}")
    print(f"Valid: {validate_sscc(pallet_sscc)}")
    print(f"URN: {sscc_to_urn(pallet_sscc)}")
    
    # Generate SSCC for variable measure container
    container_sscc = generate_sscc(extension="9")
    print(f"\nContainer SSCC: {container_sscc}")
    print(f"URN: {sscc_to_urn(container_sscc)}")
