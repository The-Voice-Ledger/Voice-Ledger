"""
Digital Product Passport - PDF Renderer

Converts a DPP JSON dict (from dpp_builder.build_dpp) into a branded,
professional PDF suitable for:
  - download via /api/dpp/batch/{batch_id}/pdf
  - Telegram delivery after batch commission
  - printing by cooperative managers

Uses fpdf2 (pure-Python, zero system dependencies → Railway-safe).
"""

import io
import base64
import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from fpdf import FPDF

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Colour palette (RGB tuples)
# ---------------------------------------------------------------------------
_GREEN = (34, 139, 34)      # Forest green - headings
_DARK = (33, 37, 41)        # Near-black - body text
_GREY = (108, 117, 125)     # Muted grey - labels / secondary
_LIGHT_BG = (248, 249, 250) # Light card background
_WHITE = (255, 255, 255)
_GOLD = (218, 165, 32)
_SILVER = (192, 192, 192)
_BRONZE = (205, 127, 50)
_RED = (220, 53, 69)


def _compliance_colour(level: str):
    """Return RGB tuple for a compliance level."""
    mapping = {
        "Gold": _GOLD,
        "Silver": _SILVER,
        "Bronze": _BRONZE,
        "Non-Compliant": _RED,
    }
    return mapping.get(level, _GREY)


class _DppPdf(FPDF):
    """Custom FPDF subclass with header / footer branding."""

    def __init__(self, dpp: Dict[str, Any]):
        super().__init__(orientation="P", unit="mm", format="A4")
        self._dpp = dpp
        self.set_auto_page_break(auto=True, margin=20)

    # -- page header -------------------------------------------------------
    def header(self):
        self.set_font("Helvetica", "B", 10)
        self.set_text_color(*_GREEN)
        self.cell(0, 6, "Voice Ledger - Digital Product Passport", ln=True, align="L")
        self.set_draw_color(*_GREEN)
        self.line(10, self.get_y(), 200, self.get_y())
        self.ln(4)

    # -- page footer -------------------------------------------------------
    def footer(self):
        self.set_y(-15)
        self.set_font("Helvetica", "I", 7)
        self.set_text_color(*_GREY)
        self.cell(0, 10, f"Page {self.page_no()}/{{nb}}", align="C")

    # -- helpers -----------------------------------------------------------
    def _section_title(self, title: str):
        self.ln(3)
        self.set_font("Helvetica", "B", 12)
        self.set_text_color(*_GREEN)
        self.cell(0, 8, title, ln=True)
        self.set_draw_color(*_GREEN)
        self.line(10, self.get_y(), 200, self.get_y())
        self.ln(2)

    def _label_value(self, label: str, value: Any, bold_value: bool = False):
        self.set_font("Helvetica", "", 9)
        self.set_text_color(*_GREY)
        self.cell(55, 6, f"{label}:", align="R")
        self.set_text_color(*_DARK)
        style = "B" if bold_value else ""
        self.set_font("Helvetica", style, 9)
        self.cell(0, 6, _safe(value), ln=True)

    def _card_start(self):
        """Draw a light-grey rounded card background."""
        self.set_fill_color(*_LIGHT_BG)
        # We'll just set the fill for multi_cell usage
        return True

    def _badge(self, text: str, colour):
        """Render a small coloured badge inline."""
        self.set_font("Helvetica", "B", 9)
        self.set_text_color(*_WHITE)
        self.set_fill_color(*colour)
        w = self.get_string_width(text) + 6
        x = self.get_x()
        y = self.get_y()
        self.rect(x, y, w, 6, style="F")
        self.set_xy(x + 1, y)
        self.cell(w - 2, 6, text)
        self.set_xy(x + w + 2, y)
        self.set_text_color(*_DARK)


