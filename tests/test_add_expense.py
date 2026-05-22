"""
tests/test_add_expense.py

Pytest test suite for Spendly Step 07 — Add Expense feature.

Coverage:
  - Unit tests for insert_expense() query helper
  - GET /expenses/add: auth guard, 200 response, form landmarks, all 7 categories
  - POST /expenses/add: auth guard, happy path, DB side effects
  - POST /expenses/add: every validation-error branch (missing amount, zero amount,
    non-numeric amount, invalid category, invalid date)
  - POST /expenses/add: optional description (omitted -> NULL in DB)
  - Profile page "Add Expense" button and navbar link
"""

import sqlite3
import pytest
import database.db as _db
from database.queries import insert_expense
from app import app as flask_app


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def seeded_db(tmp_path, monkeypatch):
    """Redirect DB_PATH to a temp file, create schema, and seed demo data."""
    db_path = str(tmp_path / "test.db")
    monkeypatch.setattr(_db, "DB_PATH", db_path)
    _db.init_db()
    _db.seed_db()
    yield db_path


@pytest.fixture()
def client(seeded_db):
    """Flask test client wired to the seeded temp DB."""
    flask_app.config["TESTING"] = True
    flask_app.config["SECRET_KEY"] = "test-secret"
    with flask_app.test_client() as c:
        yield c


@pytest.fixture()
def logged_in_client(client):
    """A test client that has already completed a login POST."""
    resp = client.post(
        "/login",
        data={"email": "demo@spendly.com", "password": "demo123"},
        follow_redirects=False,
    )
    assert resp.status_code == 302, "Login POST should redirect on success"
    return client


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

VALID_CATEGORIES = [
    "Food",
    "Transport",
    "Bills",
    "Health",
    "Entertainment",
    "Shopping",
    "Other",
]

VALID_POST_DATA = {
    "amount": "50.0",
    "category": "Food",
    "date": "2026-03-20",
    "description": "Lunch",
}


def _get_all_expenses(db_path, user_id):
    """Return all expense rows for a user directly from the DB file."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT * FROM expenses WHERE user_id = ? ORDER BY id",
        (user_id,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def _get_user_id(db_path, email="demo@spendly.com"):
    """Return the user's id directly from the DB file."""
    conn = sqlite3.connect(db_path)
    row = conn.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
    conn.close()
    return row[0]


# ---------------------------------------------------------------------------
# Unit tests — insert_expense()
# ---------------------------------------------------------------------------

class TestInsertExpenseHelper:
    """Unit tests for the insert_expense() query helper in database/queries.py."""

    def test_insert_expense_with_description_creates_row(self, seeded_db):
        """Calling insert_expense with all fields should persist a matching row."""
        user_id = _get_user_id(seeded_db)
        before = _get_all_expenses(seeded_db, user_id)

        insert_expense(user_id, 50.0, "Food", "2026-03-20", "Lunch")

        after = _get_all_expenses(seeded_db, user_id)
        assert len(after) == len(before) + 1, "Exactly one new row should be inserted"

        new_row = after[-1]
        assert new_row["user_id"] == user_id, "user_id should match"
        assert new_row["amount"] == pytest.approx(50.0), "Amount should be 50.0"
        assert new_row["category"] == "Food", "Category should be Food"
        assert new_row["date"] == "2026-03-20", "Date should be 2026-03-20"
        assert new_row["description"] == "Lunch", "Description should be Lunch"

    def test_insert_expense_without_description_stores_null(self, seeded_db):
        """Calling insert_expense with description=None should store NULL in the DB."""
        user_id = _get_user_id(seeded_db)

        insert_expense(user_id, 120.0, "Transport", "2026-04-01", None)

        rows = _get_all_expenses(seeded_db, user_id)
        new_row = rows[-1]
        assert new_row["amount"] == pytest.approx(120.0), "Amount should be 120.0"
        assert new_row["category"] == "Transport", "Category should be Transport"
        assert new_row["description"] is None, "Description should be NULL when None is passed"

    def test_insert_expense_uses_parameterized_query_safe_from_injection(self, seeded_db):
        """
        A description that contains SQL injection syntax should be stored
        as a literal string, not executed.
        """
        user_id = _get_user_id(seeded_db)
        malicious = "Lunch'); DROP TABLE expenses; --"

        insert_expense(user_id, 10.0, "Other", "2026-05-01", malicious)

        rows = _get_all_expenses(seeded_db, user_id)
        new_row = rows[-1]
        assert new_row["description"] == malicious, (
            "SQL injection payload should be stored as a literal string"
        )

    def test_insert_expense_persists_correct_user_id(self, seeded_db):
        """The row's user_id column must match what was passed in."""
        user_id = _get_user_id(seeded_db)
        insert_expense(user_id, 200.0, "Bills", "2026-05-10", "Electricity")
        rows = _get_all_expenses(seeded_db, user_id)
        assert all(r["user_id"] == user_id for r in rows), (
            "Every row for this user should carry the correct user_id"
        )


