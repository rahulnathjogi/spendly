"""
Tests for database/queries.py and the GET /profile route.

Fixtures come from conftest.py:
  seeded_db  — monkeypatches DB_PATH to a tmp file, runs init_db()+seed_db()
  client     — Flask test client bound to the seeded temp DB

Seed data (from database/db.py seed_db):
  user: Demo User  /  demo@spendly.com  /  demo123
  8 expenses across 7 categories; Bills is the top category by spend
"""

import sqlite3
import pytest
from database.queries import (
    get_user_by_id,
    get_summary_stats,
    get_recent_transactions,
    get_category_breakdown,
)


# ── SA2: get_user_by_id ───────────────────────────────────────────────────────

def test_get_user_by_id_valid(seeded_db):
    pass  # TODO(SA2): fetch demo user by id, assert name/email/member_since


def test_get_user_by_id_missing(seeded_db):
    pass  # TODO(SA2): non-existent id returns None


# ── SA2: get_summary_stats ────────────────────────────────────────────────────

def test_get_summary_stats_with_expenses(seeded_db):
    pass  # TODO(SA2): seed user has 8 expenses; assert count, top_category, total_spent > 0


def test_get_summary_stats_no_expenses(seeded_db):
    pass  # TODO(SA2): fresh user with no expenses returns zeros and "—"


# ── SA2: GET /profile route ───────────────────────────────────────────────────

def test_profile_unauthenticated(client):
    pass  # TODO(SA2): GET /profile without session → 302 redirect to /login


def test_profile_authenticated(client, seeded_db):
    pass  # TODO(SA2): set session user_id, GET /profile → 200, contains name/email/₹


# ── SA1: get_recent_transactions ─────────────────────────────────────────────

def test_get_recent_transactions_with_expenses(seeded_db):
    pass  # TODO(SA1): seed user → 8 items, newest date first, each has date/description/category/amount


def test_get_recent_transactions_no_expenses(seeded_db):
    pass  # TODO(SA1): fresh user → empty list


# ── SA3: get_category_breakdown ──────────────────────────────────────────────

def test_get_category_breakdown_with_expenses(seeded_db):
    pass  # TODO(SA3): seed user → 7 categories, ordered by amount desc


def test_get_category_breakdown_no_expenses(seeded_db):
    pass  # TODO(SA3): fresh user → empty list


def test_get_category_breakdown_pct_sums_to_100(seeded_db):
    pass  # TODO(SA3): pct values across all categories must sum exactly to 100
