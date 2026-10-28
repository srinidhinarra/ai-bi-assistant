import sqlite3
import pandas as pd

CSV_PATH = "ai_bi_assistant_sales_data - GET.csv"   
DB_PATH = "sales.db"

df = pd.read_csv(CSV_PATH)
df["Order_date"] = pd.to_datetime(df["Order_date"], format="%d-%m-%Y").dt.strftime("%Y-%m-%d")

with sqlite3.connect(DB_PATH) as conn:
    df.to_sql("sales", conn, if_exists="replace", index=False)

print(f"Loaded {len(df)} rows into {DB_PATH}")