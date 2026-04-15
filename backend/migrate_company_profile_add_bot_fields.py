import app.models_registry  # noqa: F401

from __future__ import annotations

from sqlalchemy import text

from app.database.db import engine


def _col_exists(conn, table: str, col: str) -> bool:
    rows = conn.execute(text(f"PRAGMA table_info({table});")).fetchall()
    # PRAGMA columns: cid, name, type, notnull, dflt_value, pk
    return any(r[1] == col for r in rows)


def _add_col(conn, table: str, col: str, ddl: str) -> None:
    if _col_exists(conn, table, col):
        print(f"[SKIP] {table}.{col} already exists")
        return
    conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {col} {ddl};"))
    print(f"[OK] Added {table}.{col}")


def main() -> None:
    table = "company_profiles"
    with engine.begin() as conn:
        _add_col(conn, table, "assistant_name", "VARCHAR(80) NOT NULL DEFAULT 'Aor'")
        _add_col(conn, table, "assistant_role", "VARCHAR(120) NOT NULL DEFAULT 'Real Estate Assistant'")
        _add_col(conn, table, "emoji_mode", "VARCHAR(20) NOT NULL DEFAULT 'minimal'")

    print("[DONE] Migration complete.")


if __name__ == "__main__":
    main()