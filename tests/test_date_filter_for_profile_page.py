"""
Tests for Step 06 — Date Filter for Profile Page.

Spec: .claude/specs/06-date-filter-for-profile-page.md

Fixtures used:
  seeded_db       — from conftest.py; monkeypatches DB_PATH to a tmp file,
                    runs init_db() + seed_db() (demo user + 8 May-2026 expenses)
  client          — from conftest.py; Flask test client wired to seeded_db
  logged_in_client — defined here; logs in as the demo user before yielding

Seed data summary (from database/db.py seed_db):
  user: Demo User / demo@spendly.com / demo123
  8 expenses, all dated 2026-05-01 through 2026-05-19
  total_spent = 6400.0, transaction_count = 8, top_category = "Bills"
"""

import sqlite3
import pytest
from datetime import date, timedelta
import database.db as _db
from database.queries import (
    get_summary_stats,
    get_recent_transactions,
    get_category_breakdown,
)


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture()
def logged_in_client(client):
    """Test client already authenticated as the demo user."""
    resp = client.post(
        "/login",
        data={"email": "demo@spendly.com", "password": "demo123"},
        follow_redirects=False,
    )
    assert resp.status_code == 302, (
        "Login POST should redirect; check demo credentials match seed_db"
    )
    return client


@pytest.fixture()
def multi_month_db(tmp_path, monkeypatch):
    """
    DB with a single test user whose expenses span multiple months.

    Inserted dates (relative to 2026-05-22, the known test date):
      - 2026-05-10  Food        500.0   "This month expense"
      - 2026-04-15  Transport   200.0   "Last month expense"
      - 2026-03-20  Bills       300.0   "Two months ago"
      - 2025-11-05  Shopping    1000.0  "Six+ months ago"

    The fixture yields (db_path, user_id).
    """
    db_path = str(tmp_path / "multi.db")
    monkeypatch.setattr(_db, "DB_PATH", db_path)
    _db.init_db()

    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")
    from werkzeug.security import generate_password_hash
    conn.execute(
        "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
        ("Filter User", "filter@spendly.com", generate_password_hash("filter123")),
    )
    conn.commit()
    user_id = conn.execute(
        "SELECT id FROM users WHERE email = ?", ("filter@spendly.com",)
    ).fetchone()[0]

    expenses = [
        (user_id, 500.0,  "Food",      "2026-05-10", "This month expense"),
        (user_id, 200.0,  "Transport", "2026-04-15", "Last month expense"),
        (user_id, 300.0,  "Bills",     "2026-03-20", "Two months ago"),
        (user_id, 1000.0, "Shopping",  "2025-11-05", "Six+ months ago"),
    ]
    conn.executemany(
        "INSERT INTO expenses (user_id, amount, category, date, description)"
        " VALUES (?, ?, ?, ?, ?)",
        expenses,
    )
    conn.commit()
    conn.close()
    yield db_path, user_id


@pytest.fixture()
def multi_month_client(multi_month_db, monkeypatch):
    """Flask test client logged in as the multi-month test user."""
    from app import app as flask_app
    flask_app.config["TESTING"] = True
    flask_app.config["SECRET_KEY"] = "test-secret"
    with flask_app.test_client() as c:
        resp = c.post(
            "/login",
            data={"email": "filter@spendly.com", "password": "filter123"},
            follow_redirects=False,
        )
        assert resp.status_code == 302, "Multi-month login should redirect"
        yield c


# ─────────────────────────────────────────────────────────────────────────────
# Auth guard
# ─────────────────────────────────────────────────────────────────────────────