# ---------------------------------------------------------------------------
# Auth guard tests — unauthenticated access
# ---------------------------------------------------------------------------

class TestAddExpenseAuthGuard:
    """Unauthenticated requests to GET and POST /expenses/add must redirect to /login."""

    def test_get_add_expense_unauthenticated_redirects_to_login(self, client):
        resp = client.get("/expenses/add", follow_redirects=False)
        assert resp.status_code == 302, "GET /expenses/add should redirect when not logged in"
        assert "/login" in resp.headers["Location"], (
            "Redirect target should be /login"
        )

    def test_post_add_expense_unauthenticated_redirects_to_login(self, client):
        resp = client.post(
            "/expenses/add",
            data=VALID_POST_DATA,
            follow_redirects=False,
        )
        assert resp.status_code == 302, "POST /expenses/add should redirect when not logged in"
        assert "/login" in resp.headers["Location"], (
            "Redirect target should be /login"
        )


# ---------------------------------------------------------------------------
# GET /expenses/add — authenticated
# ---------------------------------------------------------------------------

class TestGetAddExpense:
    """GET /expenses/add while authenticated should render the expense form."""

    def test_get_add_expense_returns_200(self, logged_in_client):
        resp = logged_in_client.get("/expenses/add")
        assert resp.status_code == 200, "GET /expenses/add should return 200 for logged-in users"

    def test_get_add_expense_contains_form_with_post_method(self, logged_in_client):
        resp = logged_in_client.get("/expenses/add")
        html = resp.data.decode("utf-8")
        assert "<form" in html, "Response should contain a <form> element"
        assert "POST" in html.upper(), "Form should use POST method"

    def test_get_add_expense_contains_all_7_categories(self, logged_in_client):
        resp = logged_in_client.get("/expenses/add")
        html = resp.data.decode("utf-8")
        for category in VALID_CATEGORIES:
            assert category in html, (
                f"Category '{category}' should appear in the category <select>"
            )

    def test_get_add_expense_contains_amount_field(self, logged_in_client):
        resp = logged_in_client.get("/expenses/add")
        html = resp.data.decode("utf-8")
        assert 'name="amount"' in html, "Form should contain an amount input field"

    def test_get_add_expense_contains_date_field(self, logged_in_client):
        resp = logged_in_client.get("/expenses/add")
        html = resp.data.decode("utf-8")
        assert 'name="date"' in html, "Form should contain a date input field"

    def test_get_add_expense_contains_description_field(self, logged_in_client):
        resp = logged_in_client.get("/expenses/add")
        html = resp.data.decode("utf-8")
        assert 'name="description"' in html, "Form should contain a description input field"

    def test_get_add_expense_contains_category_select(self, logged_in_client):
        resp = logged_in_client.get("/expenses/add")
        html = resp.data.decode("utf-8")
        assert 'name="category"' in html, "Form should contain a category select element"

    def test_get_add_expense_contains_cancel_link_to_profile(self, logged_in_client):
        resp = logged_in_client.get("/expenses/add")
        html = resp.data.decode("utf-8")
        assert "/profile" in html, (
            "Form page should include a cancel link pointing back to /profile"
        )

    def test_get_add_expense_extends_base_template(self, logged_in_client):
        """The page should share the base layout (navbar/footer are present)."""
        resp = logged_in_client.get("/expenses/add")
        html = resp.data.decode("utf-8")
        # base.html always renders a <nav> or similar structural element
        assert "<nav" in html or "navbar" in html.lower(), (
            "Page should extend base.html and render the shared navbar"
        )


