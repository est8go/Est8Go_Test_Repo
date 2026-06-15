"""
Store encrypted WhatsApp credentials for
a tenant.

Usage (from backend/ dir):
  PYTHONPATH=. python scripts/store_tenant_whatsapp.py

It prompts interactively for tenant_id,
phone_number_id, waba_id, and the access
token. The token is encrypted before
storage. Nothing is printed back in plain.
"""

from dotenv import load_dotenv
load_dotenv()

from app.models_registry import register_all_models
register_all_models()

from app.database.db import get_db
from app.tenants.models import Tenant, TenantChannel
from app.core.crypto import encrypt_secret, is_encryption_ready


def main():
    if not is_encryption_ready():
        print("❌ ENCRYPTION_KEY not set. Aborting.")
        return

    db = next(get_db())

    print("=== Store Tenant WhatsApp Credentials ===\n")

    # 1. Tenant
    _tid_raw = input("Tenant ID: ").strip()
    if not _tid_raw.isdigit():
        print("❌ Tenant ID must be a number.")
        return
    tenant_id = int(_tid_raw)

    tenant = db.get(Tenant, tenant_id)
    if not tenant:
        print(f"❌ No tenant with ID {tenant_id}.")
        return
    print(f"✓ Tenant: {tenant.business_name or tenant.slug}\n")

    # 2. Credentials
    phone_number_id = input("WhatsApp phone_number_id: ").strip()
    waba_id = input("WhatsApp Business Account ID (waba_id): ").strip()
    access_token = input("Access token (will be encrypted): ").strip()

    if not phone_number_id or not access_token:
        print("❌ phone_number_id and access_token are required.")
        return

    # 3. Find or create the WhatsApp channel for this tenant
    chan = (
        db.query(TenantChannel)
        .filter(
            TenantChannel.tenant_id == tenant_id,
            TenantChannel.platform == "whatsapp",
            TenantChannel.platform_id == phone_number_id,
        )
        .first()
    )

    if not chan:
        # Check if a whatsapp channel exists with a
        # different number for this tenant
        chan = (
            db.query(TenantChannel)
            .filter(
                TenantChannel.tenant_id == tenant_id,
                TenantChannel.platform == "whatsapp",
            )
            .first()
        )

    _enc_token = encrypt_secret(access_token)

    if chan:
        chan.platform_id = phone_number_id
        chan.waba_id = waba_id or None
        chan.access_token_encrypted = _enc_token
        chan.is_active = True
        print(f"\n✓ Updating existing channel (id {chan.id})")
    else:
        chan = TenantChannel(
            tenant_id=tenant_id,
            platform="whatsapp",
            platform_id=phone_number_id,
            waba_id=waba_id or None,
            access_token_encrypted=_enc_token,
            is_active=True,
            label="WhatsApp",
        )
        db.add(chan)
        print("\n✓ Creating new WhatsApp channel")

    # Also mirror the number onto the Tenant row
    # for resolver fallback compatibility
    tenant.whatsapp_phone_number_id = phone_number_id

    db.commit()

    print("✓ Credentials stored and encrypted.")
    print(f"  Tenant: {tenant.business_name or tenant.slug}")
    print(f"  phone_number_id: {phone_number_id}")
    print(f"  waba_id: {waba_id or '(none)'}")
    print(f"  token: [encrypted, {len(_enc_token)} chars]")


if __name__ == "__main__":
    main()
