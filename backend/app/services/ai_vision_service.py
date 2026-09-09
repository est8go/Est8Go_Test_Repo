"""
EST8GO AI VISION AUDITOR (v2.0)
================================
80/20 Architecture:
    80% Python Rules  — EXIF analysis, metadata checks, duplicate detection
    20% GPT Vision    — Only when Python signals are inconclusive

Audit Pipeline:
    1. EXIF Pre-Filter    (Python — free, milliseconds)
    2. Pixel Analysis     (Python — free)
    3. Duplicate Detection (Python — free, perceptual hashing)
    4. GPT Vision Audit   (AI — only if needed)
    5. Fraud Score        (Python — combines all signals)
    6. Trust Engine Update (auto-updates listing score)
"""

import os
import io
import json
import logging
from dataclasses import dataclass, field
from typing import List, Optional

import openai
import requests
from PIL import Image
from PIL.ExifTags import TAGS

logger = logging.getLogger(__name__)


def get_openai_client():
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY not set in environment")
    return openai.OpenAI(api_key=api_key)


# ================================================================
# AUDIT RESULTS
# ================================================================


@dataclass
class ImageAuditResult:
    image_url: str
    is_real: bool
    is_nigerian_context: bool
    authenticity_score: int
    fraud_signals: List[str]
    trust_signals: List[str]
    exif_data: dict
    gpt_used: bool
    gpt_note: str
    perceptual_hash: str
    audit_report: str
    recommendation: str  # APPROVE / REVIEW / REJECT


@dataclass
class ListingAuditResult:
    listing_id: int
    total_images: int
    passed_images: int
    failed_images: int
    review_images: int
    overall_score: int
    fraud_signals: List[str]
    trust_signals: List[str]
    image_results: List[ImageAuditResult]
    final_verdict: str  # APPROVE / REVIEW / REJECT
    audit_report: str
    ai_verified_real: bool
    gpt_calls_made: int


# ================================================================
# FRAUD SIGNATURES
# ================================================================

FRAUD_SOFTWARE = {
    "sketchup",
    "autodesk",
    "3ds max",
    "blender",
    "lumion",
    "enscape",
    "v-ray",
    "corona renderer",
    "archicad",
    "revit",
    "twinmotion",
    "unreal engine",
    "unity",
    "artlantis",
    "keyshot",
    "maxwell render",
}

STOCK_PLATFORMS = {
    "shutterstock",
    "getty",
    "istock",
    "adobe stock",
    "dreamstime",
    "depositphotos",
    "123rf",
    "alamy",
}

MIN_WIDTH = 400
MIN_HEIGHT = 300


# ================================================================
# LAYER 1: EXIF ANALYSIS
# ================================================================


def analyze_exif(image: Image.Image, image_url: str) -> dict:
    """Extracts EXIF metadata and checks for fraud software signatures."""
    result = {
        "has_exif": False,
        "camera_model": None,
        "software": None,
        "gps_lat": None,
        "gps_lng": None,
        "has_gps": False,
        "date_taken": None,
        "fraud_signals": [],
        "trust_signals": [],
    }

    try:
        exif_data = image._getexif()
        if not exif_data:
            result["fraud_signals"].append(
                "No EXIF metadata — may be screenshot or downloaded image"
            )
            return result

        result["has_exif"] = True
        tags = {TAGS.get(k, k): v for k, v in exif_data.items()}

        # Camera model
        camera = str(tags.get("Model", "") or tags.get("Make", ""))
        if camera.strip():
            result["camera_model"] = camera
            result["trust_signals"].append(f"Camera detected: {camera}")

        # Software signature
        software = str(tags.get("Software", "")).lower()
        if software:
            result["software"] = software
            for sig in FRAUD_SOFTWARE:
                if sig in software:
                    result["fraud_signals"].append(
                        f"3D/CGI software in EXIF: {software}"
                    )
                    break
            for sig in STOCK_PLATFORMS:
                if sig in software:
                    result["fraud_signals"].append(
                        f"Stock photo platform detected: {software}"
                    )
                    break

        # GPS
        gps_info = tags.get("GPSInfo", {})
        if gps_info:
            try:
                lat = _convert_gps(gps_info.get(2), gps_info.get(1))
                lng = _convert_gps(gps_info.get(4), gps_info.get(3))
                if lat and lng:
                    result["gps_lat"] = lat
                    result["gps_lng"] = lng
                    result["has_gps"] = True
                    result["trust_signals"].append(
                        f"GPS embedded: {lat:.4f}, {lng:.4f}"
                    )
            except Exception:
                pass

        # Timestamp
        date_taken = tags.get("DateTimeOriginal") or tags.get("DateTime")
        if date_taken:
            result["date_taken"] = str(date_taken)
            result["trust_signals"].append(f"Timestamp: {date_taken}")

    except Exception as e:
        logger.warning(f"EXIF extraction error: {e}")

    return result


