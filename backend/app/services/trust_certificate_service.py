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
    witness_count = getattr(listing, 'witness_count', 0) or 0

    # Safe strings — no injection risk in HTML
    safe_title    = (listing.title or "Property").replace("<", "&lt;").replace(">", "&gt;")
    safe_location = (listing.location or "Nigeria").replace("<", "&lt;").replace(">", "&gt;")
    safe_biz      = biz_name.replace("<", "&lt;").replace(">", "&gt;")
    safe_prop_type = (listing.property_type or "&#x2014;").replace("<", "&lt;").replace(">", "&gt;")

    # GPS maps line (pre-computed to avoid nested f-string)
    if listing.latitude and listing.longitude:
        gps_maps = (
            f'<div class="gps-link">View on Google Maps: '
            f'https://maps.google.com/?q={listing.latitude},{listing.longitude}</div>'
        )
    else:
        gps_maps = (
            '<div style="color:#94A3B8;font-size:11px;margin-top:4px">'
            'GPS coordinates not yet recorded</div>'
        )

    # Document rows (pre-computed to avoid nested f-string)
    docs_html = "".join([
        f'<table class="doc-row" cellpadding="0" cellspacing="0"><tr>'
        f'<td style="width:60%">{d[0]}</td>'
        f'<td style="width:15%;text-align:center;font-size:16px">'
        f'{"&#x2705;" if d[1] else "&#x274C;"}</td>'
        f'<td style="width:25%;text-align:right;'
        f'color:{"#10B981" if d[1] else "#94A3B8"};font-weight:bold">{d[2]}</td>'
        f'</tr></table>'
        for d in docs
    ])

    html = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8"/>
  <style>
    * {{ margin:0; padding:0; box-sizing:border-box; }}

    body {{
      font-family: Arial, Helvetica, sans-serif;
      background: #ffffff;
      color: #0A0F2C;
      font-size: 12px;
      line-height: 1.5;
    }}

    .page {{
      width: 210mm;
      min-height: 297mm;
      padding: 15mm 18mm;
      background: #ffffff;
    }}

    /* HEADER */
    .header-table {{
      width: 100%;
      border-bottom: 3px solid #0F172A;
      padding-bottom: 14px;
      margin-bottom: 20px;
    }}

    .wordmark {{
      font-family: Georgia, serif;
      font-size: 36px;
      font-weight: bold;
      color: #0F172A;
      letter-spacing: -1px;
    }}

    .wordmark-accent {{ color: #10B981; }}

    .tagline {{
      font-size: 9px;
      font-weight: bold;
      letter-spacing: 3px;
      text-transform: uppercase;
      color: #6B7280;
      margin-top: 3px;
    }}

    .cert-meta {{
      text-align: right;
      font-size: 10px;
      color: #6B7280;
      line-height: 1.8;
    }}

    /* SCORE HERO */
    .hero {{
      background: #0F172A;
      border-radius: 12px;
      padding: 24px 28px;
      margin-bottom: 20px;
      color: #ffffff;
    }}

    .hero-inner {{ width: 100%; }}

    .hero-title {{
      font-size: 10px;
      font-weight: bold;
      letter-spacing: 3px;
      text-transform: uppercase;
      color: rgba(255,255,255,0.5);
      margin-bottom: 6px;
    }}

    .hero-property {{
      font-size: 20px;
      font-weight: bold;
      color: #ffffff;
      margin-bottom: 4px;
    }}

    .hero-location {{
      font-size: 12px;
      color: rgba(255,255,255,0.5);
      margin-bottom: 10px;
    }}

    .grade-pill {{
      display: inline-block;
      padding: 4px 16px;
      border-radius: 99px;
      font-size: 10px;
      font-weight: bold;
      letter-spacing: 2px;
      text-transform: uppercase;
      background: {grade_color}33;
      color: {grade_color};
      border: 1px solid {grade_color}66;
    }}

    .score-box {{
      text-align: right;
      vertical-align: middle;
    }}

    .score-number {{
      font-size: 72px;
      font-weight: bold;
      color: {grade_color};
      line-height: 1;
      font-family: Georgia, serif;
    }}

    .score-denom {{
      font-size: 16px;
      color: rgba(255,255,255,0.3);
      font-weight: normal;
    }}

    .score-label {{
      font-size: 9px;
      letter-spacing: 2px;
      text-transform: uppercase;
      color: rgba(255,255,255,0.4);
      margin-top: 4px;
    }}

    /* SECTION TITLE */
    .section-title {{
      font-size: 9px;
      font-weight: bold;
      letter-spacing: 3px;
      text-transform: uppercase;
      color: #94A3B8;
      margin-bottom: 10px;
      margin-top: 18px;
      padding-bottom: 6px;
      border-bottom: 1px solid #E2E8F0;
    }}

    /* PROPERTY GRID */
    .prop-grid {{
      width: 100%;
      border-collapse: collapse;
      margin-bottom: 4px;
    }}

    .prop-cell {{
      width: 25%;
      padding: 10px 12px;
      background: #F8FAFC;
      border: 1px solid #E2E8F0;
      vertical-align: top;
    }}

    .prop-label {{
      font-size: 8px;
      font-weight: bold;
      letter-spacing: 2px;
      text-transform: uppercase;
      color: #94A3B8;
      margin-bottom: 4px;
    }}

    .prop-value {{
      font-size: 13px;
      font-weight: bold;
      color: #0A0F2C;
    }}

    /* BREAKDOWN TABLE */
    .breakdown {{
      width: 100%;
      border-collapse: collapse;
      font-size: 12px;
    }}

    .breakdown th {{
      background: #F1F5F9;
      padding: 8px 12px;
      text-align: left;
      font-size: 9px;
      font-weight: bold;
      letter-spacing: 1px;
      text-transform: uppercase;
      color: #64748B;
      border: 1px solid #E2E8F0;
    }}

    .breakdown td {{
      padding: 10px 12px;
      border: 1px solid #E2E8F0;
      vertical-align: middle;
    }}

    .breakdown tr:last-child {{
      background: #F8FAFC;
      font-weight: bold;
    }}

    .status-verified {{
      color: #10B981;
      font-weight: bold;
    }}

    .status-unverified {{ color: #94A3B8; }}

    .pts-badge {{
      display: inline-block;
      padding: 2px 10px;
      border-radius: 99px;
      font-size: 11px;
      font-weight: bold;
    }}

    .pts-earned {{ background: #F0FDF4; color: #10B981; }}
    .pts-zero   {{ background: #F8FAFC; color: #94A3B8; }}

    /* GPS BOX */
    .gps-box {{
      background: #F0FDF4;
      border: 1px solid #BBF7D0;
      border-left: 4px solid #10B981;
      border-radius: 8px;
      padding: 14px 16px;
      margin-top: 4px;
    }}

    .gps-label {{
      font-size: 9px;
      font-weight: bold;
      letter-spacing: 2px;
      text-transform: uppercase;
      color: #065F46;
      margin-bottom: 6px;
    }}

    .gps-coords {{
      font-family: 'Courier New', monospace;
      font-size: 14px;
      font-weight: bold;
      color: #065F46;
      letter-spacing: 1px;
    }}

    .gps-link {{
      font-size: 11px;
      color: #10B981;
      margin-top: 6px;
    }}

    /* DOCUMENTS */
    .doc-row {{
      width: 100%;
      border-collapse: collapse;
      margin-bottom: 4px;
    }}

    .doc-row td {{
      padding: 9px 14px;
      border: 1px solid #E2E8F0;
      font-size: 12px;
    }}

    /* FOOTER */
    .footer-table {{
      width: 100%;
      border-top: 2px solid #0F172A;
      padding-top: 16px;
      margin-top: 28px;
    }}

    .footer-left {{
      font-size: 10px;
      color: #6B7280;
      line-height: 1.8;
      vertical-align: bottom;
    }}

    .seal {{
      width: 90px;
      height: 90px;
      border: 3px solid {grade_color};
      border-radius: 50%;
      text-align: center;
      vertical-align: middle;
      padding: 10px;
    }}

    .seal-text {{
      font-size: 8px;
      font-weight: bold;
      text-transform: uppercase;
      letter-spacing: 1px;
      color: {grade_color};
      line-height: 1.6;
    }}

    .seal-check {{
      font-size: 20px;
      color: {grade_color};
      display: block;
      margin: 2px 0;
    }}

    /* DISCLAIMER */
    .disclaimer {{
      background: #FFF7ED;
      border: 1px solid #FED7AA;
      border-radius: 6px;
      padding: 10px 14px;
      font-size: 9px;
      color: #92400E;
      line-height: 1.6;
      margin-top: 14px;
    }}

    /* WATERMARK BAND */
    .watermark-band {{
      background: {grade_color}11;
      border-top: 1px solid {grade_color}33;
      border-bottom: 1px solid {grade_color}33;
      padding: 6px 0;
      text-align: center;
      margin: 16px 0;
    }}

    .watermark-text {{
      font-size: 9px;
      font-weight: bold;
      letter-spacing: 4px;
      text-transform: uppercase;
      color: {grade_color};
    }}
  </style>
</head>
<body>
<div class="page">

  <!-- HEADER -->
  <table class="header-table" cellpadding="0" cellspacing="0">
    <tr>
      <td>
        <div class="wordmark">
          Est<span class="wordmark-accent">8</span>Go
        </div>
        <div class="tagline">Truth as a Service</div>
      </td>
      <td class="cert-meta">
        <strong>Certificate No.</strong> {cert_number}<br/>
        <strong>Issued:</strong> {issue_date}<br/>
        <strong>Valid for:</strong> 90 days from issue date
      </td>
    </tr>
  </table>

  <!-- SCORE HERO -->
  <div class="hero">
    <table class="hero-inner" cellpadding="0" cellspacing="0">
      <tr>
        <td style="vertical-align:middle;width:70%">
          <div class="hero-title">Est8Go Trust Certificate</div>
          <div class="hero-property">{safe_title}</div>
          <div class="hero-location">{safe_location}</div>
          <div class="grade-pill">{grade_display} Grade</div>
        </td>
        <td class="score-box" style="width:30%">
          <div class="score-number">
            {trust_score}<span class="score-denom">/100</span>
          </div>
          <div class="score-label">Trust Score</div>
        </td>
      </tr>
    </table>
  </div>

  <!-- WATERMARK BAND -->
  <div class="watermark-band">
    <span class="watermark-text">
      Verified by Est8Go &nbsp;&middot;&nbsp; {grade_display} Grade &nbsp;&middot;&nbsp;
      Certificate {cert_number}
    </span>
  </div>

  <!-- PROPERTY DETAILS -->
  <div class="section-title">Property Details</div>
  <table class="prop-grid" cellpadding="0" cellspacing="0">
    <tr>
      <td class="prop-cell">
        <div class="prop-label">Property Type</div>
        <div class="prop-value">{safe_prop_type}</div>
      </td>
      <td class="prop-cell">
        <div class="prop-label">Asking Price</div>
        <div class="prop-value">{price_fmt}</div>
      </td>
      <td class="prop-cell">
        <div class="prop-label">Location</div>
        <div class="prop-value">{safe_location}</div>
      </td>
      <td class="prop-cell">
        <div class="prop-label">Listed By</div>
        <div class="prop-value">{safe_biz}</div>
      </td>
    </tr>
  </table>

  <!-- TRUST BREAKDOWN -->
  <div class="section-title">Trust Score Breakdown</div>
  <table class="breakdown" cellpadding="0" cellspacing="0">
    <thead>
      <tr>
        <th>Verification Component</th>
        <th>Status</th>
        <th>Points Earned</th>
        <th>Maximum</th>
      </tr>
    </thead>
    <tbody>
      <tr>
        <td>GPS Site Verification</td>
        <td class="{'status-verified' if gps_score > 0 else 'status-unverified'}">
          {'&#10003; Location verified on-site' if gps_score > 0 else '&#10007; Not yet verified'}
        </td>
        <td>
          <span class="pts-badge {'pts-earned' if gps_score > 0 else 'pts-zero'}">
            +{gps_score} pts
          </span>
        </td>
        <td style="color:#94A3B8;text-align:center">30</td>
      </tr>
      <tr>
        <td>Automated Media Audit</td>
        <td class="{'status-verified' if ai_score > 0 else 'status-unverified'}">
          {'&#10003; Images passed audit' if ai_score > 0 else '&#10007; Audit not completed'}
        </td>
        <td>
          <span class="pts-badge {'pts-earned' if ai_score > 0 else 'pts-zero'}">
            +{ai_score} pts
          </span>
        </td>
        <td style="color:#94A3B8;text-align:center">20</td>
      </tr>
      <tr>
        <td>Document Verification</td>
        <td class="{'status-verified' if doc_score > 0 else 'status-unverified'}">
          {'&#10003; Documents verified' if doc_score > 0 else '&#10007; No documents uploaded'}
        </td>
        <td>
          <span class="pts-badge {'pts-earned' if doc_score > 0 else 'pts-zero'}">
            +{doc_score} pts
          </span>
        </td>
        <td style="color:#94A3B8;text-align:center">40</td>
      </tr>
      <tr>
        <td>Witness Attestation</td>
        <td class="{'status-verified' if witness_score > 0 else 'status-unverified'}">
          {witness_count} witness{'es' if witness_count != 1 else ''} recorded
        </td>
        <td>
          <span class="pts-badge {'pts-earned' if witness_score > 0 else 'pts-zero'}">
            +{witness_score} pts
          </span>
        </td>
        <td style="color:#94A3B8;text-align:center">10</td>
      </tr>
      <tr>
        <td><strong>TOTAL TRUST SCORE</strong></td>
        <td></td>
        <td>
          <strong style="font-size:16px;color:{grade_color}">
            {trust_score} / 100
          </strong>
        </td>
        <td style="text-align:center">
          <strong style="color:{grade_color}">{grade_display}</strong>
        </td>
      </tr>
    </tbody>
  </table>

  <!-- GPS VERIFICATION -->
  <div class="section-title">GPS Verification Record</div>
  <div class="gps-box">
    <div class="gps-label">Recorded Coordinates</div>
    <div class="gps-coords">{gps_text}</div>
    {gps_maps}
  </div>

  <!-- DOCUMENTS -->
  <div class="section-title">Documents on Record</div>
  {docs_html}

  <!-- FOOTER -->
  <table class="footer-table" cellpadding="0" cellspacing="0">
    <tr>
      <td class="footer-left">
        <strong style="font-size:12px;color:#0A0F2C">
          Est8Go Service Limited
        </strong><br/>
        Trust Infrastructure for African Real Estate<br/>
        Certificate Reference: {cert_number}<br/>
        Verify authenticity: est8go-api.onrender.com<br/>
        This certificate is valid for 90 days from issue date.
      </td>
      <td style="text-align:right;vertical-align:middle;width:110px">
        <table cellpadding="0" cellspacing="0" style="margin-left:auto">
          <tr>
            <td>
              <div class="seal">
                <div class="seal-text">
                  EST8GO<br/>
                  <span class="seal-check">&#10003;</span>
                  VERIFIED<br/>
                  {grade_display.upper()}
                </div>
              </div>
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>

  <!-- DISCLAIMER -->
  <div class="disclaimer">
    <strong>Important Disclaimer:</strong>
    This certificate reflects the property trust score
    at the time of generation, based on GPS site
    verification, automated media audit, legal document
    verification, and witness attestation recorded on the
    Est8Go platform. Est8Go Service Limited does not
    guarantee title, ownership, or freedom from
    encumbrances. Independent legal verification by a
    qualified Nigerian solicitor is strongly recommended
    before any property transaction.
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
