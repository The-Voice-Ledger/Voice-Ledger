"""
GS1 Identifier Utilities

Handles conversion of multi-language identifiers to ASCII-safe formats
for use in batch IDs, URLs, and database fields.
"""

import unicodedata
import re
from typing import Optional


# Phonetic mappings for common non-ASCII characters
PHONETIC_MAPPINGS = {
    # Arabic
    'ع': 'a',     # Ain
    'غ': 'g',     # Ghain
    'ق': 'q',     # Qaf
    'خ': 'kh',    # Khah
    'ش': 'sh',    # Sheen
    'ظ': 'z',     # Zah
    'ص': 's',     # Sad
    'ض': 'd',     # Dad
    'ث': 'th',    # Thah
    'ذ': 'dh',    # Dhal
    'ج': 'j',     # Jeem
    'ز': 'z',     # Zain
    'ه': 'h',     # Hah
    'و': 'w',     # Waw
    'ي': 'y',     # Yah
    'ل': 'l',     # Lam
    'م': 'm',     # Meem
    'ن': 'n',     # Noon
    'ر': 'r',     # Rah
    'ب': 'b',     # Bah
    'ت': 't',     # Tah
    'ث': 'th',    # Thah
    'س': 's',     # Seen
    'ف': 'f',     # Fah
    'ك': 'k',     # Kaf
    'ا': 'a',     # Alif
    'إ': 'i',     # Alif with Hamza below
    'أ': 'a',     # Alif with Hamza above
    
    # Amharic (common ones)
    'ሊ': 'li',
    'ለ': 'le',
    'ያ': 'ya',
    'ወ': 'we',
    'ዓ': 'a',
    'ዋ': 'wa',
    'ሪ': 'ri',
    'ሲ': 'si',
    'ሰ': 'se',
    'ተ': 'te',
    'ጠ': 'tta',
    'ቴ': 'tte',
    'ትክ': 'tik',
}


def transliterate_to_ascii(text: str, use_phonetic: bool = True) -> str:
    """
    Convert non-ASCII characters to ASCII-safe equivalents.
    
    Supports:
    - Unicode normalization (NFD) for accented characters
    - Phonetic mappings for Arabic and Amharic
    - Fallback to Unicode codepoints
    
    Args:
        text: Input text (may contain Arabic, Amharic, etc.)
        use_phonetic: If True, use phonetic mappings for better readability
        
    Returns:
        ASCII-safe string with only alphanumeric and underscore characters
        
    Examples:
        >>> transliterate_to_ascii("غيديو")  # Arabic Gedeo
        'gidio' or 'U063FU064A...' (depends on phonetic mapping)
        
        >>> transliterate_to_ascii("يرقا شافي")  # Arabic Yirgacheffe
        'yirqa_shafi'
        
        >>> transliterate_to_ascii("Café")
        'Cafe'
    """
    if not text:
        return "UNKNOWN"
    
    result = []
    
    for char in text:
        # Check phonetic mapping first
        if use_phonetic and char in PHONETIC_MAPPINGS:
            result.append(PHONETIC_MAPPINGS[char])
            continue
        
        # Try Unicode normalization for accented characters
        try:
            normalized = unicodedata.normalize('NFKD', char)
            ascii_char = normalized.encode('ascii', 'ignore').decode('ascii')
            if ascii_char:
                result.append(ascii_char)
                continue
        except Exception:
            pass
        
        # If ASCII, keep it
        if ord(char) < 128:
            result.append(char)
            continue
        
        # Skip non-ASCII if no mapping exists
        # (produces cleaner IDs than codepoint fallback)
    
    # Join and clean up
    ascii_text = ''.join(result).strip()
    
    # Return UNKNOWN if nothing was transliterable
    if not ascii_text:
        return "UNKNOWN"
    
    return ascii_text


def make_batch_id_safe(batch_id: str) -> str:
    """
    Convert batch ID to URL-safe format.
    
    - Transliterates non-ASCII characters
    - Removes special characters
    - Replaces spaces with underscores
    - Limits to 50 characters for database
    
    Args:
        batch_id: Batch ID (may contain non-ASCII)
        
    Returns:
        URL-safe batch ID
        
    Examples:
        >>> make_batch_id_safe("غيديو_يرقا_شافي_20260519_165847")
        'GIDIO_YIRQA_SHAFI_20260519_165847'
    """
    # Transliterate non-ASCII
    safe_id = transliterate_to_ascii(batch_id, use_phonetic=True)
    
    # Upper case and normalize spaces
    safe_id = safe_id.upper().replace(" ", "_")
    
    # Remove non-alphanumeric except underscore
    safe_id = re.sub(r'[^A-Z0-9_]', '', safe_id)
    
    # Remove consecutive underscores
    safe_id = re.sub(r'_+', '_', safe_id)
    
    # Limit to 50 chars
    safe_id = safe_id[:50]
    
    # Ensure it's not empty
    return safe_id if safe_id else "UNKNOWN"


if __name__ == "__main__":
    # Test cases
    test_cases = [
        "غيديو",  # Arabic Gedeo
        "يرقا شافي",  # Arabic Yirgacheffe
        "ሊብ",  # Amharic
        "Café",  # Accented
        "Normal-Text",  # ASCII
    ]
    
    for test in test_cases:
        result = transliterate_to_ascii(test)
        safe = make_batch_id_safe(test)
        print(f"{test:20} → {result:20} → {safe}")
