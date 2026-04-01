#!/usr/bin/env python3
import sys
sys.path.insert(0, '/home/ubuntu/saleapp')
from database.sale_history import update_product_stats
update_product_stats()
print("Stats updated!")

# Verify
import sqlite3
conn = sqlite3.connect('/home/ubuntu/saleapp/data/salebot.db')
row = conn.execute("SELECT count(*) FROM product_catalog WHERE total_sale_count > 0").fetchone()
print(f"Products with sale data: {row[0]}")
row = conn.execute("SELECT product_id, name, total_sale_count, last_sale_type, usual_sale_time FROM product_catalog WHERE total_sale_count > 0 ORDER BY total_sale_count DESC LIMIT 5").fetchall()
for r in row:
    print(f"  {r[0]}: {r[1]} - {r[2]}x sales, type={r[3]}, usual={r[4]}")