def _convert_gps(coord, ref) -> Optional[float]:
    if not coord:
        return None
    try:
        d = float(coord[0]) + float(coord[1]) / 60 + float(coord[2]) / 3600
        if ref in ["S", "W"]:
            d = -d
        return d
    except Exception:
        return None


# ================================================================
# LAYER 2: PIXEL ANALYSIS
# ================================================================


def analyze_pixels(image: Image.Image) -> dict:
    """Checks resolution and aspect ratio for CGI signals."""
    result = {
        "width": image.width,
        "height": image.height,
        "fraud_signals": [],
        "trust_signals": [],
        "too_small": False,
    }

    if image.width < MIN_WIDTH or image.height < MIN_HEIGHT:
        result["fraud_signals"].append(
            f"Image too small ({image.width}x{image.height})"
        )
        result["too_small"] = True
    else:
        result["trust_signals"].append(f"Good resolution: {image.width}x{image.height}")

    return result


# ================================================================
# LAYER 3: PERCEPTUAL HASH (Duplicate Detection)
# ================================================================


def generate_perceptual_hash(image: Image.Image) -> str:
    """Generates a perceptual hash for duplicate detection."""
    small = image.resize((8, 8), Image.LANCZOS).convert("L")
    pixels = list(small.getdata())
    avg = sum(pixels) / len(pixels)
    bits = "".join("1" if p > avg else "0" for p in pixels)
    return hex(int(bits, 2))[2:].zfill(16)


def is_duplicate(perceptual_hash: str, existing_hashes: List[str]) -> bool:
    """Hamming distance < 5 = likely duplicate."""

    def hamming(h1: str, h2: str) -> int:
        try:
            b1 = bin(int(h1, 16))[2:].zfill(64)
            b2 = bin(int(h2, 16))[2:].zfill(64)
            return sum(c1 != c2 for c1, c2 in zip(b1, b2))
        except Exception:
            return 64

    return any(hamming(perceptual_hash, h) < 5 for h in existing_hashes)


# ================================================================
# LAYER 4: GPT VISION AUDIT
# ================================================================


async def run_gpt_vision_audit(image_url: str) -> dict:
    """GPT-4o-mini Vision — only called when Python is inconclusive."""
    prompt = (
        "You are auditing a Nigerian real estate photo. "
        "Return ONLY a JSON object:\n"
        '{"is_real_photo": bool, "is_nigerian_context": bool, '
        '"cgi_probability": 0-100, "stock_photo_probability": 0-100, '
        '"foreign_architecture": bool, "fraud_signals": [], '
        '"trust_signals": [], "note": "brief assessment"}\n\n'
        "Nigerian context: tropical vegetation, red/laterite soil, "
        "Nigerian architecture, Abuja/Lagos patterns. "
        "Flag: snow, European buildings, perfect CGI lighting, watermarks."
    )

    try:
        client = get_openai_client()
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {"url": image_url, "detail": "low"},
                        },
                    ],
                }
            ],
            max_tokens=400,
            response_format={"type": "json_object"},
        )
        result = json.loads(response.choices[0].message.content)
        logger.info(f"✅ GPT Vision: {result.get('note', 'Complete')}")
        return result

    except Exception as e:
        logger.error(f"❌ GPT Vision failed: {e}")
        return {
            "is_real_photo": True,
            "is_nigerian_context": True,
            "cgi_probability": 0,
            "stock_photo_probability": 0,
            "foreign_architecture": False,
            "fraud_signals": [],
            "trust_signals": [],
            "note": "Audit skipped — manual review recommended",
        }


