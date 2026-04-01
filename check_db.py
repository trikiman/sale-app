import sqlite3
conn = sqlite3.connect("database/sale_monitor.db")
c = conn.cursor()
c.execute("SELECT count(*) FROM sale_appearances")
print("Appearances:", c.fetchone()[0])
c.execute("SELECT count(*) FROM sale_sessions")
print("Sessions:", c.fetchone()[0])
c.execute("SELECT product_id, count(*) as cnt FROM sale_sessions GROUP BY product_id ORDER BY cnt DESC LIMIT 5")
for row in c.fetchall():
    print(f"  product {row[0]}: {row[1]} sessions")
