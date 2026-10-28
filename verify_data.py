import sqlite3

conn = sqlite3.connect("sales.db")
table = conn.execute(
    "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
).fetchone()[0]

cols = [r[1] for r in conn.execute(f"PRAGMA table_info({table})")]
print("Table:", table)
print("Columns:", cols)

# find the date column and show a sample
date_col = next(c for c in cols if "date" in c.lower())
qty_col = next(c for c in cols if c.lower() == "quantity")
price_col = next(c for c in cols if "unit" in c.lower())
disc_col = next(c for c in cols if "discount" in c.lower())
status_col = next(c for c in cols if "status" in c.lower())

print("\nSample dates:", [r[0] for r in conn.execute(f"SELECT {date_col} FROM {table} LIMIT 3")])

total = conn.execute(f"""
    SELECT SUM({qty_col} * {price_col} - {disc_col}) FROM {table}
    WHERE {status_col} = 'Completed' AND {qty_col} > 0 AND {price_col} IS NOT NULL
""").fetchone()[0]
print("\nTotal revenue (expected 1439200):", total)