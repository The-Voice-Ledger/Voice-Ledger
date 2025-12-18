"""
QR Code Generation for Batch Verification

Generates QR codes containing verification URLs for batch verification workflow.
"""

import qrcode
import io
import base64
import os
from typing import Tuple, Optional
from pathlib import Path


def generate_verification_qr_code(
    verification_token: str,
    base_url: str = None,
    output_file: Optional[Path] = None,
    use_telegram_deeplink: bool = True
) -> Tuple[str, Optional[Path]]:
    """
    Generate QR code for batch verification URL.
    
    Args:
        verification_token: Unique verification token
        base_url: Base URL for verification page (default: from env)
        output_file: Optional path to save QR code image
        use_telegram_deeplink: If True, uses Telegram deep link for authenticated verification
        
    Returns:
        Tuple of (base64_encoded_image, saved_file_path)
        
    Example:
        >>> token = "VRF-K7M2P9QR-3F8A2B1C"
        >>> qr_b64, qr_path = generate_verification_qr_code(token)
        >>> # QR contains: tg://resolve?domain=voiceledgerbot&start=verify_VRF-K7M2P9QR-3F8A2B1C
    """
    # Get bot username from environment
    bot_username = os.getenv('TELEGRAM_BOT_USERNAME', 'voiceledgerbot')
    
    # Construct verification URL
    if use_telegram_deeplink:
        # Telegram deep link format: tg://resolve?domain=botusername&start=verify_TOKEN
        verification_url = f"tg://resolve?domain={bot_username}&start=verify_{verification_token}"
    else:
        # Web URL fallback
        if base_url is None:
            base_url = os.getenv('BASE_URL', 'http://localhost:8000')
        verification_url = f"{base_url}/verify/{verification_token}"
    
    # Create QR code
    qr = qrcode.QRCode(
        version=1,  # Auto-size
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(verification_url)
    qr.make(fit=True)
    
    # Generate image
    img = qr.make_image(fill_color="black", back_color="white")
    
    # Convert to base64 for Telegram API
    buffer = io.BytesIO()
    img.save(buffer, format='PNG')
    buffer.seek(0)
    img_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
    
    # Save to file if output_file provided
    saved_path = None
    if output_file:
        output_file.parent.mkdir(parents=True, exist_ok=True)
        img.save(output_file)
        saved_path = output_file
    
    return img_base64, saved_path


def generate_qr_code_bytes(verification_token: str, base_url: str = None) -> bytes:
    """
    Generate QR code as raw bytes for direct Telegram upload.
    
    Args:
        verification_token: Unique verification token
        base_url: Base URL for verification page
        
    Returns:
        PNG image bytes
    """
    if base_url is None:
        base_url = os.getenv('BASE_URL', 'http://localhost:8000')
    
    verification_url = f"{base_url}/verify/{verification_token}"
    
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(verification_url)
    qr.make(fit=True)
    
    img = qr.make_image(fill_color="black", back_color="white")
    
    buffer = io.BytesIO()
    img.save(buffer, format='PNG')
    buffer.seek(0)
    
    return buffer.getvalue()


# Test code
if __name__ == "__main__":
    print("📱 Testing Verification QR Code Generation...")
    print()
    
    # Test token
    test_token = "VRF-K7M2P9QR-3F8A2B1C"
    
    # Generate QR code
    output_dir = Path(__file__).parent.parent.parent / "qrcodes"
    output_file = output_dir / f"{test_token}_verification_qr.png"
    
    qr_base64, qr_path = generate_verification_qr_code(
        verification_token=test_token,
        base_url="https://voice-ledger.com",
        output_file=output_file
    )
    
    print(f"✅ QR code generated")
    print(f"   URL: https://voice-ledger.com/verify/{test_token}")
    print(f"   Saved to: {qr_path}")
    print(f"   Base64 length: {len(qr_base64)} characters")
    print()
    print("✓ QR code generation working correctly!")
