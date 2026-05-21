import sqlite3
import os
from werkzeug.security import generate_password_hash

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "spendly.db")


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    conn = get_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS expenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            amount REAL NOT NULL,
            category TEXT NOT NULL,
            date TEXT NOT NULL,
            description TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (user_id) REFERENCES users(id)
        );
    """)
    conn.commit()
    conn.close()


def seed_db():
    conn = get_db()
    count = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    if count > 0:
        conn.close()
        return

    conn.execute(
        "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
        ("Demo User", "demo@spendly.com", generate_password_hash("demo123")),
    )
    conn.commit()

    user_id = conn.execute("SELECT id FROM users WHERE email = ?", ("demo@spendly.com",)).fetchone()[0]

    expenses = [
        (user_id, 450.0,  "Food",          "2026-05-01", "Groceries from supermarket"),
        (user_id, 120.0,  "Transport",      "2026-05-03", "Auto rickshaw to office"),
        (user_id, 2200.0, "Bills",          "2026-05-05", "Electricity bill"),
        (user_id, 800.0,  "Health",         "2026-05-08", "Pharmacy — vitamins"),
        (user_id, 650.0,  "Entertainment",  "2026-05-10", "Movie tickets"),
        (user_id, 1500.0, "Shopping",       "2026-05-13", "New headphones"),
        (user_id, 300.0,  "Other",          "2026-05-16", "Miscellaneous"),
        (user_id, 380.0,  "Food",           "2026-05-19", "Dinner with friends"),
    ]
    conn.executemany(
        "INSERT INTO expenses (user_id, amount, category, date, description) VALUES (?, ?, ?, ?, ?)",
        expenses,
    )
    conn.commit()
    conn.close()


def create_user(name, email, password):
    password_hash = generate_password_hash(password)
    conn = get_db()
    try:
        cursor = conn.execute(
            "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
            (name, email, password_hash),
        )
        conn.commit()
        return cursor.lastrowid
    finally:
        conn.close()