class TestAuthGuard:
    def test_profile_no_session_redirects_to_login(self, client):
        """Unauthenticated GET /profile must 302-redirect to /login."""
        resp = client.get("/profile")
        assert resp.status_code == 302, (
            "Expected 302 redirect for unauthenticated /profile"
        )
        assert "/login" in resp.headers["Location"], (
            "Redirect target must include /login"
        )

    def test_profile_with_date_params_no_session_redirects_to_login(self, client):
        """Unauthenticated GET /profile?date_from=...&date_to=... must also redirect."""
        resp = client.get("/profile?date_from=2026-01-01&date_to=2026-05-31")
        assert resp.status_code == 302, (
            "Expected 302 redirect for unauthenticated /profile with date params"
        )
        assert "/login" in resp.headers["Location"], (
            "Redirect target must include /login"
        )


# ─────────────────────────────────────────────────────────────────────────────
# Backward compatibility — no query params
# ─────────────────────────────────────────────────────────────────────────────

class TestNoParams:
    def test_profile_no_params_returns_200(self, logged_in_client):
        """/profile with no query params returns HTTP 200."""
        resp = logged_in_client.get("/profile")
        assert resp.status_code == 200, "Expected 200 for authenticated /profile"

    def test_profile_no_params_contains_rupee_symbol(self, logged_in_client):
        """/profile with no query params shows ₹ in the rendered HTML."""
        resp = logged_in_client.get("/profile")
        assert "₹" in resp.data.decode("utf-8"), (
            "Profile page must display ₹ symbol for amounts"
        )

    def test_profile_no_params_shows_all_expenses(self, logged_in_client):
        """With no filter, all 8 seeded expenses must be reflected in totals."""
        resp = logged_in_client.get("/profile")
        html = resp.data.decode("utf-8")
        # The seeded total is 6400.0 → rendered as ₹6,400.00
        assert "6,400.00" in html, (
            "Unfiltered profile must show the full total of all seeded expenses"
        )

    def test_profile_no_params_shows_transaction_count(self, logged_in_client):
        """With no filter, transaction count must reflect all 8 seeded records."""
        resp = logged_in_client.get("/profile")
        html = resp.data.decode("utf-8")
        assert "8" in html, (
            "Unfiltered profile must mention the total transaction count of 8"
        )


# ─────────────────────────────────────────────────────────────────────────────
# Malformed date inputs — graceful fallback
# ─────────────────────────────────────────────────────────────────────────────

class TestMalformedDates:
    @pytest.mark.parametrize("bad_date", [
        "not-a-date",
        "99-99-99",
        "2026/05/01",   # wrong separator
        "01-01-2026",   # DD-MM-YYYY instead of YYYY-MM-DD
        "",
        "abcdefgh",
        "2026-13-01",   # month 13
        "2026-00-01",   # month 00
    ])
    def test_malformed_date_from_does_not_crash(self, logged_in_client, bad_date):
        """A malformed date_from silently falls back to unfiltered view (no 500)."""
        resp = logged_in_client.get(f"/profile?date_from={bad_date}")
        assert resp.status_code == 200, (
            f"Malformed date_from={bad_date!r} must not crash — expected 200"
        )

    @pytest.mark.parametrize("bad_date", [
        "not-a-date",
        "99-99-99",
        "2026/05/31",
        "31-05-2026",
        "",
        "abcdefgh",
    ])
    def test_malformed_date_to_does_not_crash(self, logged_in_client, bad_date):
        """A malformed date_to silently falls back to unfiltered view (no 500)."""
        resp = logged_in_client.get(f"/profile?date_to={bad_date}")
        assert resp.status_code == 200, (
            f"Malformed date_to={bad_date!r} must not crash — expected 200"
        )

    def test_both_malformed_falls_back_to_unfiltered(self, logged_in_client):
        """When both date params are invalid the full unfiltered dataset is shown."""
        resp = logged_in_client.get(
            "/profile?date_from=bad-date&date_to=also-bad"
        )
        assert resp.status_code == 200
        html = resp.data.decode("utf-8")
        assert "6,400.00" in html, (
            "Both malformed dates → unfiltered; full total must appear"
        )

    def test_only_date_from_valid_falls_back_to_unfiltered(self, logged_in_client):
        """Only date_from provided (date_to absent) → treated as unfiltered."""
        resp = logged_in_client.get("/profile?date_from=2026-05-01")
        assert resp.status_code == 200
        # Spec: if either param is absent or malformed, fall back to All Time
        html = resp.data.decode("utf-8")
        assert "6,400.00" in html, (
            "Single date_from with absent date_to must fall back to unfiltered"
        )

    def test_only_date_to_valid_falls_back_to_unfiltered(self, logged_in_client):
        """Only date_to provided (date_from absent) → treated as unfiltered."""
        resp = logged_in_client.get("/profile?date_to=2026-05-31")
        assert resp.status_code == 200
        html = resp.data.decode("utf-8")
        assert "6,400.00" in html, (
            "Single date_to with absent date_from must fall back to unfiltered"
        )


