import asyncio
from app.database.db import SessionLocal
from app.services.notification_service import check_for_abandoned_chats


async def main():
    print("🚀 Reminder Worker Started (Checking every 60 minutes)...")
    while True:
        db = SessionLocal()
        try:
            await check_for_abandoned_chats(db)
        finally:
            db.close()

        # Wait for 1 hour before checking again
        await asyncio.sleep(3600)


if __name__ == "__main__":
    asyncio.run(main())
