import os
from dotenv import load_dotenv

load_dotenv()
from supabase import create_client

url = os.getenv("SUPABASE_URL")
key = os.getenv("SUPABASE_KEY")
client = create_client(url, key)

buckets_needed = ["property-documents", "property-reels"]

for bucket in buckets_needed:
    try:
        client.storage.create_bucket(bucket, options={"public": True})
        print(f"✅ Created: {bucket}")
    except Exception as e:
        print(f"⏭️  {bucket}: {e}")

print("Done.")
