from sqlalchemy import text
from app.database.db import SessionLocal


def sync_chat_tables():
    db = SessionLocal()
    print("🚀 Building AI Chat Memory in Supabase...")

    sql_commands = [
        # 1. Create Conversations Table
        """
        CREATE TABLE IF NOT EXISTS conversations (
            id SERIAL PRIMARY KEY,
            tenant_id INTEGER REFERENCES tenants(id),
            channel VARCHAR(50),
            external_user_id VARCHAR(255),
            display_name VARCHAR(255),
            state VARCHAR(50) DEFAULT 'ACTIVE',
            data_json TEXT DEFAULT '{}',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            reminder_count INTEGER DEFAULT 0,
            last_reminder_sent_at TIMESTAMP
        );
        """,
        # 2. Create Conversation Messages Table
        """
        CREATE TABLE IF NOT EXISTS conversation_messages (
            id SERIAL PRIMARY KEY,
            conversation_id INTEGER REFERENCES conversations(id) ON DELETE CASCADE,
            role VARCHAR(50),
            content TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """,
    ]

    try:
        for cmd in sql_commands:
            db.execute(text(cmd))
            db.commit()
            print("✅ Step complete.")

        print("\n🎉 CHAT MEMORY IS LIVE ON SUPABASE!")
    except Exception as e:
        print(f"❌ Error: {e}")
        db.rollback()
    finally:
        db.close()


if __name__ == "__main__":
    sync_chat_tables()
