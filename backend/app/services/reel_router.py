"""
EST8GO REEL ROUTER (Stage C)
==============================
Realtor portal endpoints for social reel generation.

Endpoints:
    POST /reels/generate/{listing_id}  — Trigger reel generation
    GET  /reels/{listing_id}           — Check generation status
    GET  /reels/listing/{listing_id}   — Get all reels for a listing
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, BackgroundTasks, Form
from sqlalchemy.orm import Session

from app.database.db import get_db
from app.auth.deps import get_current_user
from app.users.models import User
from app.listings.models import Listing, ListingImage
from app.services.reel_engine import (
    ReelRequest,
    generate_property_reel,
    check_ffmpeg_available,
    ASPECT_RATIOS,
    MUSIC_TRACKS,
)
from app.services.notification_service import send_meta_text_message
from app.services.tenant_service import get_tenant_profile

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/reels", tags=["Social Reel Engine"])


# ================================================================
# 1. GENERATE REEL
# ================================================================


@router.post("/generate/{listing_id}", tags=["Social Reel Engine"])
async def generate_listing_reel(
    listing_id: int,
    background_tasks: BackgroundTasks,
    music_choice: str = Form(
        default="corporate",
        description="Music track: afrobeats / corporate / ambient / custom",
    ),
    aspect_ratio: str = Form(
        default="reels",
        description="Format: reels (9:16) / feed (1:1) / facebook (16:9)",
    ),
    custom_music_url: Optional[str] = Form(
        default=None, description="Optional: URL to your own MP3 (max 5MB)"
    ),
    x_tenant_id: int = Header(..., alias="X-Tenant-Id"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    ONE-CLICK SOCIAL BLAST:
    Triggers async reel generation for a verified listing.
    Realtor gets WhatsApp notification when video is ready.
    """
    # Validate inputs
    if music_choice not in list(MUSIC_TRACKS.keys()) + ["custom"]:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid music choice. Options: {list(MUSIC_TRACKS.keys()) + ['custom']}",
        )

    if aspect_ratio not in ASPECT_RATIOS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid aspect ratio. Options: {list(ASPECT_RATIOS.keys())}",
        )

    # Check FFmpeg availability
    if not check_ffmpeg_available():
        raise HTTPException(
            status_code=503,
            detail="Video engine not available. FFmpeg not installed on server.",
        )

    # Get listing with tenant isolation
    listing = (
        db.query(Listing)
        .filter(
            Listing.id == listing_id,
            Listing.tenant_id == x_tenant_id,
        )
        .first()
    )
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")

    # Get images
    images = db.query(ListingImage).filter(ListingImage.listing_id == listing_id).all()

    if not images:
        raise HTTPException(
            status_code=400,
            detail="No photos found for this listing. Upload photos first.",
        )

    image_urls = [img.url for img in images if img.url]

    # Get tenant profile
    tenant_profile = get_tenant_profile(db, x_tenant_id)
    biz_name = tenant_profile.get("business_name", "Est8Go")

    # Build listing data for the reel
    price_fmt = f"₦{int(listing.price):,}" if listing.price else "Price on request"

    listing_data = {
        "biz_name": biz_name,
        "title": listing.title,
        "location": listing.location,
        "price": price_fmt,
        "property_type": listing.property_type or "Property",
        "trust_score": listing.trust_score or 0,
        "trust_grade": listing.trust_grade or "ungraded",
        "gps_verified": bool(listing.gps_verified_at),
        "ai_verified": listing.ai_verified_real or False,
        "phone": current_user.phone_number or "",
    }

    # Build reel request
    reel_request = ReelRequest(
        listing_id=listing_id,
        tenant_id=x_tenant_id,
        image_urls=image_urls,
        music_choice=music_choice,
        aspect_ratio=aspect_ratio,
        custom_music_url=custom_music_url,
        realtor_phone=current_user.phone_number,
    )

    # Trigger async generation
    background_tasks.add_task(
        _generate_and_notify,
        reel_request,
        listing_data,
        current_user.phone_number,
        biz_name,
        db,
    )

    return {
        "status": "generating",
        "listing_id": listing_id,
        "listing_title": listing.title,
        "music": music_choice,
        "format": aspect_ratio,
        "images_count": len(image_urls),
        "message": (
            f"🎬 Reel generation started for *{listing.title}*. "
            f"You'll receive a WhatsApp notification when your "
            f"{aspect_ratio} reel is ready to download."
        ),
    }


# ================================================================
# 2. REEL OPTIONS (What's available for a listing)
# ================================================================


