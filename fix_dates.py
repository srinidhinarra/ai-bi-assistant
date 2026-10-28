import sqlite3

conn = sqlite3.connect("sales.db")

# 03-01-2026 -> 2026-01-03 (only touches rows still in dd-mm-yyyy, safe to re-run)
conn.execute("""
    UPDATE sales
    SET Order_date = substr(Order_date, 7, 4) || '-' ||
                     substr(Order_date, 4, 2) || '-' ||
                     substr(Order_date, 1, 2)
    WHERE Order_date LIKE '__-__-____'
""")
conn.commit()

print("Sample dates:", [r[0] for r in conn.execute("SELECT Order_date FROM sales LIMIT 3")])
print("Monthly revenue:")
for row in conn.execute("""
    SELECT strftime('%Y-%m', Order_date) AS month,
           SUM(Quantity * Unit_price - Discount_amount) AS revenue
    FROM sales
    WHERE Status = 'Completed' AND Quantity > 0 AND Unit_price IS NOT NULL
    GROUP BY month ORDER BY month
"""):
    print(" ", row)
conn.close()