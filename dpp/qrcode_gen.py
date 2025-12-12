"""
QR Code Generator for Digital Product Passports

Generates QR codes that link to DPP resolver URLs.
Consumers can scan these codes to access full traceability information.
"""

import io
import base64
from pathlib import Path
from typing import Optional

import qrcode
from qrcode.image.pil import PilImage


def generate_qr_code(
    batch_id: str,
    resolver_base_url: str = "https://dpp.voiceledger.io",
    output_file: Optional[Path] = None,
    size: int = 10,
    border: int = 2
) -> tuple[str, Optional[Path]]:
    """
    Generate QR code for a batch's DPP.
    
    Args:
        batch_id: Batch identifier
        resolver_base_url: Base URL for DPP resolver
        output_file: Optional path to save QR code image
        size: QR code box size (pixels per box)
        border: Border size (boxes)
    
    Returns:
        Tuple of (base64_encoded_image, output_file_path)
    """
    # Construct DPP URL
    dpp_url = f"{resolver_base_url}/dpp/{batch_id}"
    
    # Generate QR code
    qr = qrcode.QRCode(
        version=1,  # Auto-adjust size
        error_correction=qrcode.constants.ERROR_CORRECT_H,  # High error correction
        box_size=size,
        border=border,
    )
    
    qr.add_data(dpp_url)
    qr.make(fit=True)
    
    # Create image
    img = qr.make_image(fill_color="black", back_color="white")
    
    # Convert to base64 for embedding
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)
    base64_image = base64.b64encode(buffer.getvalue()).decode()
    
    # Save to file if requested
    saved_path = None
    if output_file:
        output_file.parent.mkdir(parents=True, exist_ok=True)
        img.save(output_file)
        saved_path = output_file
    
    return base64_image, saved_path


def generate_qr_code_svg(
    batch_id: str,
    resolver_base_url: str = "https://dpp.voiceledger.io",
    output_file: Optional[Path] = None
) -> str:
    """
    Generate SVG QR code (scalable vector graphics).
    
    Args:
        batch_id: Batch identifier
        resolver_base_url: Base URL for DPP resolver
        output_file: Optional path to save SVG file
    
    Returns:
        SVG string
    """
    import qrcode.image.svg
    
    dpp_url = f"{resolver_base_url}/dpp/{batch_id}"
    
    # Generate QR code as SVG
    factory = qrcode.image.svg.SvgPathImage
    qr = qrcode.QRCode(
        image_factory=factory,
        error_correction=qrcode.constants.ERROR_CORRECT_H
    )
    
    qr.add_data(dpp_url)
    qr.make(fit=True)
    
    img = qr.make_image()
    
    # Save to file if requested
    if output_file:
        output_file.parent.mkdir(parents=True, exist_ok=True)
        img.save(output_file)
    
    # Return SVG as string
    buffer = io.BytesIO()
    img.save(buffer)
    return buffer.getvalue().decode()


