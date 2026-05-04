import os
from dotenv import load_dotenv

load_dotenv()
from supabase import create_client

url = os.getenv("SUPABASE_URL")
key = os.getenv("SUPABASE_KEY")
client = create_client(url, key)
files = client.storage.from_("property-reels").list()
print("Files:", [f["name"] for f in files])
