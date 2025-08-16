import sqlite3

def init():
    conn = sqlite3.connect('gym.db')
    # ALTER TABLE sales ADD COLUMN buyer_type TEXT DEFAULT 'walk-in';

    cur = conn.cursor()

    # Drop existing tables
    cur.execute('DROP TABLE IF EXISTS members')
    cur.execute('DROP TABLE IF EXISTS products')
    cur.execute('DROP TABLE IF EXISTS sales')
    cur.execute('DROP TABLE IF EXISTS attendance')

    # Members table
    cur.execute('''
    CREATE TABLE members (
        rfid TEXT PRIMARY KEY,
        first_name TEXT NOT NULL,
        middle_name TEXT,
        last_name TEXT NOT NULL,
        birthday TEXT NOT NULL,
        last_visit TEXT,
        membership_expiration TEXT,
        membership_status TEXT,
        picture TEXT
    )
    ''')

    # Products table
    cur.execute('''
    CREATE TABLE products (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE,
        price REAL,
        stock INTEGER
    )
    ''')

    # Sales table
    cur.execute('''
    CREATE TABLE sales (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        product_id INTEGER,
        qty INTEGER,
        total REAL,
        date TEXT,
        FOREIGN KEY (product_id) REFERENCES products(id)
    )
    ''')

    # Attendance table
    cur.execute('''
    CREATE TABLE attendance (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        member_id TEXT,
        date TEXT,
        FOREIGN KEY (member_id) REFERENCES members(rfid)
    )
    ''')

    conn.commit()
    conn.close()
    print("✅ Clean database initialized with all required tables (no dummy data).")

if __name__ == '__main__':
    init()