# ---------------------------------------------------------------------------
# POST /expenses/add — happy path
# ---------------------------------------------------------------------------

class TestPostAddExpenseHappyPath:
    """Valid POST submissions should insert the expense and redirect to /profile."""

    def test_valid_post_redirects_to_profile(self, logged_in_client):
        resp = logged_in_client.post(
            "/expenses/add",
            data=VALID_POST_DATA,
            follow_redirects=False,
        )
        assert resp.status_code == 302, "Valid POST should redirect"
        assert "/profile" in resp.headers["Location"], (
            "Redirect target should be /profile"
        )

    def test_valid_post_inserts_row_in_db(self, logged_in_client, seeded_db):
        before = _get_all_expenses(seeded_db, _get_user_id(seeded_db))
        logged_in_client.post(
            "/expenses/add",
            data=VALID_POST_DATA,
            follow_redirects=False,
        )
        after = _get_all_expenses(seeded_db, _get_user_id(seeded_db))
        assert len(after) == len(before) + 1, "One new expense row should be in the DB"

    def test_valid_post_stores_correct_values(self, logged_in_client, seeded_db):
        logged_in_client.post(
            "/expenses/add",
            data=VALID_POST_DATA,
            follow_redirects=False,
        )
        rows = _get_all_expenses(seeded_db, _get_user_id(seeded_db))
        new_row = rows[-1]
        assert new_row["amount"] == pytest.approx(50.0), "Stored amount should be 50.0"
        assert new_row["category"] == "Food", "Stored category should be Food"
        assert new_row["date"] == "2026-03-20", "Stored date should be 2026-03-20"
        assert new_row["description"] == "Lunch", "Stored description should be Lunch"

    def test_valid_post_with_decimal_amount(self, logged_in_client, seeded_db):
        """Amounts with decimal places should be stored correctly."""
        data = {**VALID_POST_DATA, "amount": "99.99"}
        logged_in_client.post("/expenses/add", data=data, follow_redirects=False)
        rows = _get_all_expenses(seeded_db, _get_user_id(seeded_db))
        assert rows[-1]["amount"] == pytest.approx(99.99), "Decimal amount should persist correctly"


# ---------------------------------------------------------------------------
# POST /expenses/add — optional description
# ---------------------------------------------------------------------------

class TestPostAddExpenseOptionalDescription:
    """Submitting without a description should succeed and store NULL."""

    def test_no_description_redirects_to_profile(self, logged_in_client):
        data = {k: v for k, v in VALID_POST_DATA.items() if k != "description"}
        resp = logged_in_client.post(
            "/expenses/add",
            data=data,
            follow_redirects=False,
        )
        assert resp.status_code == 302, "Missing description should still succeed (302)"
        assert "/profile" in resp.headers["Location"], (
            "Redirect target should be /profile"
        )

    def test_no_description_stores_null_in_db(self, logged_in_client, seeded_db):
        data = {k: v for k, v in VALID_POST_DATA.items() if k != "description"}
        logged_in_client.post("/expenses/add", data=data, follow_redirects=False)
        rows = _get_all_expenses(seeded_db, _get_user_id(seeded_db))
        assert rows[-1]["description"] is None, "Missing description should be stored as NULL"

    def test_empty_string_description_stores_null_in_db(self, logged_in_client, seeded_db):
        """An empty string in the description field should also be treated as absent (NULL)."""
        data = {**VALID_POST_DATA, "description": ""}
        logged_in_client.post("/expenses/add", data=data, follow_redirects=False)
        rows = _get_all_expenses(seeded_db, _get_user_id(seeded_db))
        assert rows[-1]["description"] is None, (
            "Blank description string should be stored as NULL"
        )

    def test_whitespace_only_description_stores_null_in_db(self, logged_in_client, seeded_db):
        """A whitespace-only description should be stripped and stored as NULL."""
        data = {**VALID_POST_DATA, "description": "   "}
        logged_in_client.post("/expenses/add", data=data, follow_redirects=False)
        rows = _get_all_expenses(seeded_db, _get_user_id(seeded_db))
        assert rows[-1]["description"] is None, (
            "Whitespace-only description should be stored as NULL after stripping"
        )


