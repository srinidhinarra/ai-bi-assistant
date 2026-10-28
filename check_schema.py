import sqlite3

conn = sqlite3.connect("sales.db")

for name, sql in conn.execute("SELECT name, sql FROM sqlite_master WHERE type='table'"):
    print(sql)
    print()

table = conn.execute(
    "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
).fetchone()[0]

print("First 5 rows:")
for row in conn.execute(f"SELECT * FROM {table} LIMIT 5"):
    print(row)

print("\nRow count:", conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])