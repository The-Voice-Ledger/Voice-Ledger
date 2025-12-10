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
    Generate a Global Location Number (GLN).
    
    Args:
        location_code: Unique location identifier (will be zero-padded to 6 digits)
    
    Returns:
        13-digit GLN string
    
    Example:
        >>> gln("10")
        '061414100000010'
    """
    return PREFIX + location_code.zfill(6)


def gtin(product_code: str) -> str:
    """
    Generate a Global Trade Item Number (GTIN).
    
    Args:
        product_code: Unique product identifier (will be zero-padded to 6 digits)
    
    Returns:
        13-digit GTIN string
    
    Example:
        >>> gtin("200")
        '061414100000200'
    """
    return PREFIX + product_code.zfill(6)


def sscc(serial: str) -> str:
    """
    Generate a Serial Shipping Container Code (SSCC).
    
    Args:
        serial: Unique serial number (will be zero-padded to 9 digits)
    
    Returns:
        18-digit SSCC string (starts with extension digit '0')
    
    Example:
        >>> sscc("999")
        '0061414100000000999'
    """
    base = PREFIX + serial.zfill(9)
    return "0" + base  # SSCC starts with an extension digit
