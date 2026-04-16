"""
Database health check script.
Uses DATABASE_PATH from config to ensure consistency.
"""
import sqlite3
import sys
from config import DATABASE_PATH, DATA_DIR
import os

print(f"Database path: {DATABASE_PATH}")
print(f"Data directory exists: {os.path.exists(DATA_DIR)}")
print(f"Database file exists: {os.path.exists(DATABASE_PATH)}")

if not os.path.exists(DATABASE_PATH):
    print("ERROR: Database file not found!")
    sys.exit(1)

try:
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    
    # Get list of tables
    c.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [row[0] for row in c.fetchall()]
    print(f"\nTables found: {tables}")
    
    # Check key tables
    if 'sale_appearances' in tables:
        c.execute("SELECT count(*) FROM sale_appearances")
        print("Appearances:", c.fetchone()[0])
    else:
        print("Note: sale_appearances table not found (may be unused)")
    
    if 'sale_sessions' in tables:
        c.execute("SELECT count(*) FROM sale_sessions")
        print("Sessions:", c.fetchone()[0])
        
        c.execute("SELECT product_id, count(*) as cnt FROM sale_sessions GROUP BY product_id ORDER BY cnt DESC LIMIT 5")
        rows = c.fetchall()
        if rows:
            print("Top products by sessions:")
            for row in rows:
                print(f"  product {row[0]}: {row[1]} sessions")
    else:
        print("Note: sale_sessions table not found (may be unused)")
    
    # Check users table (main app table)
    if 'users' in tables:
        c.execute("SELECT count(*) FROM users")
        print(f"Users: {c.fetchone()[0]}")
    
    # Check favorite products
    if 'favorite_products' in tables:
        c.execute("SELECT count(*) FROM favorite_products")
        print(f"Favorite products: {c.fetchone()[0]}")
    
    conn.close()
    print("\nDatabase check completed successfully.")
    
except sqlite3.Error as e:
    print(f"ERROR: Database error: {e}")
    sys.exit(1)
except Exception as e:
    print(f"ERROR: {e}")
    sys.exit(1)