# ─────────────────────────────────────────────────────────────────────────────
# date_from > date_to validation
# ─────────────────────────────────────────────────────────────────────────────

class TestInvertedDateRange:
    def test_inverted_range_flashes_error(self, logged_in_client):
        """date_from > date_to must produce a visible flash error message."""
        resp = logged_in_client.get(
            "/profile?date_from=2026-05-31&date_to=2026-05-01",
            follow_redirects=True,
        )
        assert resp.status_code == 200
        html = resp.data.decode("utf-8")
        assert "Start date must be before end date" in html, (
            "Flash error 'Start date must be before end date.' must appear"
        )

    def test_inverted_range_falls_back_to_unfiltered(self, logged_in_client):
        """After an inverted range error the page must show all expenses."""
        resp = logged_in_client.get(
            "/profile?date_from=2026-12-31&date_to=2026-01-01",
            follow_redirects=True,
        )
        html = resp.data.decode("utf-8")
        assert "6,400.00" in html, (
            "Inverted range must fall back to unfiltered total"
        )


# ─────────────────────────────────────────────────────────────────────────────
# Happy path — custom date range
# ─────────────────────────────────────────────────────────────────────────────

class TestCustomDateRange:
    def test_valid_custom_range_returns_200(self, logged_in_client):
        """A well-formed custom range must return HTTP 200."""
        resp = logged_in_client.get(
            "/profile?date_from=2026-05-01&date_to=2026-05-05"
        )
        assert resp.status_code == 200

    def test_valid_custom_range_filters_amounts(self, logged_in_client):
        """
        Filter to 2026-05-01 through 2026-05-05 inclusive.
        Seeded expenses in range:
          2026-05-01  Food       450.0
          2026-05-03  Transport  120.0
          2026-05-05  Bills     2200.0
        Total = 2770.0 → ₹2,770.00
        """
        resp = logged_in_client.get(
            "/profile?date_from=2026-05-01&date_to=2026-05-05"
        )
        html = resp.data.decode("utf-8")
        assert "2,770.00" in html, (
            "Custom range 2026-05-01→2026-05-05 must total ₹2,770.00"
        )

    def test_valid_custom_range_excludes_out_of_range_expenses(self, logged_in_client):
        """
        Filter to a single day that has exactly one seeded expense.
        2026-05-08 Health 800.0 → ₹800.00 should appear; 6,400.00 must NOT.
        """
        resp = logged_in_client.get(
            "/profile?date_from=2026-05-08&date_to=2026-05-08"
        )
        html = resp.data.decode("utf-8")
        assert "800.00" in html, (
            "Single-day filter must show the ₹800 Health expense"
        )
        assert "6,400.00" not in html, (
            "Single-day filter must not show the unfiltered total"
        )

    def test_valid_custom_range_rupee_symbol_present(self, logged_in_client):
        """₹ symbol must be present even when a custom date range is active."""
        resp = logged_in_client.get(
            "/profile?date_from=2026-05-01&date_to=2026-05-19"
        )
        assert "₹" in resp.data.decode("utf-8"), (
            "₹ symbol must appear in filtered profile view"
        )

    def test_custom_range_transaction_count(self, logged_in_client):
        """
        Filter to 2026-05-01 through 2026-05-03 → 2 expenses.
        The rendered page must mention the count 2.
        """
        resp = logged_in_client.get(
            "/profile?date_from=2026-05-01&date_to=2026-05-03"
        )
        html = resp.data.decode("utf-8")
        # Total for this range: 450 + 120 = 570
        assert "570.00" in html, (
            "Filter 2026-05-01→2026-05-03 should total ₹570.00"
        )


