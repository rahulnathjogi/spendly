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
        member_since = datetime.strptime(row["created_at"], "%Y-%m-%d %H:%M:%S").strftime("%B %Y")
        return {"name": row["name"], "email": row["email"], "member_since": member_since}
    finally:
        conn.close()


def get_summary_stats(user_id):
    # SA2: aggregate expenses for the user
    # Returns dict {"total_spent": float, "transaction_count": int, "top_category": str}
    conn = get_db()
    try:
        row = conn.execute(
            "SELECT COALESCE(SUM(amount), 0.0) AS total, COUNT(*) AS count FROM expenses WHERE user_id = ?",
            (user_id,),
        ).fetchone()
        total_spent = float(row["total"])
        transaction_count = int(row["count"])

        top_row = conn.execute(
            "SELECT category FROM expenses WHERE user_id = ? GROUP BY category ORDER BY SUM(amount) DESC LIMIT 1",
            (user_id,),
        ).fetchone()
        top_category = top_row["category"] if top_row else "—"

        return {"total_spent": total_spent, "transaction_count": transaction_count, "top_category": top_category}
    finally:
        conn.close()


def get_recent_transactions(user_id, limit=10):
    # SA1: return the most recent expenses for the user, newest first
    # Each item: {"date": str, "description": str, "category": str, "amount": float}
    conn = get_db()
    try:
        rows = conn.execute(
            """
            SELECT date, description, category, amount
            FROM expenses
            WHERE user_id = ?
            ORDER BY date DESC, id DESC
            LIMIT ?
            """,
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


def get_category_breakdown(user_id):
    # SA3: aggregate spend by category, ordered by amount desc
    # Each item: {"name": str, "amount": float, "pct": int}
    # pct values must sum to 100; adjust the largest category to absorb rounding error
    conn = get_db()
    try:
        rows = conn.execute(
            "SELECT category AS name, SUM(amount) AS amount FROM expenses WHERE user_id = ? GROUP BY category ORDER BY amount DESC",
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
