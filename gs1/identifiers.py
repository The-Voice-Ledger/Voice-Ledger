"""
GS1 Identifier Generation Module

This module generates three types of GS1 identifiers:
- GLN (Global Location Number): Identifies parties and physical locations
- GTIN (Global Trade Item Number): Identifies products
- SSCC (Serial Shipping Container Code): Identifies logistic units

All identifiers use a common company prefix for this prototype.
"""

PREFIX = "0614141"  # Example GS1 company prefix


def gln(location_code: str) -> str:
    """
    Generate a Global Location Number (GLN) with check digit per GS1 standards.
    
    GLN Format: Company Prefix (7 digits) + Location Reference (5 digits) + Check Digit (1)
    
    Args:
        location_code: Unique location identifier (will be zero-padded to 5 digits)
    
    Returns:
        13-digit GLN string with check digit
    
    Example:
        >>> gln("10")
        '0614141000108'  # Last digit is check digit
    """
    # GLN: company prefix (7) + location ref (5) + check digit (1) = 13 total
    base = PREFIX + location_code.zfill(5)
    return base + calculate_check_digit(base)


def calculate_check_digit(code: str) -> str:
    """
    Calculate GS1 check digit using the standard algorithm.
    
    Args:
        code: Numeric string without check digit
    
    Returns:
        Single digit check digit as string
    """
    # GS1 check digit algorithm: weight alternates 3,1,3,1... from right to left
    total = sum(int(digit) * (3 if i % 2 else 1) for i, digit in enumerate(reversed(code)))
    check_digit = (10 - (total % 10)) % 10
    return str(check_digit)


def gtin(product_code: str, gtin_format: str = "GTIN-14") -> str:
    """
    Generate a Global Trade Item Number (GTIN) with check digit.
    
    Supports GTIN-13 and GTIN-14 formats per GS1 standards.
    
    Args:
        product_code: Unique product identifier (5-6 digits recommended)
        gtin_format: "GTIN-13" (13 digits) or "GTIN-14" (14 digits)
    
    Returns:
        GTIN string with check digit
    
    Examples:
        >>> gtin("12345", "GTIN-13")
        '0614141012345X'  # X = check digit
        >>> gtin("12345", "GTIN-14")
        '00614141012345X'  # X = check digit
    """
    if gtin_format == "GTIN-13":
        # GTIN-13: company prefix (7) + product code (5) + check digit (1)
        base = PREFIX + product_code.zfill(5)
        return base + calculate_check_digit(base)
    elif gtin_format == "GTIN-14":
        # GTIN-14: indicator (1) + company prefix (7) + product code (5) + check digit (1)
        base = "0" + PREFIX + product_code.zfill(5)
        return base + calculate_check_digit(base)
    else:
        raise ValueError(f"Unsupported GTIN format: {gtin_format}. Use 'GTIN-13' or 'GTIN-14'.")


def sscc(serial: str) -> str:
    """
    Generate a Serial Shipping Container Code (SSCC) with check digit per GS1 standards.
    
    SSCC Format: Extension Digit (1) + Company Prefix (7) + Serial Reference (9) + Check Digit (1)
    
    Args:
        serial: Unique serial number (will be zero-padded to 9 digits)
    
    Returns:
        18-digit SSCC string with check digit
    
    Example:
        >>> sscc("999")
        '006141410000000999X'  # X = check digit
    """
    # SSCC: extension (1) + company prefix (7) + serial ref (9) + check digit (1) = 18 total
    base = "0" + PREFIX + serial.zfill(9)
    return base + calculate_check_digit(base)


def gtin_to_sgtin_urn(gtin_14: str, serial_number: str) -> str:
    """
    Convert GTIN-14 to SGTIN URN format per GS1 EPCIS 2.0 standard.
    
    SGTIN URN Format: urn:epc:id:sgtin:CompanyPrefix.ItemRefAndIndicator.SerialNumber
    
    GTIN-14 Structure: [Indicator(1)][CompanyPrefix(7)][ItemRef(5)][CheckDigit(1)]
    
    For SGTIN URN:
    - CompanyPrefix: digits 1-7 (skip indicator digit 0)
    - ItemRefAndIndicator: digits 7-13 (item ref + check digit)
    - SerialNumber: batch_id or serial
    
    Args:
        gtin_14: 14-digit GTIN (e.g., "00614141165623")
        serial_number: Batch ID or serial number (e.g., "BATCH-001")
    
    Returns:
        GS1-compliant SGTIN URN
    
    Example:
        >>> gtin_to_sgtin_urn("00614141165623", "BATCH-001")
        'urn:epc:id:sgtin:0614141.165623.BATCH-001'
    """
    if len(gtin_14) != 14:
        raise ValueError(f"GTIN must be 14 digits, got {len(gtin_14)}")
    
    # Extract components (skip indicator digit at position 0)
    company_prefix = gtin_14[1:8]  # 7 digits
    item_ref_and_check = gtin_14[8:14]  # 5 digits item ref + 1 check digit
    
    return f"urn:epc:id:sgtin:{company_prefix}.{item_ref_and_check}.{serial_number}"