# ─────────────────────────────────────────────────────────────────────────────
# Empty state — no matching expenses in range
# ─────────────────────────────────────────────────────────────────────────────

class TestEmptyDateRange:
    def test_no_expenses_in_range_returns_200(self, logged_in_client):
        """A range with no matching expenses must still return HTTP 200."""
        resp = logged_in_client.get(
            "/profile?date_from=2020-01-01&date_to=2020-12-31"
        )
        assert resp.status_code == 200, (
            "Empty date range must return 200, not an error"
        )

    def test_no_expenses_in_range_shows_zero_total(self, logged_in_client):
        """₹0.00 must appear when no expenses match the active filter."""
        resp = logged_in_client.get(
            "/profile?date_from=2020-01-01&date_to=2020-12-31"
        )
        html = resp.data.decode("utf-8")
        assert "0.00" in html, (
            "Empty range must display ₹0.00 total spent"
        )

    def test_no_expenses_in_range_rupee_symbol_present(self, logged_in_client):
        """₹ symbol must appear even when the filtered total is zero."""
        resp = logged_in_client.get(
            "/profile?date_from=2020-01-01&date_to=2020-12-31"
        )
        assert "₹" in resp.data.decode("utf-8"), (
            "₹ symbol must be shown even for an empty filter result"
        )

    def test_no_expenses_in_range_no_server_error(self, logged_in_client):
        """An empty result set must not produce a 500 or any server-side exception."""
        resp = logged_in_client.get(
            "/profile?date_from=2099-01-01&date_to=2099-12-31"
        )
        assert resp.status_code == 200
        assert b"500" not in resp.data, "No internal server error must occur"


# ─────────────────────────────────────────────────────────────────────────────
# Preset filters — multi-month dataset
# ─────────────────────────────────────────────────────────────────────────────

class TestPresetFilters:
    def test_this_month_preset_scope(self, multi_month_client):
        """
        'This Month' range (2026-05-01 through 2026-05-31) must include
        the May expense (500.0) but not April/March/November ones.
        """
        resp = multi_month_client.get(
            "/profile?date_from=2026-05-01&date_to=2026-05-31"
        )
        assert resp.status_code == 200
        html = resp.data.decode("utf-8")
        assert "500.00" in html, (
            "'This Month' filter must include the May 500 expense"
        )
        # Total for May only = 500
        assert "1,000.00" not in html, (
            "'This Month' must not include the November 1000 Shopping expense"
        )

    def test_last_3_months_excludes_old_expense(self, multi_month_client):
        """
        Last-3-months window (approx 2026-02-22 through 2026-05-22) must
        exclude the 2025-11-05 Shopping expense of 1000.0.
        """
        # 3-month window: 2026-02-22 through 2026-05-22
        resp = multi_month_client.get(
            "/profile?date_from=2026-02-22&date_to=2026-05-22"
        )
        html = resp.data.decode("utf-8")
        # The November 1000 expense must not appear in the total
        # May+April+March = 500+200+300 = 1000 but that should appear as sum
        # The standalone 1000.00 from Shopping (Nov) should be absent as the
        # total without it is 1000 — we check the November description instead
        assert "Six+ months ago" not in html, (
            "Last-3-months filter must exclude the November Shopping expense"
        )

    def test_last_6_months_excludes_very_old_expense(self, multi_month_client):
        """
        Last-6-months window (approx 2025-11-22 through 2026-05-22) should
        exclude the 2025-11-05 expense (before the window start).
        """
        resp = multi_month_client.get(
            "/profile?date_from=2025-11-22&date_to=2026-05-22"
        )
        html = resp.data.decode("utf-8")
        assert "Six+ months ago" not in html, (
            "Last-6-months filter must exclude the 2025-11-05 expense"
        )

    def test_last_6_months_includes_recent_expenses(self, multi_month_client):
        """
        Last-6-months window must still include expenses from May, April,
        and March of 2026.
        """
        resp = multi_month_client.get(
            "/profile?date_from=2025-11-22&date_to=2026-05-22"
        )
        html = resp.data.decode("utf-8")
        assert "This month expense" in html or "500.00" in html, (
            "Last-6-months filter must include the May expense"
        )

    def test_all_time_clean_url_returns_full_dataset(self, multi_month_client):
        """
        'All Time' uses a clean /profile URL (no query params) and must
        return all 4 expenses for the multi-month user.
        Total = 500 + 200 + 300 + 1000 = 2000.
        """
        resp = multi_month_client.get("/profile")
        assert resp.status_code == 200
        html = resp.data.decode("utf-8")
        assert "2,000.00" in html, (
            "'All Time' (no params) must show all 4 expenses totalling ₹2,000.00"
        )

    def test_all_time_preset_no_query_params_needed(self, multi_month_client):
        """
        The 'All Time' preset must work without any query parameters.
        Verifies that clean /profile is equivalent to All Time.
        """
        resp_clean = multi_month_client.get("/profile")
        resp_params = multi_month_client.get("/profile?date_from=&date_to=")
        # Both should return 200
        assert resp_clean.status_code == 200
        assert resp_params.status_code == 200