@router.get("/options/{listing_id}", tags=["Social Reel Engine"])
async def get_reel_options(
    listing_id: int,
    x_tenant_id: int = Header(..., alias="X-Tenant-Id"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Returns available reel options and listing readiness.
    Shows Realtor what they can generate and what's missing.
    """
    listing = (
        db.query(Listing)
        .filter(Listing.id == listing_id, Listing.tenant_id == x_tenant_id)
        .first()
    )
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")

    images = db.query(ListingImage).filter(ListingImage.listing_id == listing_id).all()

    image_count = len(images)
    trust_score = listing.trust_score or 0
    trust_grade = listing.trust_grade or "ungraded"
    gps_verified = bool(listing.gps_verified_at)
    ai_verified = listing.ai_verified_real or False

    # Readiness checks
    checks = {
        "photos": {
            "ready": image_count >= 3,
            "value": image_count,
            "message": f"{image_count}/3 photos minimum required",
        },
        "gps": {
            "ready": gps_verified,
            "message": "GPS verified" if gps_verified else "GPS not captured",
        },
        "ai_audit": {
            "ready": ai_verified,
            "message": "AI audit passed" if ai_verified else "AI audit pending",
        },
        "trust_score": {
            "ready": trust_score >= 50,
            "value": trust_score,
            "message": f"Trust score: {trust_score}/100",
        },
    }

    ready_for_reel = image_count >= 3

    return {
        "listing_id": listing_id,
        "title": listing.title,
        "ready_for_reel": ready_for_reel,
        "trust_grade": trust_grade,
        "trust_score": trust_score,
        "checks": checks,
        "music_options": {
            "afrobeats": "Trending Afrobeats instrumental",
            "corporate": "Professional corporate background",
            "ambient": "Calm luxury ambient",
            "custom": "Upload your own MP3 (max 5MB)",
        },
        "format_options": {
            "reels": "Instagram Reels / TikTok (9:16 vertical)",
            "feed": "Instagram / Facebook Feed (1:1 square)",
            "facebook": "Facebook / YouTube (16:9 landscape)",
        },
        "message": (
            "✅ Ready to generate your reel!"
            if ready_for_reel
            else f"⚠️ Upload at least 3 photos to generate a reel "
            f"({image_count} uploaded so far)"
        ),
    }


# ================================================================
# 3. FFMPEG STATUS CHECK
# ================================================================


@router.get("/engine-status", tags=["Social Reel Engine"])
async def check_engine_status():
    """Checks if the video engine is available on the server."""
    available = check_ffmpeg_available()
    return {
        "ffmpeg_available": available,
        "status": "✅ Video engine ready" if available else "❌ FFmpeg not installed",
        "supported_formats": list(ASPECT_RATIOS.keys()),
        "supported_music": list(MUSIC_TRACKS.keys()) + ["custom"],
        "max_duration_sec": 22,
        "max_photos": 8,
    }


# ================================================================
# BACKGROUND TASK — Generate + Notify
# ================================================================


async def _generate_and_notify(
    request: ReelRequest,
    listing_data: dict,
    realtor_phone: Optional[str],
    biz_name: str,
    db: Session,
):
    """
    Runs reel generation and sends WhatsApp notification when done.
    Executes in background — never blocks the API response.
    """
    try:
        result = await generate_property_reel(request, listing_data, db)

        if result.success and realtor_phone:
            success_msg = (
                f"🎬 *Your Reel is Ready!* ✅\n\n"
                f"*{listing_data.get('title', 'Property')}*\n"
                f"Format: {result.aspect_ratio.title()}\n"
                f"Duration: {result.duration} seconds\n"
                f"Size: {result.file_size_mb}MB\n\n"
                f"📥 *Download your reel:*\n{result.video_url}\n\n"
                f"📝 *Suggested caption:*\n{result.caption[:200]}...\n\n"
                f"Post it now while the listing is hot! 🔥"
            )
            await send_meta_text_message(realtor_phone, success_msg)
            logger.info(f"✅ Reel delivered to {realtor_phone}")

        elif not result.success and realtor_phone:
            error_msg = (
                f"⚠️ *Reel Generation Issue*\n\n"
                f"There was a problem generating your reel for "
                f"*{listing_data.get('title', 'this listing')}*.\n\n"
                f"Error: {result.error}\n\n"
                f"Please try again or contact Est8Go support."
            )
            await send_meta_text_message(realtor_phone, error_msg)

    except Exception as e:
        logger.error(f"❌ Background reel task failed: {e}", exc_info=True)
