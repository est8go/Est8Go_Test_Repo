import os
from dotenv import load_dotenv

load_dotenv()
from supabase import create_client

url = os.getenv("SUPABASE_URL")
key = os.getenv("SUPABASE_KEY")
client = create_client(url, key)

# property-documents is PRIVATE — sensitive title docs (C of O, deeds) are
# served only via the access-controlled proxy, never a public URL (A2).
# property-reels stays public (non-sensitive marketing videos).
buckets_needed = {
    "property-documents": False,
    "property-reels": True,
}

for bucket, is_public in buckets_needed.items():
    try:
        client.storage.create_bucket(bucket, options={"public": is_public})
        print(f"✅ Created: {bucket} (public={is_public})")
    except Exception as e:
        print(f"⏭️  {bucket}: {e}")

print("Done.")