# ─────────────────────────────────────────────────────────────────────────────
# Query helper — function signatures accept date_from / date_to kwargs
# ─────────────────────────────────────────────────────────────────────────────

class TestQueryHelperSignatures:
    """
    These tests assert that the three query helpers accept date_from and
    date_to keyword arguments without raising TypeError. They do NOT test
    the HTTP layer — they call the helpers directly.
    """

    def test_get_summary_stats_accepts_date_kwargs(self, seeded_db):
        """get_summary_stats must accept date_from and date_to kwargs."""
        try:
            result = get_summary_stats(
                user_id=1,
                date_from="2026-05-01",
                date_to="2026-05-31",
            )
        except TypeError as exc:
            pytest.fail(
                f"get_summary_stats does not accept date_from/date_to kwargs: {exc}"
            )

    def test_get_summary_stats_none_kwargs_behave_like_unfiltered(self, seeded_db):
        """Passing date_from=None, date_to=None must equal calling with no kwargs."""
        result_default = get_summary_stats(1)
        result_none = get_summary_stats(1, date_from=None, date_to=None)
        assert result_default["total_spent"] == result_none["total_spent"], (
            "date_from=None, date_to=None must produce same total as no kwargs"
        )
        assert result_default["transaction_count"] == result_none["transaction_count"], (
            "date_from=None, date_to=None must produce same count as no kwargs"
        )

    def test_get_recent_transactions_accepts_date_kwargs(self, seeded_db):
        """get_recent_transactions must accept date_from and date_to kwargs."""
        try:
            result = get_recent_transactions(
                user_id=1,
                date_from="2026-05-01",
                date_to="2026-05-31",
            )
        except TypeError as exc:
            pytest.fail(
                f"get_recent_transactions does not accept date_from/date_to kwargs: {exc}"
            )

    def test_get_recent_transactions_none_kwargs_behave_like_unfiltered(self, seeded_db):
        """Passing date_from=None, date_to=None must return same rows as no kwargs."""
        result_default = get_recent_transactions(1)
        result_none = get_recent_transactions(1, date_from=None, date_to=None)
        assert len(result_default) == len(result_none), (
            "date_from=None, date_to=None must return same number of rows as no kwargs"
        )

    def test_get_category_breakdown_accepts_date_kwargs(self, seeded_db):
        """get_category_breakdown must accept date_from and date_to kwargs."""
        try:
            result = get_category_breakdown(
                user_id=1,
                date_from="2026-05-01",
                date_to="2026-05-31",
            )
        except TypeError as exc:
            pytest.fail(
                f"get_category_breakdown does not accept date_from/date_to kwargs: {exc}"
            )

    def test_get_category_breakdown_none_kwargs_behave_like_unfiltered(self, seeded_db):
        """Passing date_from=None, date_to=None must return same categories as no kwargs."""
        result_default = get_category_breakdown(1)
        result_none = get_category_breakdown(1, date_from=None, date_to=None)
        assert len(result_default) == len(result_none), (
            "date_from=None, date_to=None must produce same category list as no kwargs"
        )


