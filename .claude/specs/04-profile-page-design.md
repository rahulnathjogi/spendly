# Spec: Profile Page Design

## Overview
Replace the placeholder `profile.html` with a fully designed profile page that displays the logged-in user's account details and a summary of their expense activity. This step transforms the stub left at the end of Step 03 into a real, data-driven page — pulling the user record by id from the database and computing expense stats (total spent, count, top category) with a new helper. It also introduces the card-grid layout pattern that the expense dashboard will reuse in later steps.

## Depends on
- Step 01 — Database setup (`get_db()`, `users` and `expenses` tables)
- Step 02 — Registration (`users` rows exist)
- Step 03 — Login and Logout (`session['user_id']`, `login_required` decorator)

## Routes
- `GET /profile` — render the profile page with user data and expense stats — logged-in (already exists, upgrade it)

No new routes.

## Database changes
No new tables or columns. Two new DB helper functions must be added to `database/db.py`:

- `get_user_by_id(user_id)` — fetches a single `users` row by primary key using a parameterised query. Returns a `sqlite3.Row` or `None`.
- `get_expense_stats(user_id)` — returns a dict with:
  - `total` — sum of `amount` for the user (float, 0.0 if no expenses)
  - `count` — number of expense rows (int)
  - `top_category` — the category with the highest total spend, or `None` if no expenses

## Templates
- **Modify**: `templates/profile.html`
  - Remove the placeholder text
  - Add a profile header section: user's name (large, display font) and email beneath it
  - Add a stats row with three cards: Total Spent (₹), Number of Expenses, Top Category
  - Add an account details card: name, email, member since (formatted from `created_at`)
  - All monetary values formatted with ₹ prefix and two decimal places

## Files to change
- `app.py` — update `profile()` to call `get_user_by_id` and `get_expense_stats`, pass both to the template
- `database/db.py` — add `get_user_by_id()` and `get_expense_stats()` helpers; update import in `app.py`
- `templates/profile.html` — full redesign (replace placeholder markup)

## Files to create
None.

## New dependencies
No new dependencies.

## Rules for implementation
- No SQLAlchemy or ORMs
- Parameterised queries only — never use f-strings in SQL
- Passwords hashed with werkzeug (no changes to auth logic needed here)
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- Page-specific CSS goes in `{% block head %}` as a `<style>` tag
- Page-specific JS goes in `{% block scripts %}` wrapped in an IIFE
- `get_expense_stats` must handle users with zero expenses without crashing (return 0.0, 0, None)
- Do not store computed stats in session — always fetch fresh from DB on page load
- Format all currency as `₹X,XXX.XX` using Python's `{:,.2f}` format or equivalent Jinja filter

## Definition of done
- [ ] `GET /profile` renders without errors when logged in as demo user
- [ ] Page displays the user's name in the profile header
- [ ] Page displays the user's email address
- [ ] "Total Spent" stat card shows the correct sum of all expenses in ₹
- [ ] "Number of Expenses" stat card shows the correct count
- [ ] "Top Category" stat card shows the category with the highest total spend
- [ ] "Member Since" shows the `created_at` date formatted readably (e.g. "May 2026")
- [ ] A user with zero expenses sees ₹0.00, 0, and "—" (or similar) without any crash or error
- [ ] `/profile` redirects to `/login` when accessed without a session (login_required still enforced)
- [ ] All monetary values are prefixed with ₹ and show two decimal places