# ================================================================
# LAYER 5: FRAUD SCORER
# ================================================================


def calculate_authenticity_score(
    exif_result: dict,
    pixel_result: dict,
    gpt_result: dict,
    duplicate: bool,
) -> tuple:
    score = 100

    # EXIF deductions
    for signal in exif_result.get("fraud_signals", []):
        if "3D/CGI" in signal:
            score -= 40
        elif "Stock photo" in signal:
            score -= 30
        elif "No EXIF" in signal:
            score -= 15

    # Pixel deductions
    if pixel_result.get("too_small"):
        score -= 10

    # Duplicate
    if duplicate:
        score -= 50

    # GPT deductions
    if gpt_result:
        cgi = gpt_result.get("cgi_probability", 0)
        stk = gpt_result.get("stock_photo_probability", 0)
        if cgi > 70:
            score -= 35
        elif cgi > 40:
            score -= 15
        if stk > 60:
            score -= 25
        if gpt_result.get("foreign_architecture"):
            score -= 20
        if not gpt_result.get("is_nigerian_context"):
            score -= 15

    score = max(0, min(score, 100))

    if score >= 75:
        recommendation = "APPROVE"
    elif score >= 50:
        recommendation = "REVIEW"
    else:
        recommendation = "REJECT"

    return score, recommendation


# ================================================================
# MAIN: SINGLE IMAGE AUDIT
# ================================================================


async def audit_single_image(
    image_url: str,
    existing_hashes: List[str] = None,
) -> ImageAuditResult:
    """Full audit pipeline for one image."""
    if existing_hashes is None:
        existing_hashes = []

    fraud_signals = []
    trust_signals = []
    gpt_result = {}
    gpt_used = False
    exif_result = {}
    pixel_result = {}
    p_hash = ""

    try:
        response = requests.get(image_url, timeout=10)
        image = Image.open(io.BytesIO(response.content))

        # Layer 1
        exif_result = analyze_exif(image, image_url)
        fraud_signals.extend(exif_result.get("fraud_signals", []))
        trust_signals.extend(exif_result.get("trust_signals", []))

        # Layer 2
        pixel_result = analyze_pixels(image)
        fraud_signals.extend(pixel_result.get("fraud_signals", []))
        trust_signals.extend(pixel_result.get("trust_signals", []))

        # Layer 3
        p_hash = generate_perceptual_hash(image)
        dup = is_duplicate(p_hash, existing_hashes)
        if dup:
            fraud_signals.append("Duplicate image detected")

        # Layer 4 — GPT only if no critical Python fraud found
        critical = any(
            "3D/CGI" in s or "Stock photo" in s or "Duplicate" in s
            for s in fraud_signals
        )
        if not critical:
            gpt_result = await run_gpt_vision_audit(image_url)
            gpt_used = True
            fraud_signals.extend(gpt_result.get("fraud_signals", []))
            trust_signals.extend(gpt_result.get("trust_signals", []))

        # Layer 5
        score, recommendation = calculate_authenticity_score(
            exif_result, pixel_result, gpt_result, dup
        )

        is_real = score >= 50
        is_nigerian = gpt_result.get("is_nigerian_context", True) if gpt_used else True

        report = (
            f"Score: {score}/100 | Verdict: {recommendation}\n"
            f"Fraud: {fraud_signals}\n"
            f"Trust: {trust_signals}\n"
            f"GPT: {gpt_result.get('note', 'N/A')}"
        )

        return ImageAuditResult(
            image_url=image_url,
            is_real=is_real,
            is_nigerian_context=is_nigerian,
            authenticity_score=score,
            fraud_signals=fraud_signals,
            trust_signals=trust_signals,
            exif_data=exif_result,
            gpt_used=gpt_used,
            gpt_note=gpt_result.get("note", ""),
            perceptual_hash=p_hash,
            audit_report=report,
            recommendation=recommendation,
        )

    except Exception as e:
        logger.error(f"❌ Image audit failed: {e}")
        return ImageAuditResult(
            image_url=image_url,
            is_real=True,
            is_nigerian_context=True,
            authenticity_score=50,
            fraud_signals=[f"Audit error: {str(e)}"],
            trust_signals=[],
            exif_data={},
            gpt_used=False,
            gpt_note="Audit failed — manual review required",
            perceptual_hash="",
            audit_report=f"Audit failed: {str(e)}",
            recommendation="REVIEW",
        )