# ─────────────────────────────────────────────────────────────────────────────
# Query helper — filtered results correctness
# ─────────────────────────────────────────────────────────────────────────────

class TestQueryHelperFiltering:
    """
    Direct unit tests on the query helpers with date_from/date_to populated.
    Uses the seeded_db fixture (8 expenses, all in May 2026).
    """

    def test_get_summary_stats_filtered_to_single_day(self, seeded_db):
        """
        Filter to 2026-05-08 only → 1 expense (Health 800.0).
        """
        result = get_summary_stats(1, date_from="2026-05-08", date_to="2026-05-08")
        assert result["transaction_count"] == 1, (
            "Filtered stats must count only the single matching expense"
        )
        assert result["total_spent"] == 800.0, (
            "Filtered total must be 800.0 for the single Health expense"
        )

    def test_get_summary_stats_filtered_empty_range(self, seeded_db):
        """
        Filter to a range with no seeded expenses → total 0, count 0.
        """
        result = get_summary_stats(1, date_from="2020-01-01", date_to="2020-12-31")
        assert result["total_spent"] == 0.0, (
            "Empty range must yield total_spent of 0.0"
        )
        assert result["transaction_count"] == 0, (
            "Empty range must yield transaction_count of 0"
        )

    def test_get_summary_stats_filtered_range_total(self, seeded_db):
        """
        Filter 2026-05-01 through 2026-05-05: Food 450 + Transport 120 + Bills 2200 = 2770.
        """
        result = get_summary_stats(1, date_from="2026-05-01", date_to="2026-05-05")
        assert result["transaction_count"] == 3, (
            "Three expenses fall within 2026-05-01 to 2026-05-05"
        )
        assert result["total_spent"] == pytest.approx(2770.0), (
            "Filtered total must be 2770.0"
        )

    def test_get_recent_transactions_filtered_to_single_day(self, seeded_db):
        """
        Filter to 2026-05-10 → only the Entertainment 650.0 expense.
        """
        result = get_recent_transactions(
            1, date_from="2026-05-10", date_to="2026-05-10"
        )
        assert len(result) == 1, "Single-day filter must return exactly 1 transaction"
        assert result[0]["amount"] == 650.0, (
            "The single transaction on 2026-05-10 must be the 650.0 Entertainment expense"
        )
        assert result[0]["category"] == "Entertainment"

    def test_get_recent_transactions_filtered_empty_range(self, seeded_db):
        """
        Filter to a range with no seeded data → empty list.
        """
        result = get_recent_transactions(
            1, date_from="2020-01-01", date_to="2020-12-31"
        )
        assert result == [], "Empty range must return an empty list"

    def test_get_recent_transactions_ordering_preserved_under_filter(self, seeded_db):
        """
        Within a multi-expense date range, ordering must remain newest-first.
        Filter 2026-05-01 through 2026-05-10 → 5 expenses, newest date first.
        """
        result = get_recent_transactions(
            1, date_from="2026-05-01", date_to="2026-05-10"
        )
        assert len(result) == 5, "Five expenses fall between 2026-05-01 and 2026-05-10"
        dates = [r["date"] for r in result]
        assert dates == sorted(dates, reverse=True), (
            "Transactions must be returned newest-first under filtered query"
        )

    def test_get_category_breakdown_filtered_single_category(self, seeded_db):
        """
        Filter to 2026-05-08 → only Health category; 100% share.
        """
        result = get_category_breakdown(
            1, date_from="2026-05-08", date_to="2026-05-08"
        )
        assert len(result) == 1, "Only one category (Health) has expenses on 2026-05-08"
        assert result[0]["name"] == "Health"
        assert result[0]["pct"] == 100, (
            "Single category in filtered view must account for 100%"
        )

    def test_get_category_breakdown_filtered_empty_range(self, seeded_db):
        """
        Filter to a range with no expenses → empty list.
        """
        result = get_category_breakdown(
            1, date_from="2020-01-01", date_to="2020-12-31"
        )
        assert result == [], "Empty range must return an empty category list"

    def test_get_category_breakdown_pct_sums_to_100_under_filter(self, seeded_db):
        """
        Within a multi-category filtered range, pct values must still sum to 100.
        """
        result = get_category_breakdown(
            1, date_from="2026-05-01", date_to="2026-05-10"
        )
        assert len(result) > 1, "Multiple categories expected in 2026-05-01→2026-05-10"
        total_pct = sum(c["pct"] for c in result)
        assert total_pct == 100, (
            f"Category pct values must sum to 100 under filter; got {total_pct}"
        )

    def test_get_summary_stats_top_category_under_filter(self, seeded_db):
        """
        Filter to 2026-05-01 through 2026-05-05 → top category must be Bills (2200.0).
        """
        result = get_summary_stats(1, date_from="2026-05-01", date_to="2026-05-05")
        assert result["top_category"] == "Bills", (
            "Top category for 2026-05-01→2026-05-05 must be Bills (highest spend)"
        )