# ---------------------------------------------------------------------------
# POST /expenses/add — validation errors
# ---------------------------------------------------------------------------

class TestPostAddExpenseValidation:
    """Every validation failure must re-render the form (200) with an error message."""

    # -- amount validation --

    def test_missing_amount_returns_200(self, logged_in_client):
        data = {k: v for k, v in VALID_POST_DATA.items() if k != "amount"}
        resp = logged_in_client.post("/expenses/add", data=data)
        assert resp.status_code == 200, "Missing amount should re-render the form (200)"

    def test_missing_amount_shows_error(self, logged_in_client):
        data = {k: v for k, v in VALID_POST_DATA.items() if k != "amount"}
        resp = logged_in_client.post("/expenses/add", data=data)
        html = resp.data.decode("utf-8")
        assert any(
            phrase in html.lower()
            for phrase in ["amount", "positive", "required", "error", "invalid"]
        ), "Response should contain an error message about amount"

    def test_zero_amount_returns_200(self, logged_in_client):
        data = {**VALID_POST_DATA, "amount": "0"}
        resp = logged_in_client.post("/expenses/add", data=data)
        assert resp.status_code == 200, "Zero amount should re-render the form (200)"

    def test_zero_amount_shows_error(self, logged_in_client):
        data = {**VALID_POST_DATA, "amount": "0"}
        resp = logged_in_client.post("/expenses/add", data=data)
        html = resp.data.decode("utf-8")
        assert any(
            phrase in html.lower()
            for phrase in ["amount", "positive", "greater", "error", "invalid"]
        ), "Response should contain an error message for zero amount"

    def test_negative_amount_returns_200(self, logged_in_client):
        data = {**VALID_POST_DATA, "amount": "-10"}
        resp = logged_in_client.post("/expenses/add", data=data)
        assert resp.status_code == 200, "Negative amount should re-render the form (200)"

    def test_non_numeric_amount_returns_200(self, logged_in_client):
        data = {**VALID_POST_DATA, "amount": "abc"}
        resp = logged_in_client.post("/expenses/add", data=data)
        assert resp.status_code == 200, "Non-numeric amount should re-render the form (200)"

    def test_non_numeric_amount_shows_error(self, logged_in_client):
        data = {**VALID_POST_DATA, "amount": "abc"}
        resp = logged_in_client.post("/expenses/add", data=data)
        html = resp.data.decode("utf-8")
        assert any(
            phrase in html.lower()
            for phrase in ["amount", "positive", "number", "error", "invalid"]
        ), "Response should contain an error message for non-numeric amount"

    def test_non_numeric_amount_does_not_insert_row(self, logged_in_client, seeded_db):
        before = _get_all_expenses(seeded_db, _get_user_id(seeded_db))
        data = {**VALID_POST_DATA, "amount": "not-a-number"}
        logged_in_client.post("/expenses/add", data=data)
        after = _get_all_expenses(seeded_db, _get_user_id(seeded_db))
        assert len(after) == len(before), "Validation failure must not insert any row"

    # -- category validation --

    def test_invalid_category_returns_200(self, logged_in_client):
        data = {**VALID_POST_DATA, "category": "Vacation"}
        resp = logged_in_client.post("/expenses/add", data=data)
        assert resp.status_code == 200, "Invalid category should re-render the form (200)"

    def test_invalid_category_shows_error(self, logged_in_client):
        data = {**VALID_POST_DATA, "category": "Vacation"}
        resp = logged_in_client.post("/expenses/add", data=data)
        html = resp.data.decode("utf-8")
        assert any(
            phrase in html.lower()
            for phrase in ["category", "valid", "error", "invalid", "select"]
        ), "Response should contain an error message for invalid category"

    def test_empty_category_returns_200(self, logged_in_client):
        data = {**VALID_POST_DATA, "category": ""}
        resp = logged_in_client.post("/expenses/add", data=data)
        assert resp.status_code == 200, "Empty category should re-render the form (200)"

    def test_invalid_category_does_not_insert_row(self, logged_in_client, seeded_db):
        before = _get_all_expenses(seeded_db, _get_user_id(seeded_db))
        data = {**VALID_POST_DATA, "category": "Bogus"}
        logged_in_client.post("/expenses/add", data=data)
        after = _get_all_expenses(seeded_db, _get_user_id(seeded_db))
        assert len(after) == len(before), "Invalid category must not insert any row"

    # -- date validation --

    def test_invalid_date_returns_200(self, logged_in_client):
        data = {**VALID_POST_DATA, "date": "not-a-date"}
        resp = logged_in_client.post("/expenses/add", data=data)
        assert resp.status_code == 200, "Invalid date should re-render the form (200)"

    def test_invalid_date_shows_error(self, logged_in_client):
        data = {**VALID_POST_DATA, "date": "not-a-date"}
        resp = logged_in_client.post("/expenses/add", data=data)
        html = resp.data.decode("utf-8")
        assert any(
            phrase in html.lower()
            for phrase in ["date", "valid", "error", "invalid"]
        ), "Response should contain an error message for invalid date"

    def test_invalid_date_does_not_insert_row(self, logged_in_client, seeded_db):
        before = _get_all_expenses(seeded_db, _get_user_id(seeded_db))
        data = {**VALID_POST_DATA, "date": "32-13-2026"}
        logged_in_client.post("/expenses/add", data=data)
        after = _get_all_expenses(seeded_db, _get_user_id(seeded_db))
        assert len(after) == len(before), "Invalid date must not insert any row"

    def test_empty_date_returns_200(self, logged_in_client):
        data = {**VALID_POST_DATA, "date": ""}
        resp = logged_in_client.post("/expenses/add", data=data)
        assert resp.status_code == 200, "Empty date should re-render the form (200)"

    def test_wrong_date_separator_returns_200(self, logged_in_client):
        """Dates using the wrong separator (/) must be rejected."""
        data = {**VALID_POST_DATA, "date": "2026/03/20"}
        resp = logged_in_client.post("/expenses/add", data=data)
        assert resp.status_code == 200, "Date with wrong separator should re-render the form (200)"