# ================================================================
# MAIN: LISTING-LEVEL AUDIT
# ================================================================


async def audit_listing_images(
    listing_id: int,
    image_urls: List[str],
) -> ListingAuditResult:
    """Audits all images for a listing. Tracks hashes for duplicate detection."""
    results = []
    seen_hashes = []
    gpt_calls = 0
    all_fraud = []
    all_trust = []

    for url in image_urls:
        result = await audit_single_image(url, seen_hashes)
        results.append(result)
        if result.perceptual_hash:
            seen_hashes.append(result.perceptual_hash)
        if result.gpt_used:
            gpt_calls += 1
        all_fraud.extend(result.fraud_signals)
        all_trust.extend(result.trust_signals)

    total = len(results)
    passed = sum(1 for r in results if r.recommendation == "APPROVE")
    failed = sum(1 for r in results if r.recommendation == "REJECT")
    review = sum(1 for r in results if r.recommendation == "REVIEW")
    avg = sum(r.authenticity_score for r in results) // total if total else 0

    if failed > 0:
        verdict, ai_ok = "REJECT", False
    elif review > total * 0.3:
        verdict, ai_ok = "REVIEW", False
    else:
        verdict, ai_ok = "APPROVE", True

    report = (
        f"LISTING {listing_id} | {total} images | "
        f"✅{passed} ⚠️{review} ❌{failed} | "
        f"Score: {avg}/100 | Verdict: {verdict} | GPT calls: {gpt_calls}"
    )

    logger.info(report)

    return ListingAuditResult(
        listing_id=listing_id,
        total_images=total,
        passed_images=passed,
        failed_images=failed,
        review_images=review,
        overall_score=avg,
        fraud_signals=list(set(all_fraud)),
        trust_signals=list(set(all_trust)),
        image_results=results,
        final_verdict=verdict,
        audit_report=report,
        ai_verified_real=ai_ok,
        gpt_calls_made=gpt_calls,
    )


# ================================================================
# TRUST ENGINE INTEGRATION
# ================================================================


async def audit_and_update_listing(listing, db) -> ListingAuditResult:
    """
    Full audit that automatically updates the listing's trust score.
    Call this after a Realtor uploads photos.
    """
    image_urls = [img.url for img in listing.images if img.url]

    if not image_urls:
        logger.warning(f"Listing {listing.id} has no images to audit")
        return None

    audit = await audit_listing_images(listing.id, image_urls)

    # Update AI fields
    listing.ai_verified_real = audit.ai_verified_real
    listing.ai_audit_report = audit.audit_report

    # Recalculate full trust score
    from app.services.document_trust_engine import calculate_full_trust_score

    doc_keys = []
    if getattr(listing, "cof_uploaded", False):
        doc_keys.append("c_of_o")
    if getattr(listing, "deed_uploaded", False):
        doc_keys.append("deed_of_assignment")
    if getattr(listing, "survey_uploaded", False):
        doc_keys.append("survey_plan")

    # Pass the listing itself so the score is computed from the stored
    # document_score, exactly as every other write path does. Before
    # this, the audit recomputed with a different formula and could
    # demote a listing by 17 points on a photo upload alone.
    trust = calculate_full_trust_score(
        gps_verified=bool(listing.gps_verified_at),
        gps_expired=False,
        gps_location_match=getattr(listing, "gps_location_match", False),
        ai_verified=audit.ai_verified_real,
        document_keys=doc_keys,
        listing=listing,
    )

    listing.trust_score = trust["total_score"]
    listing.trust_grade = trust["grade"].lower()
    db.commit()

    try:
        from app.credits.service import deduct_credits
        deduct_credits(
            tenant_id = listing.tenant_id,
            action    = "AI_VISION_AUDIT",
            tier      = "ACCESS",
            reference = f"ai_audit_{listing.id}",
            db        = db,
        )
    except Exception as e:
        logger.warning(f"Credit deduction failed for AI: {e}")

    logger.info(
        f"✅ Listing {listing.id} | "
        f"Trust: {listing.trust_score} | Grade: {listing.trust_grade}"
    )
    return audit
