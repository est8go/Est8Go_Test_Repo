from __future__ import annotations
import sqlite3

DB_PATH = "app.db"

def _has_column(cur, table: str, col: str) -> bool:
    cur.execute(f"PRAGMA table_info({table})")
    return any(r[1] == col for r in cur.fetchall())

def main() -> None:
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()

    if not _has_column(cur, "tenants", "plan"):
        cur.execute(
            "ALTER TABLE tenants ADD COLUMN plan VARCHAR(20) NOT NULL DEFAULT 'free'"
        )
        print("[OK] Added tenants.plan")
    else:
        print("[SKIP] tenants.plan already exists")

    con.commit()
    con.close()
    print("[DONE] Migration complete.")

if __name__ == "__main__":
    main()