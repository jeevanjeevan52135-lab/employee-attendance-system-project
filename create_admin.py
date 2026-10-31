"""Create the first admin account. Run: python create_admin.py"""
import getpass
import sqlite3
from pathlib import Path
from werkzeug.security import generate_password_hash

DB_PATH = Path(__file__).resolve().parent / "attendance.db"
name = input("Admin full name: ").strip()
email = input("Admin email: ").strip().lower()
password = getpass.getpass("Password (minimum 10 characters): ")

if not name or "@" not in email or len(password) < 10:
    raise SystemExit("Enter a name, valid email and password of at least 10 characters.")

if not DB_PATH.exists():
    # Importing app initializes the schema.
    from app import init_db
    init_db()

conn = sqlite3.connect(DB_PATH)
try:
    conn.execute(
        "INSERT INTO users(name,email,password_hash,role) VALUES(?,?,?,'admin')",
        (name, email, generate_password_hash(password))
    )
    conn.commit()
    print("Admin account created. Start the app with: python app.py")
except sqlite3.IntegrityError:
    conn.rollback()
    raise SystemExit("That email already exists.")
finally:
    conn.close()
