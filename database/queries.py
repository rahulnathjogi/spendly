import sqlite3
from datetime import datetime
from database.db import get_db


def get_user_by_id(user_id):
    # SA2: fetch name, email, member_since from users table
    # Returns dict {"name": ..., "email": ..., "member_since": "Month YYYY"} or None
    conn = get_db()
    try:
        row = conn.execute(
            "SELECT name, email, created_at FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()
        if row is None:
            return None
        member_since = datetime.strptime(row["created_at"].split(".")[0], "%Y-%m-%d %H:%M:%S").strftime("%B %Y")
        return {"name": row["name"], "email": row["email"], "member_since": member_since}
    finally:
        conn.close()


def get_summary_stats(user_id, date_from=None, date_to=None):
    conn = get_db()
    try:
        if date_from and date_to:
            row = conn.execute(
                "SELECT COALESCE(SUM(amount), 0.0) AS total, COUNT(*) AS count "
                "FROM expenses WHERE user_id = ? AND date BETWEEN ? AND ?",
                (user_id, date_from, date_to),
            ).fetchone()
            top_row = conn.execute(
                "SELECT category FROM expenses WHERE user_id = ? AND date BETWEEN ? AND ? "
                "GROUP BY category ORDER BY SUM(amount) DESC LIMIT 1",
                (user_id, date_from, date_to),
            ).fetchone()
        else:
            row = conn.execute(
                "SELECT COALESCE(SUM(amount), 0.0) AS total, COUNT(*) AS count "
                "FROM expenses WHERE user_id = ?",
                (user_id,),
            ).fetchone()
            top_row = conn.execute(
                "SELECT category FROM expenses WHERE user_id = ? "
                "GROUP BY category ORDER BY SUM(amount) DESC LIMIT 1",
                (user_id,),
            ).fetchone()

        return {
            "total_spent": float(row["total"]),
            "transaction_count": int(row["count"]),
            "top_category": top_row["category"] if top_row else "—",
        }
    finally:
        conn.close()


def get_recent_transactions(user_id, limit=10, date_from=None, date_to=None):
    conn = get_db()
    try:
        if date_from and date_to:
            rows = conn.execute(
                "SELECT date, description, category, amount FROM expenses "
                "WHERE user_id = ? AND date BETWEEN ? AND ? "
                "ORDER BY date DESC, id DESC LIMIT ?",
                (user_id, date_from, date_to, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT date, description, category, amount FROM expenses "
                "WHERE user_id = ? ORDER BY date DESC, id DESC LIMIT ?",
                (user_id, limit),
            ).fetchall()
        return [
            {
                "date": row["date"],
                "description": row["description"],
                "category": row["category"],
                "amount": float(row["amount"]),
            }
            for row in rows
        ]
    finally:
        conn.close()


def insert_expense(user_id, amount, category, date, description):
    conn = get_db()
    try:
        conn.execute(
            "INSERT INTO expenses (user_id, amount, category, date, description) VALUES (?, ?, ?, ?, ?)",
            (user_id, amount, category, date, description),
        )
        conn.commit()
    finally:
        conn.close()


def get_category_breakdown(user_id, date_from=None, date_to=None):
    conn = get_db()
    try:
        if date_from and date_to:
            rows = conn.execute(
                "SELECT category AS name, SUM(amount) AS amount FROM expenses "
                "WHERE user_id = ? AND date BETWEEN ? AND ? "
                "GROUP BY category ORDER BY amount DESC",
                (user_id, date_from, date_to),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT category AS name, SUM(amount) AS amount FROM expenses "
                "WHERE user_id = ? GROUP BY category ORDER BY amount DESC",
                (user_id,),
            ).fetchall()
        if not rows:
            return []
        total = sum(float(row["amount"]) for row in rows)
        result = [
            {"name": row["name"], "amount": float(row["amount"]), "pct": round(float(row["amount"]) / total * 100)}
            for row in rows
        ]
        diff = 100 - sum(c["pct"] for c in result)
        result[0]["pct"] += diff
        return result
    finally:
        conn.close()