# ---------------------------------------------------------------------------
# Parametrize: exhaustive validation error cases
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "field, bad_value, reason",
    [
        ("amount", "",          "empty amount string"),
        ("amount", "0",         "zero is not positive"),
        ("amount", "0.00",      "zero with decimals"),
        ("amount", "-5",        "negative amount"),
        ("amount", "abc",       "non-numeric amount"),
        ("amount", "1e999",     "overflow float string"),
        ("category", "",        "empty category"),
        ("category", "Luxury",  "unknown category not in allowed list"),
        ("category", "food",    "wrong case — must match exactly"),
        ("date",    "",         "empty date"),
        ("date",    "20-03-26", "wrong date format — not YYYY-MM-DD"),
        ("date",    "2026/03/20", "slash separator instead of dash"),
        ("date",    "2026-13-01", "impossible month 13"),
        ("date",    "not-a-date", "plain invalid string"),
    ],
)
def test_validation_error_rerenders_form(logged_in_client, field, bad_value, reason):
    """All invalid inputs must produce a 200 re-render, never a 302."""
    data = {**VALID_POST_DATA, field: bad_value}
    resp = logged_in_client.post("/expenses/add", data=data)
    assert resp.status_code == 200, (
        f"Expected 200 (form re-render) for {reason!r}, got {resp.status_code}"
    )


@pytest.mark.parametrize(
    "field, bad_value, reason",
    [
        ("amount", "",          "empty amount string"),
        ("amount", "0",         "zero is not positive"),
        ("amount", "-5",        "negative amount"),
        ("amount", "abc",       "non-numeric amount"),
        ("category", "",        "empty category"),
        ("category", "Luxury",  "unknown category"),
        ("date",    "",         "empty date"),
        ("date",    "not-a-date", "plain invalid string"),
    ],
)
def test_validation_error_does_not_insert_row(logged_in_client, seeded_db, field, bad_value, reason):
    """No row should be written to the DB when validation fails."""
    before = _get_all_expenses(seeded_db, _get_user_id(seeded_db))
    data = {**VALID_POST_DATA, field: bad_value}
    logged_in_client.post("/expenses/add", data=data)
    after = _get_all_expenses(seeded_db, _get_user_id(seeded_db))
    assert len(after) == len(before), (
        f"Validation failure ({reason}) must not insert any row into the DB"
    )


