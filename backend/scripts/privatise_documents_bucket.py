"""
PHASE 1 A2.1 — PRIVATISE THE property-documents BUCKET
=======================================================
Sensitive title documents (C of O, deeds, surveys) must NEVER be served
via public URLs. This flips the `property-documents` Supabase bucket to
private so objects are only reachable via the access-controlled proxy
route (A2.2) — never a public URL.

Idempotent: setting an already-private bucket to private is a no-op.
Only touches `property-documents` — `property-images` / `property-reels`
are left untouched (non-sensitive, may stay public).

Run from the backend folder:
    PYTHONPATH=. python scripts/privatise_documents_bucket.py
"""

import os
from dotenv import load_dotenv

load_dotenv()

from supabase import create_client

BUCKET = "property-documents"


def _public_flag(client) -> bool | None:
    for b in client.storage.list_buckets():
        if b.name == BUCKET:
            return getattr(b, "public", None)
    return None


def main():
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_KEY")  # service_role key — has update_bucket rights
    if not url or not key:
        raise SystemExit("FAILED: SUPABASE_URL / SUPABASE_KEY missing from env")

    client = create_client(url, key)

    before = _public_flag(client)
    if before is None:
        raise SystemExit(f"FAILED: Bucket '{BUCKET}' not found - nothing to privatise")
    print(f"BEFORE: {BUCKET} public={before}")

    # Idempotent: flipping already-private to private is a no-op.
    client.storage.update_bucket(BUCKET, {"public": False})

    after = _public_flag(client)
    print(f"AFTER:  {BUCKET} public={after}")

    if after is False:
        print(f"OK: {BUCKET} is now PRIVATE - documents no longer publicly served.")
    else:
        raise SystemExit(f"FAILED: {BUCKET} public flag is still {after!r} - check service-role key")


if __name__ == "__main__":
    main()
