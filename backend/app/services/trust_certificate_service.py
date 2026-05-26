"""
EST8GO TRUST CERTIFICATE GENERATOR
====================================
Generates a professional PDF trust certificate
for verified property listings.
Designed for diaspora buyers who need printable
proof before sending money home.

Cost: 20 Est8 Credits per certificate
"""

import logging
from datetime import datetime

logger = logging.getLogger(__name__)


def generate_trust_certificate(
    listing: object,
    tenant: object,
    company_profile: object = None,
) -> bytes:
    """
    Generates a PDF trust certificate for a listing.
    Returns PDF bytes.
    """

    trust_score = listing.trust_score or 0
    trust_grade = listing.trust_grade or "Unrated"

    # Trust grade colours
    grade_colors = {
        "Emerald": "#10B981",
        "Gold":    "#F59E0B",
        "Silver":  "#94A3B8",
        "Bronze":  "#CD7F32",
        "Unrated": "#6B7280",
    }
    # DB stores lowercase; normalise for display
    grade_display = trust_grade.title()
    grade_color = grade_colors.get(grade_display, "#6B7280")

    # Format GPS coordinates
    gps_text = "Not verified"
    if listing.latitude and listing.longitude:
        gps_text = f"{listing.latitude:.6f}, {listing.longitude:.6f}"

    # Format document status
    docs = []
    if getattr(listing, 'cof_uploaded', False):
        docs.append(("Certificate of Occupancy", True, "+15 pts"))
    if getattr(listing, 'deed_uploaded', False):
        docs.append(("Deed of Assignment", True, "+10 pts"))
    if getattr(listing, 'survey_uploaded', False):
        docs.append(("Survey Plan", True, "+10 pts"))
    if not docs:
        docs.append(("No documents uploaded", False, "+0 pts"))

    # Format price
    price = listing.price or 0
    if price >= 1_000_000_000:
        price_fmt = f"&#x20A6;{price/1_000_000_000:.1f}B"
    elif price >= 1_000_000:
        price_fmt = f"&#x20A6;{price/1_000_000:.1f}M"
    elif price >= 1_000:
        price_fmt = f"&#x20A6;{price/1_000:.0f}K"
    else:
        price_fmt = f"&#x20A6;{price:,}"

    biz_name = (
        company_profile.company_name if company_profile
        else tenant.business_name if tenant
        else "Est8Go Verified Agent"
    )

    cert_number = f"EST8-{listing.id:06d}-{datetime.utcnow().strftime('%Y%m')}"
    issue_date = datetime.utcnow().strftime("%d %B %Y")

    # Score breakdown
    gps_score = 30 if (listing.latitude and listing.longitude) else 0
    ai_score = 20 if getattr(listing, 'ai_verified_real', False) else 0
    doc_score = getattr(listing, 'document_score', 0) or 0
    witness_score = min((getattr(listing, 'witness_count', 0) or 0) * 5, 10)

    # Safe title / location (no f-string injection risk — these go into static HTML)
    safe_title = (listing.title or "Property").replace("<", "&lt;").replace(">", "&gt;")
    safe_location = (listing.location or "Nigeria").replace("<", "&lt;").replace(">", "&gt;")
    safe_biz = biz_name.replace("<", "&lt;").replace(">", "&gt;")
    safe_prop_type = (listing.property_type or "—").replace("<", "&lt;").replace(">", "&gt;")

    gps_verified_class = "verified" if gps_score > 0 else "unverified"
    gps_verified_text = "&#10003; Verified" if gps_score > 0 else "&#10007; Not verified"
    ai_verified_class = "verified" if ai_score > 0 else "unverified"
    ai_verified_text = "&#10003; Passed" if ai_score > 0 else "&#10007; Not audited"
    doc_verified_class = "verified" if doc_score > 0 else "unverified"
    doc_verified_text = "&#10003; Documents verified" if doc_score > 0 else "&#10007; No documents"
    witness_count = getattr(listing, 'witness_count', 0) or 0
    witness_verified_class = "verified" if witness_score > 0 else "unverified"

    gps_badge_class = "" if gps_score == 0 else ""
    ai_badge_zero = " zero" if ai_score == 0 else ""
    doc_badge_zero = " zero" if doc_score == 0 else ""
    witness_badge_zero = " zero" if witness_score == 0 else ""
    gps_badge_zero = " zero" if gps_score == 0 else ""

    maps_link = ""
    if listing.latitude and listing.longitude:
        maps_link = f"""<div style="margin-top:8px">
      <a style="font-size:11px;color:#10B981;font-weight:600"
         href="https://maps.google.com/?q={listing.latitude},{listing.longitude}">
        View on Google Maps &#x2192;
      </a>
    </div>"""

    docs_html = "".join([
        f"""<div class="doc-row">
      <span class="doc-name">{d[0]}</span>
      <span class="doc-check">{"&#x2705;" if d[1] else "&#x274C;"}</span>
      <span style="font-size:11px;color:{"#10B981" if d[1] else "#94A3B8"}">{d[2]}</span>
    </div>"""
        for d in docs
    ])

    html = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8"/>
  <style>
    * {{ margin: 0; padding: 0; box-sizing: border-box; }}

    body {{
      font-family: Arial, sans-serif;
      background: #ffffff;
      color: #0A0F2C;
      padding: 0;
    }}

    .page {{
      width: 210mm;
      min-height: 297mm;
      padding: 20mm 20mm;
      background: #ffffff;
      position: relative;
    }}

    .header {{
      display: flex;
      justify-content: space-between;
      align-items: flex-start;
      padding-bottom: 20px;
      border-bottom: 3px solid #0F172A;
      margin-bottom: 24px;
    }}

    .wordmark {{
      font-size: 32px;
      font-weight: 800;
      letter-spacing: -1px;
      color: #0F172A;
    }}

    .wordmark span {{ color: #10B981; }}

    .tagline {{
      font-size: 10px;
      font-weight: 600;
      letter-spacing: 0.2em;
      text-transform: uppercase;
      color: #6B7280;
      margin-top: 4px;
    }}

    .cert-info {{ text-align: right; }}

    .cert-number {{
      font-size: 11px;
      font-weight: 700;
      color: #6B7280;
      letter-spacing: 0.1em;
    }}

    .cert-date {{
      font-size: 11px;
      color: #6B7280;
      margin-top: 4px;
    }}

    .score-hero {{
      background: #0F172A;
      border-radius: 16px;
      padding: 28px 32px;
      margin-bottom: 24px;
      display: flex;
      align-items: center;
      justify-content: space-between;
    }}

    .score-left h2 {{
      font-size: 13px;
      font-weight: 700;
      color: rgba(255,255,255,0.6);
      text-transform: uppercase;
      letter-spacing: 0.15em;
      margin-bottom: 8px;
    }}

    .score-left h1 {{
      font-size: 20px;
      font-weight: 800;
      color: #ffffff;
      line-height: 1.2;
    }}

    .score-right {{ text-align: center; }}

    .score-number {{
      font-size: 64px;
      font-weight: 800;
      color: {grade_color};
      line-height: 1;
    }}

    .score-label {{
      font-size: 11px;
      font-weight: 700;
      color: rgba(255,255,255,0.5);
      text-transform: uppercase;
      letter-spacing: 0.1em;
      margin-top: 4px;
    }}

    .grade-badge {{
      display: inline-block;
      background: {grade_color}22;
      color: {grade_color};
      font-size: 12px;
      font-weight: 700;
      padding: 4px 14px;
      border-radius: 99px;
      border: 1px solid {grade_color}44;
      margin-top: 8px;
      text-transform: uppercase;
      letter-spacing: 0.1em;
    }}

    .section-title {{
      font-size: 10px;
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: 0.15em;
      color: #6B7280;
      margin-bottom: 12px;
    }}

    .property-grid {{
      display: flex;
      flex-wrap: wrap;
      gap: 12px;
      margin-bottom: 24px;
    }}

    .prop-field {{
      background: #F8FAFC;
      border: 1px solid #E2E8F0;
      border-radius: 10px;
      padding: 12px 14px;
      width: calc(50% - 6px);
    }}

    .prop-field-label {{
      font-size: 9px;
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: 0.12em;
      color: #94A3B8;
      margin-bottom: 4px;
    }}

    .prop-field-value {{
      font-size: 13px;
      font-weight: 600;
      color: #0A0F2C;
    }}

    .breakdown-table {{
      width: 100%;
      border-collapse: collapse;
      margin-bottom: 24px;
    }}

    .breakdown-table th {{
      font-size: 9px;
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: 0.12em;
      color: #94A3B8;
      text-align: left;
      padding: 8px 12px;
      background: #F8FAFC;
      border: 1px solid #E2E8F0;
    }}

    .breakdown-table td {{
      padding: 10px 12px;
      border: 1px solid #E2E8F0;
      font-size: 12px;
      color: #0A0F2C;
    }}

    .verified {{ color: #10B981; font-weight: 600; }}
    .unverified {{ color: #94A3B8; }}

    .points-badge {{
      display: inline-block;
      background: #F0FDF4;
      color: #10B981;
      font-size: 11px;
      font-weight: 700;
      padding: 2px 10px;
      border-radius: 99px;
    }}

    .points-badge.zero {{
      background: #F8FAFC;
      color: #94A3B8;
    }}

    .doc-row {{
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 10px 14px;
      border: 1px solid #E2E8F0;
      border-radius: 8px;
      margin-bottom: 6px;
    }}

    .doc-name {{ font-size: 12px; font-weight: 500; }}
    .doc-check {{ font-size: 14px; }}

    .gps-box {{
      background: #F0FDF4;
      border: 1px solid #BBF7D0;
      border-radius: 10px;
      padding: 14px;
      margin-bottom: 24px;
    }}

    .gps-coords {{
      font-family: 'Courier New', monospace;
      font-size: 13px;
      font-weight: 600;
      color: #065F46;
    }}

    .footer {{
      border-top: 2px solid #0F172A;
      padding-top: 16px;
      margin-top: 32px;
      display: flex;
      justify-content: space-between;
      align-items: flex-end;
    }}

    .footer-left {{
      font-size: 10px;
      color: #6B7280;
      line-height: 1.6;
    }}

    .seal {{
      width: 80px;
      height: 80px;
      border: 3px solid #10B981;
      border-radius: 50%;
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      text-align: center;
      padding: 8px;
    }}

    .seal-text {{
      font-size: 7px;
      font-weight: 800;
      text-transform: uppercase;
      letter-spacing: 0.05em;
      color: #10B981;
      line-height: 1.4;
    }}

    .disclaimer {{
      background: #FFF7ED;
      border: 1px solid #FED7AA;
      border-radius: 8px;
      padding: 10px 14px;
      font-size: 9px;
      color: #92400E;
      line-height: 1.5;
      margin-top: 16px;
    }}
  </style>
</head>
<body>
<div class="page">

  <div class="header">
    <div>
      <div class="wordmark">Est<span>8</span>Go</div>
      <div class="tagline">Truth as a Service</div>
    </div>
    <div class="cert-info">
      <div class="cert-number">Certificate No. {cert_number}</div>
      <div class="cert-date">Issued: {issue_date}</div>
      <div class="cert-date">Valid for 90 days</div>
    </div>
  </div>

  <div class="score-hero">
    <div class="score-left">
      <h2>Est8Go Trust Certificate</h2>
      <h1>{safe_title}</h1>
      <div style="font-size:12px;color:rgba(255,255,255,0.5);margin-top:6px">{safe_location}</div>
      <div class="grade-badge">{grade_display} Grade</div>
    </div>
    <div class="score-right">
      <div class="score-number">{trust_score}</div>
      <div class="score-label">Trust Score</div>
      <div style="font-size:10px;color:rgba(255,255,255,0.4);margin-top:4px">out of 100</div>
    </div>
  </div>

  <div class="section-title">Property Details</div>
  <div class="property-grid">
    <div class="prop-field">
      <div class="prop-field-label">Property Type</div>
      <div class="prop-field-value">{safe_prop_type}</div>
    </div>
    <div class="prop-field">
      <div class="prop-field-label">Asking Price</div>
      <div class="prop-field-value">{price_fmt}</div>
    </div>
    <div class="prop-field">
      <div class="prop-field-label">Location</div>
      <div class="prop-field-value">{safe_location}</div>
    </div>
    <div class="prop-field">
      <div class="prop-field-label">Listed By</div>
      <div class="prop-field-value">{safe_biz}</div>
    </div>
  </div>

  <div class="section-title">Trust Score Breakdown</div>
  <table class="breakdown-table">
    <thead>
      <tr>
        <th>Verification Component</th>
        <th>Status</th>
        <th>Points</th>
        <th>Max</th>
      </tr>
    </thead>
    <tbody>
      <tr>
        <td>GPS Site Verification</td>
        <td class="{gps_verified_class}">{gps_verified_text}</td>
        <td><span class="points-badge{gps_badge_zero}">+{gps_score}</span></td>
        <td style="color:#94A3B8">30</td>
      </tr>
      <tr>
        <td>Automated Media Audit</td>
        <td class="{ai_verified_class}">{ai_verified_text}</td>
        <td><span class="points-badge{ai_badge_zero}">+{ai_score}</span></td>
        <td style="color:#94A3B8">20</td>
      </tr>
      <tr>
        <td>Document Verification</td>
        <td class="{doc_verified_class}">{doc_verified_text}</td>
        <td><span class="points-badge{doc_badge_zero}">+{doc_score}</span></td>
        <td style="color:#94A3B8">40</td>
      </tr>
      <tr>
        <td>Witness Attestation</td>
        <td class="{witness_verified_class}">{witness_count} witnesses recorded</td>
        <td><span class="points-badge{witness_badge_zero}">+{witness_score}</span></td>
        <td style="color:#94A3B8">10</td>
      </tr>
      <tr style="background:#F8FAFC;font-weight:700">
        <td><strong>Total Trust Score</strong></td>
        <td></td>
        <td>
          <span style="font-size:14px;font-weight:800;color:{grade_color}">
            {trust_score}/100
          </span>
        </td>
        <td style="color:#94A3B8">100</td>
      </tr>
    </tbody>
  </table>

  <div class="section-title">GPS Verification</div>
  <div class="gps-box">
    <div style="font-size:10px;font-weight:700;text-transform:uppercase;
                letter-spacing:0.1em;color:#065F46;margin-bottom:6px">
      Recorded Coordinates
    </div>
    <div class="gps-coords">{gps_text}</div>
    {maps_link}
  </div>

  <div class="section-title">Documents Verified</div>
  <div style="margin-bottom:24px">
    {docs_html}
  </div>

  <div class="footer">
    <div class="footer-left">
      <strong>Est8Go Service Limited</strong><br/>
      Trust Infrastructure for African Real Estate<br/>
      Certificate: {cert_number}<br/>
      Verify online: est8go-api.onrender.com<br/>
      This certificate is valid for 90 days from issue date.
    </div>
    <div class="seal">
      <div class="seal-text">
        EST8GO<br/>
        VERIFIED<br/>
        &#10003;<br/>
        {grade_display.upper()}
      </div>
    </div>
  </div>

  <div class="disclaimer">
    <strong>Important:</strong> This certificate reflects the trust score at the time of
    generation based on GPS verification, automated media audit, document verification,
    and witness attestation. Est8Go Service Limited does not guarantee title or ownership.
    Independent legal verification is always recommended before any property transaction.
  </div>

</div>
</body>
</html>"""

    try:
        from weasyprint import HTML
        document = HTML(string=html)
        pdf_bytes = document.write_pdf()
        return pdf_bytes
    except ImportError:
        logger.error("WeasyPrint not installed")
        raise RuntimeError(
            "PDF generation unavailable. "
            "Contact support."
        )
    except Exception as e:
        logger.error(f"PDF generation failed: {e}")
        raise