def create_labeled_qr_code(
    batch_id: str,
    product_name: str,
    resolver_base_url: str = "https://dpp.voiceledger.io",
    output_file: Optional[Path] = None
) -> Path:
    """
    Create QR code with product label overlay.
    
    Args:
        batch_id: Batch identifier
        product_name: Product name to display
        resolver_base_url: Base URL for DPP resolver
        output_file: Path to save labeled QR code
    
    Returns:
        Path to saved file
    """
    from PIL import Image, ImageDraw, ImageFont
    
    # Generate base QR code
    dpp_url = f"{resolver_base_url}/dpp/{batch_id}"
    
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=10,
        border=2,
    )
    qr.add_data(dpp_url)
    qr.make(fit=True)
    
    qr_img = qr.make_image(fill_color="black", back_color="white").convert("RGB")
    
    # Create new image with space for label
    qr_width, qr_height = qr_img.size
    label_height = 80
    total_height = qr_height + label_height
    
    # Create canvas
    labeled_img = Image.new("RGB", (qr_width, total_height), "white")
    
    # Paste QR code
    labeled_img.paste(qr_img, (0, 0, qr_width, qr_height))
    
    # Add text label
    draw = ImageDraw.Draw(labeled_img)
    
    try:
        # Try to use a nice font
        font_title = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 20)
        font_batch = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 14)
    except:
        # Fall back to default font
        font_title = ImageFont.load_default()
        font_batch = ImageFont.load_default()
    
    # Draw product name
    text_y = qr_height + 10
    draw.text((qr_width // 2, text_y), product_name, fill="black", 
              font=font_title, anchor="mt")
    
    # Draw batch ID
    batch_text = f"Batch: {batch_id}"
    draw.text((qr_width // 2, text_y + 30), batch_text, fill="gray", 
              font=font_batch, anchor="mt")
    
    # Draw instructions
    instructions = "Scan for full traceability"
    draw.text((qr_width // 2, text_y + 50), instructions, fill="gray", 
              font=font_batch, anchor="mt")
    
    # Save
    if output_file is None:
        output_dir = Path(__file__).parent / "qrcodes"
        output_dir.mkdir(parents=True, exist_ok=True)
        output_file = output_dir / f"{batch_id}_labeled_qr.png"
    
    output_file.parent.mkdir(parents=True, exist_ok=True)
    labeled_img.save(output_file)
    
    return output_file


def generate_batch_qr_codes(
    batches: list[tuple[str, str]],
    resolver_base_url: str = "https://dpp.voiceledger.io",
    output_dir: Optional[Path] = None
) -> list[Path]:
    """
    Generate QR codes for multiple batches.
    
    Args:
        batches: List of (batch_id, product_name) tuples
        resolver_base_url: Base URL for DPP resolver
        output_dir: Output directory for QR codes
    
    Returns:
        List of paths to generated QR codes
    """
    if output_dir is None:
        output_dir = Path(__file__).parent / "qrcodes"
    
    output_dir.mkdir(parents=True, exist_ok=True)
    
    generated_files = []
    
    for batch_id, product_name in batches:
        output_file = output_dir / f"{batch_id}_qr.png"
        base64_img, saved_path = generate_qr_code(
            batch_id=batch_id,
            resolver_base_url=resolver_base_url,
            output_file=output_file
        )
        
        if saved_path:
            generated_files.append(saved_path)
            print(f"✅ Generated QR code for {batch_id}: {saved_path}")
    
    return generated_files


# Demo/test code
if __name__ == "__main__":
    print("📱 Generating QR Codes for DPPs...")
    print()
    
    # Generate simple QR code
    batch_id = "BATCH-2025-001"
    print(f"🔲 Generating QR code for {batch_id}...")
    
    output_dir = Path(__file__).parent / "qrcodes"
    output_file = output_dir / f"{batch_id}_qr.png"
    
    base64_img, saved_path = generate_qr_code(
        batch_id=batch_id,
        resolver_base_url="https://dpp.voiceledger.io",
        output_file=output_file
    )
    
    print(f"✅ QR code saved to: {saved_path}")
    print(f"   URL: https://dpp.voiceledger.io/dpp/{batch_id}")
    print(f"   Base64 length: {len(base64_img)} characters")
    print()
    
    # Generate labeled QR code
    print("🏷️  Generating labeled QR code...")
    labeled_file = create_labeled_qr_code(
        batch_id=batch_id,
        product_name="Ethiopian Yirgacheffe",
        resolver_base_url="https://dpp.voiceledger.io",
        output_file=output_dir / f"{batch_id}_labeled_qr.png"
    )
    
    print(f"✅ Labeled QR code saved to: {labeled_file}")
    print()
    
    # Generate SVG version
    print("🎨 Generating SVG QR code...")
    svg_file = output_dir / f"{batch_id}_qr.svg"
    svg_content = generate_qr_code_svg(
        batch_id=batch_id,
        resolver_base_url="https://dpp.voiceledger.io",
        output_file=svg_file
    )
    
    print(f"✅ SVG QR code saved to: {svg_file}")
    print(f"   SVG size: {len(svg_content)} characters")
    print()
    
    print("🎉 QR code generation complete!")
    print("📍 Scan any QR code to access the Digital Product Passport")
