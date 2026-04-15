import sqlite3

conn = sqlite3.connect("app.db")
cur = conn.cursor()

print("Tables:")
cur.execute("SELECT name FROM sqlite_master WHERE type='table';")
tables = cur.fetchall()
print(tables)

print("\nUsers:")
try:
    cur.execute("SELECT id, email, tenant_id FROM users;")
    rows = cur.fetchall()
    print(rows)
except Exception as e:
    print("ERROR:", e)

conn.close()