def _safe(val: Any) -> str:
    """Convert value to a latin-1 safe printable string, handling None."""
    if val is None:
        return "N/A"
    s = str(val)
    # Replace common Unicode chars that Helvetica (latin-1) cannot render
    s = s.replace("\u2014", "-")   # em dash
    s = s.replace("\u2013", "-")   # en dash
    s = s.replace("\u2018", "'")   # left single quote
    s = s.replace("\u2019", "'")   # right single quote
    s = s.replace("\u201c", '"')   # left double quote
    s = s.replace("\u201d", '"')   # right double quote
    s = s.replace("\u2026", "...") # ellipsis
    s = s.replace("\u00b7", "-")   # middle dot
    # Fallback: drop anything still outside latin-1
    return s.encode("latin-1", errors="replace").decode("latin-1")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def render_dpp_pdf(dpp: Dict[str, Any]) -> bytes:
    """
    Render a DPP dict to a branded PDF.

    Args:
        dpp: Full DPP dictionary from ``build_dpp()``

    Returns:
        PDF file content as bytes
    """
    pdf = _DppPdf(dpp)
    pdf.alias_nb_pages()
    pdf.add_page()

    # ------------------------------------------------------------------
    # Title block
    # ------------------------------------------------------------------
    pdf.set_font("Helvetica", "B", 18)
    pdf.set_text_color(*_GREEN)
    pdf.cell(0, 12, "Digital Product Passport", ln=True, align="C")

    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(*_DARK)
    batch_id = dpp.get("batchId", "Unknown")
    pdf.cell(0, 6, f"Batch  {batch_id}", ln=True, align="C")

    issued = dpp.get("issuedAt", "")[:19].replace("T", " ")
    pdf.set_font("Helvetica", "I", 8)
    pdf.set_text_color(*_GREY)
    pdf.cell(0, 5, f"Generated {issued} UTC   |   Passport {dpp.get('passportId', '')}", ln=True, align="C")
    pdf.ln(4)

    # ------------------------------------------------------------------
    # 1. Product Information
    # ------------------------------------------------------------------
    prod = dpp.get("productInformation", {})
    pdf._section_title("Product Information")
    pdf._label_value("Product", prod.get("productName"), bold_value=True)
    pdf._label_value("Variety", prod.get("variety"))
    pdf._label_value("Processing", prod.get("processMethod"))
    pdf._label_value("Quantity", f"{prod.get('quantity', '?')} {prod.get('unit', 'kg')}")
    pdf._label_value("GTIN", prod.get("gtin"))

    # ------------------------------------------------------------------
    # 2. Traceability / Origin
    # ------------------------------------------------------------------
    trace = dpp.get("traceability", {})
    origin = trace.get("origin", {})
    farmer = origin.get("farmer", {})

    pdf._section_title("Traceability & Origin")
    pdf._label_value("Country", origin.get("country"))
    pdf._label_value("Region", origin.get("region"))
    pdf._label_value("Farm / Cooperative", origin.get("farmName"))
    pdf._label_value("Farmer", farmer.get("name"))
    pdf._label_value("Farmer DID", farmer.get("did"))
    pdf._label_value("GLN", farmer.get("gln"))

    # ------------------------------------------------------------------
    # 3. EUDR Compliance
    # ------------------------------------------------------------------
    eudr = dpp.get("eudrCompliance", {})
    pdf._section_title("EUDR Compliance")

    comp_status = eudr.get("complianceStatus", "UNKNOWN")
    comp_level = eudr.get("complianceLevel", "Unknown")

    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(*_GREY)
    pdf.cell(55, 6, "Compliance Level:", align="R")
    pdf._badge(comp_level, _compliance_colour(comp_level))
    pdf.ln(8)

    pdf._label_value("Status", comp_status)

    # Geolocation
    geo = eudr.get("geolocation", {})
    farm_loc = geo.get("farmLocation", {})
    coords = farm_loc.get("coordinates", {})
    if coords:
        pdf._label_value("Farm Latitude", coords.get("latitude"))
        pdf._label_value("Farm Longitude", coords.get("longitude"))
    pdf._label_value("GPS Source", farm_loc.get("source", farm_loc.get("status", "N/A")))
    verified_at = farm_loc.get("verifiedAt")
    if verified_at:
        pdf._label_value("Verified At", verified_at[:19].replace("T", " "))

    # Risk assessment
    risk = eudr.get("riskAssessment", {})
    pdf._label_value("Deforestation Risk", risk.get("deforestationRisk", "UNKNOWN"))
    defo_check = risk.get("deforestationCheck", {})
    if defo_check:
        pdf._label_value("Tree Cover Loss (ha)", defo_check.get("treeCoverLossHectares"))
        pdf._label_value("Compliant", defo_check.get("compliant"))
        pdf._label_value("Data Source", defo_check.get("dataSource"))
        pdf._label_value("Confidence", defo_check.get("confidence"))

    # ------------------------------------------------------------------
    # 4. DON Attestation (Chainlink)
    # ------------------------------------------------------------------
    don = dpp.get("donAttestation", {})
    if don and don.get("attestationExists"):
        pdf._section_title("Chainlink DON Attestation")
        pdf._label_value("Farm ID", don.get("farmId"))
        pdf._label_value("Risk Level", don.get("riskLabel"))
        pdf._label_value("EUDR Compliant", don.get("eudrCompliant"))
        pdf._label_value("Tree Loss (ha)", don.get("treeLossHectares"))
        don_coords = don.get("coordinates", {})
        if don_coords:
            pdf._label_value("DON Latitude", don_coords.get("latitude"))
            pdf._label_value("DON Longitude", don_coords.get("longitude"))
        verification = don.get("verification", {})
        pdf._label_value("Method", verification.get("method"))
        pdf._label_value("Data Source", verification.get("dataSource"))

    # ------------------------------------------------------------------
    # 5. Due Diligence
    # ------------------------------------------------------------------
    dd = dpp.get("dueDiligence", {})
    pdf._section_title("Due Diligence")
    pdf._label_value("EUDR Compliant", dd.get("eudrCompliant"))
    ra = dd.get("riskAssessment", {})
    pdf._label_value("Deforestation Risk", ra.get("deforestationRisk"))
    pdf._label_value("Assessment Date", ra.get("assessmentDate"))
    pdf._label_value("Methodology", ra.get("methodology"))
    pdf._label_value("DD Statement", dd.get("dueDiligenceStatement"))

    # ------------------------------------------------------------------
    # 6. Sustainability / Certifications
    # ------------------------------------------------------------------
    sust = dpp.get("sustainability", {})
    certs = sust.get("certifications", [])
    if certs:
        pdf._section_title("Certifications")
        for cert in certs:
            pdf._label_value("Type", cert.get("type"))
            pdf._label_value("Issuer", cert.get("issuer"))
            pdf._label_value("Issued", cert.get("issuedDate"))
            pdf._label_value("Expires", cert.get("expiryDate"))
            pdf.ln(1)

    carbon = sust.get("carbonFootprint", {})
    if carbon:
        pdf._section_title("Carbon Footprint")
        pdf._label_value("Value", f"{carbon.get('value')} {carbon.get('unit', '')}")
        pdf._label_value("Scope", carbon.get("scope"))

    # ------------------------------------------------------------------
    # 7. Blockchain Anchors
    # ------------------------------------------------------------------
    bc = dpp.get("blockchain", {})
    anchors = bc.get("anchors", [])
    if anchors:
        pdf._section_title("Blockchain Anchors")
        pdf._label_value("Network", bc.get("network"))
        if bc.get("tokenId"):
            pdf._label_value("Token ID", bc.get("tokenId"))
        for i, anchor in enumerate(anchors[:10], 1):  # cap at 10
            tx = anchor.get("transactionHash", "pending")
            pdf._label_value(f"Event {i}", tx[:42] + ("..." if len(str(tx)) > 42 else ""))

    # ------------------------------------------------------------------
    # 8. Supply Chain Events (timeline)
    # ------------------------------------------------------------------
    events = trace.get("events", [])
    if events:
        pdf._section_title("Supply Chain Events")
        for ev in events[:15]:  # cap at 15
            ts = (ev.get("timestamp") or "")[:19].replace("T", " ")
            pdf.set_font("Helvetica", "B", 8)
            pdf.set_text_color(*_DARK)
            pdf.cell(55, 5, ts, align="R")
            pdf.set_font("Helvetica", "", 8)
            pdf.cell(0, 5, f"  {ev.get('eventType', '')}  ({ev.get('bizStep', '')})", ln=True)

    # ------------------------------------------------------------------
    # 9. QR Code
    # ------------------------------------------------------------------
    qr = dpp.get("qrCode", {})
    qr_image_url = qr.get("imageUrl", "")
    if qr_image_url.startswith("data:image/png;base64,"):
        pdf._section_title("Scan for Live DPP")
        try:
            raw_b64 = qr_image_url.split(",", 1)[1]
            qr_bytes = base64.b64decode(raw_b64)
            # Write to a temp BytesIO so fpdf can read it
            img_stream = io.BytesIO(qr_bytes)
            img_stream.name = "qr.png"
            x_center = (210 - 40) / 2
            pdf.image(img_stream, x=x_center, w=40, h=40)
            pdf.ln(2)
            pdf.set_font("Helvetica", "", 7)
            pdf.set_text_color(*_GREY)
            dpp_url = qr.get("url", "")
            pdf.cell(0, 4, dpp_url, ln=True, align="C")
        except Exception as e:
            logger.warning("Could not embed QR image in PDF: %s", e)

    # ------------------------------------------------------------------
    # Footer note
    # ------------------------------------------------------------------
    pdf.ln(6)
    pdf.set_font("Helvetica", "I", 7)
    pdf.set_text_color(*_GREY)
    pdf.multi_cell(
        0, 4,
        "This Digital Product Passport was generated by Voice Ledger. "
        "Data is sourced from on-chain records, GPS-verified farm locations, "
        "and satellite deforestation analysis (Global Forest Watch). "
        "Verify authenticity by scanning the QR code above.",
        align="C",
    )

    return pdf.output()