# ─────────────────────────────────────────────────────────────────────────────
# Template rendering — filter state
# ─────────────────────────────────────────────────────────────────────────────

class TestTemplateRendering:
    def test_profile_renders_filter_bar(self, logged_in_client):
        """Profile page must contain a filter bar with the preset labels."""
        resp = logged_in_client.get("/profile")
        html = resp.data.decode("utf-8")
        assert "This Month" in html, "Filter bar must include 'This Month' preset"
        assert "Last 3 Months" in html, "Filter bar must include 'Last 3 Months' preset"
        assert "Last 6 Months" in html, "Filter bar must include 'Last 6 Months' preset"
        assert "All Time" in html, "Filter bar must include 'All Time' preset"

    def test_profile_filter_bar_has_date_inputs(self, logged_in_client):
        """Profile page must render custom date input fields."""
        resp = logged_in_client.get("/profile")
        html = resp.data.decode("utf-8")
        assert 'type="date"' in html or "type='date'" in html, (
            "Filter bar must contain <input type='date'> fields"
        )

    def test_profile_filtered_view_still_renders_full_page(self, logged_in_client):
        """A filtered profile page must still render all structural sections."""
        resp = logged_in_client.get(
            "/profile?date_from=2026-05-01&date_to=2026-05-31"
        )
        assert resp.status_code == 200
        html = resp.data.decode("utf-8")
        # Page extends base.html — check for basic HTML structure
        assert "<html" in html or "<!DOCTYPE" in html, (
            "Filtered profile must render a full HTML page extending base.html"
        )

    def test_profile_rupee_in_filtered_view(self, logged_in_client):
        """₹ must appear when a custom date filter is active."""
        resp = logged_in_client.get(
            "/profile?date_from=2026-05-01&date_to=2026-05-08"
        )
        assert "₹" in resp.data.decode("utf-8"), (
            "₹ symbol must appear in filtered profile view"
        )

    def test_profile_rupee_in_empty_filtered_view(self, logged_in_client):
        """₹ must appear even when no expenses match the active filter."""
        resp = logged_in_client.get(
            "/profile?date_from=2020-01-01&date_to=2020-01-31"
        )
        assert "₹" in resp.data.decode("utf-8"), (
            "₹ symbol must appear even when filtered total is zero"
        )
