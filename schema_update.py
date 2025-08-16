import sqlite3

conn = sqlite3.connect('gym.db')
cursor = conn.cursor()

try:
    cursor.execute("ALTER TABLE sales ADD COLUMN buyer_type TEXT DEFAULT 'walk-in'")
    print("✅ Column 'buyer_type' added to 'sales' table.")
except sqlite3.OperationalError as e:
    print(f"⚠️ Skipped: {e}")

conn.commit()
conn.close()