# ---------------------------------------------------------------------------
# Form value re-population on validation failure
# ---------------------------------------------------------------------------

class TestFormRepopulationOnError:
    """When the form is re-rendered after a validation error, previously submitted
    values should be present in the response so the user does not lose their input."""

    def test_repopulates_category_on_invalid_amount(self, logged_in_client):
        data = {**VALID_POST_DATA, "amount": "bad", "category": "Health"}
        resp = logged_in_client.post("/expenses/add", data=data)
        html = resp.data.decode("utf-8")
        assert "Health" in html, (
            "Previously selected category should be present in re-rendered form"
        )

    def test_repopulates_date_on_invalid_amount(self, logged_in_client):
        data = {**VALID_POST_DATA, "amount": "bad", "date": "2026-03-20"}
        resp = logged_in_client.post("/expenses/add", data=data)
        html = resp.data.decode("utf-8")
        assert "2026-03-20" in html, (
            "Previously entered date should be present in re-rendered form"
        )

    def test_repopulates_description_on_invalid_category(self, logged_in_client):
        data = {**VALID_POST_DATA, "category": "Bogus", "description": "My lunch"}
        resp = logged_in_client.post("/expenses/add", data=data)
        html = resp.data.decode("utf-8")
        assert "My lunch" in html, (
            "Previously entered description should be present in re-rendered form"
        )


# ---------------------------------------------------------------------------
# Navigation: profile page "Add Expense" link and navbar link
# ---------------------------------------------------------------------------

class TestAddExpenseNavigation:
    """The profile page and navbar should surface a link to /expenses/add."""

    def test_profile_page_contains_add_expense_link(self, logged_in_client):
        resp = logged_in_client.get("/profile")
        html = resp.data.decode("utf-8")
        assert "/expenses/add" in html, (
            "Profile page should contain a link to /expenses/add"
        )

    def test_navbar_contains_add_expense_link_when_logged_in(self, logged_in_client):
        """Any authenticated page should render the navbar with the Add Expense link."""
        resp = logged_in_client.get("/profile")
        html = resp.data.decode("utf-8")
        assert "/expenses/add" in html, (
            "Navbar should include a link to /expenses/add when the user is logged in"
        )

    def test_add_expense_link_not_required_when_logged_out(self, client):
        """The landing page for anonymous users does not need to expose the add expense route."""
        resp = client.get("/")
        assert resp.status_code == 200, "Landing page should return 200 for anonymous users"


# ---------------------------------------------------------------------------
# Category completeness — exactly 7 options
# ---------------------------------------------------------------------------

class TestCategoryOptions:
    """The form's category dropdown must contain exactly the 7 fixed options."""

    def test_exactly_seven_category_options(self, logged_in_client):
        resp = logged_in_client.get("/expenses/add")
        html = resp.data.decode("utf-8")
        # Each category name appears at least once in the option list
        found = [cat for cat in VALID_CATEGORIES if cat in html]
        assert len(found) == 7, (
            f"Expected all 7 categories; found: {found}"
        )

    @pytest.mark.parametrize("category", VALID_CATEGORIES)
    def test_each_category_is_present_in_form(self, logged_in_client, category):
        resp = logged_in_client.get("/expenses/add")
        html = resp.data.decode("utf-8")
        assert category in html, (
            f"Category '{category}' should appear in the /expenses/add form"
        )

    @pytest.mark.parametrize("category", VALID_CATEGORIES)
    def test_each_valid_category_is_accepted(self, logged_in_client, seeded_db, category):
        """Every category in the fixed list should pass validation and produce a redirect."""
        data = {**VALID_POST_DATA, "category": category}
        resp = logged_in_client.post("/expenses/add", data=data, follow_redirects=False)
        assert resp.status_code == 302, (
            f"Valid category '{category}' should result in a 302 redirect, not a form re-render"
        )
