import sqlite3

conn = sqlite3.connect('gym.db')
cur = conn.cursor()

# Add rfid, login_time, logout_time if not exist
try:
    cur.execute("ALTER TABLE attendance ADD COLUMN rfid TEXT")
except sqlite3.OperationalError:
    print("✅ 'rfid' column already exists.")

try:
    cur.execute("ALTER TABLE attendance ADD COLUMN login_time TEXT")
except sqlite3.OperationalError:
    print("✅ 'login_time' already exists.")

try:
    cur.execute("ALTER TABLE attendance ADD COLUMN logout_time TEXT")
except sqlite3.OperationalError:
    print("✅ 'logout_time' already exists.")

conn.commit()
conn.close()
print("✅ Migration complete!")