# ---------------------------------------------------------------------------
# Convenience: build + render in one call
# ---------------------------------------------------------------------------

def build_and_render_pdf(batch_id: str) -> bytes:
    """
    Build the DPP for *batch_id* and render it to PDF bytes.

    This is a convenience wrapper that calls ``build_dpp`` followed by
    ``render_dpp_pdf``.  Callers that already have the DPP dict should
    call ``render_dpp_pdf`` directly.

    Raises:
        ValueError: if the batch is not found
    """
    from dpp.dpp_builder import build_dpp, load_batch_data

    batch = load_batch_data(batch_id)
    if not batch:
        raise ValueError(f"Batch {batch_id} not found")

    # Derive real compliance values
    deforestation_risk = "none"
    eudr_compliant = True
    if batch.farmer:
        f = batch.farmer
        risk = (f.deforestation_risk or "UNKNOWN").lower()
        deforestation_risk = risk if risk in ("low", "medium", "high", "unknown") else "none"
        eudr_compliant = (
            f.deforestation_compliant is True
            and f.latitude is not None
            and f.longitude is not None
        )

    dpp = build_dpp(
        batch_id=batch_id,
        deforestation_risk=deforestation_risk,
        eudr_compliant=eudr_compliant,
    )
    return render_dpp_pdf(dpp)
