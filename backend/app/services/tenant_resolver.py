"""
EST8GO TENANT RESOLVER
======================
Identifies which tenant owns an incoming message based on
the Meta platform ID (phone_number_id, page_id, instagram_account_id).

Rules-First (80/20):
- Pure Python/SQLAlchemy — zero AI cost
- Checks TenantChannel table first (multiple numbers support)
- Falls back to direct Tenant columns
- Returns None if unresolved (webhook is ignored safely)

Usage:
    from app.services.tenant_resolver import resolve_tenant_from_webhook
    tenant = resolve_tenant_from_webhook(db, platform, platform_id)
"""

import logging
from sqlalchemy.orm import Session
from app.tenants.models import Tenant, TenantChannel

logger = logging.getLogger(__name__)


def resolve_tenant_from_webhook(
    db: Session, platform: str, platform_id: str
) -> Tenant | None:
    """
    Master resolver: identifies tenant from any Meta platform ID.

    Args:
        db:          SQLAlchemy session
        platform:    'whatsapp', 'instagram', or 'facebook'
        platform_id: The Meta-provided ID for this platform

    Returns:
        Tenant object if found, None if unresolved
    """
    if not platform_id:
        logger.warning("⚠️ RESOLVER: No platform_id provided — ignoring webhook")
        return None

    # --- STEP 1: Check TenantChannel table (supports multiple numbers) ---
    channel = (
        db.query(TenantChannel)
        .filter(
            TenantChannel.platform == platform,
            TenantChannel.platform_id == platform_id,
            TenantChannel.is_active == True,
        )
        .first()
    )

    if channel:
        tenant = (
            db.query(Tenant)
            .filter(Tenant.id == channel.tenant_id, Tenant.is_active == True)
            .first()
        )

        if tenant:
            logger.info(
                f"✅ RESOLVER: [{platform}] {platform_id} → "
                f"Tenant {tenant.id} ({tenant.business_name}) via channel table"
            )
            return tenant

    # --- STEP 2: Fallback to direct Tenant columns ---
    if platform == "whatsapp":
        tenant = (
            db.query(Tenant)
            .filter(
                Tenant.whatsapp_phone_number_id == platform_id, Tenant.is_active == True
            )
            .first()
        )

    elif platform == "facebook":
        tenant = (
            db.query(Tenant)
            .filter(Tenant.facebook_page_id == platform_id, Tenant.is_active == True)
            .first()
        )

    elif platform == "instagram":
        tenant = (
            db.query(Tenant)
            .filter(
                Tenant.instagram_account_id == platform_id, Tenant.is_active == True
            )
            .first()
        )

    else:
        logger.warning(f"⚠️ RESOLVER: Unknown platform '{platform}' — ignoring")
        return None

    if tenant:
        logger.info(
            f"✅ RESOLVER: [{platform}] {platform_id} → "
            f"Tenant {tenant.id} ({tenant.business_name}) via direct column"
        )
        return tenant

    # --- STEP 3: Unresolved — log and return None ---
    logger.error(
        f"❌ RESOLVER: [{platform}] {platform_id} — "
        f"No tenant found. Register this ID in tenant_channels."
    )
    return None


def extract_platform_id_from_webhook(data: dict) -> tuple[str, str]:
    """
    Extracts the platform and its ID from a raw Meta webhook payload.

    Returns:
        Tuple of (platform, platform_id)
        e.g. ('whatsapp', '1138633615995344')
             ('facebook', '123456789')
             ('instagram', '987654321')
    """
    try:
        entry = data.get("entry", [{}])[0]
        changes = entry.get("changes", [{}])[0]
        value = changes.get("value", {})

        # WhatsApp: phone_number_id is in metadata
        if "messages" in value or "statuses" in value:
            phone_number_id = value.get("metadata", {}).get("phone_number_id", "")
            if phone_number_id:
                return ("whatsapp", phone_number_id)

        # Instagram / Facebook Messenger
        if "messaging" in entry:
            recipient_id = entry["messaging"][0].get("recipient", {}).get("id", "")
            raw = str(data).lower()
            if "instagram" in raw:
                return ("instagram", recipient_id)
            return ("facebook", recipient_id)

    except Exception as e:
        logger.error(f"❌ RESOLVER: Failed to extract platform ID — {e}")

    return ("unknown", "")


def register_tenant_channel(
    db: Session, tenant_id: int, platform: str, platform_id: str, label: str = ""
) -> TenantChannel:
    """
    Registers a new channel for a tenant.
    Use this when onboarding a new tenant or adding a second number.

    Args:
        db:          SQLAlchemy session
        tenant_id:   The tenant's ID
        platform:    'whatsapp', 'instagram', or 'facebook'
        platform_id: The Meta platform ID
        label:       Optional label e.g. 'Sales Line', 'Rentals Line'

    Returns:
        The created or existing TenantChannel
    """
    # Check if already exists
    existing = (
        db.query(TenantChannel).filter(TenantChannel.platform_id == platform_id).first()
    )

    if existing:
        logger.info(
            f"⏭️ REGISTER: Channel {platform_id} already exists "
            f"for tenant {existing.tenant_id}"
        )
        return existing

    channel = TenantChannel(
        tenant_id=tenant_id,
        platform=platform,
        platform_id=platform_id,
        label=label or f"{platform.title()} Line",
        is_active=True,
    )
    db.add(channel)
    db.commit()
    db.refresh(channel)

    logger.info(
        f"✅ REGISTER: New channel [{platform}] {platform_id} → Tenant {tenant_id}"
    )
    return channel


def deactivate_tenant_channel(db: Session, platform_id: str) -> bool:
    """
    Deactivates a channel when a company changes their number.
    Preserves history — does not delete.

    Returns:
        True if deactivated, False if not found
    """
    channel = (
        db.query(TenantChannel).filter(TenantChannel.platform_id == platform_id).first()
    )

    if not channel:
        logger.warning(f"⚠️ DEACTIVATE: Channel {platform_id} not found")
        return False

    channel.is_active = False
    db.commit()

    logger.info(f"✅ DEACTIVATE: Channel {platform_id} deactivated")
    return True
