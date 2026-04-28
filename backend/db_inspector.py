import os
from sqlalchemy import create_engine, inspect
from dotenv import load_dotenv

# 1. Load keys
load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")


def audit_database_structure():
    if not DATABASE_URL:
        print("❌ ERROR: DATABASE_URL not found in .env")
        return

    # Create connection
    engine = create_engine(DATABASE_URL)
    inspector = inspect(engine)

    print("\n" + "=" * 60)
    print("        EST8GO SUPABASE SCHEMA AUDIT REPORT")
    print("=" * 60 + "\n")

    # Get all table names
    tables = inspector.get_table_names()

    if not tables:
        print("⚠️  The database is empty! No tables found.")
        return

    for table_name in tables:
        print(f"📁 TABLE: {table_name.upper()}")
        print("-" * 30)

        # Get columns
        columns = inspector.get_columns(table_name)
        for column in columns:
            pk = "🔑 PK" if column.get("primary_key") else ""
            nullable = "NULL" if column.get("nullable") else "NOT NULL"
            print(
                f"  - {column['name']:20} | {str(column['type']):12} | {nullable:8} {pk}"
            )

        # Get Foreign Keys (Relationships)
        fks = inspector.get_foreign_keys(table_name)
        for fk in fks:
            print(
                f"  🔗 Link: {fk['constrained_columns']} -> {fk['referred_table']}.{fk['referred_columns']}"
            )

        print("\n")

    print("=" * 60)
    print("        AUDIT COMPLETE")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    audit_database_structure()
