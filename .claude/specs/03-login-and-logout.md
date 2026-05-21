# Spec: Login and Logout

## Overview
Implement login and logout so registered users can authenticate into Spendly and end their session. This step upgrades the existing stub `GET /login` route into a full `GET`/`POST` handler that validates credentials against the `users` table, writes the authenticated user's id and name into Flask's `session`, and redirects to a protected dashboard placeholder. The `GET /logout` stub is replaced with a handler that clears the session and redirects to the landing page. After this step all subsequent steps can gate routes behind a `login_required` guard.

## Depends on
- Step 01 — Database setup (`users` table, `get_db()`)
- Step 02 — Registration (`create_user()`, `users` rows exist)

## Routes
- `GET /login` — render login form — public (already exists as stub, upgrade it)
- `POST /login` — validate credentials, write session, redirect to `/profile` — public
- `GET /logout` — clear session, redirect to `/` — logged-in (already exists as stub, upgrade it)

## Database changes
No new tables or columns. The existing `users` table covers all requirements.

One new DB helper must be added to `database/db.py`:
- `get_user_by_email(email)` — fetches a single `users` row by email using a parameterised query. Returns a `sqlite3.Row` object or `None` if not found.

## Templates
- **Modify**: `templates/login.html`
  - Set the form `action` to `url_for('login')` with `method="post"`
  - Add `name` attributes to inputs: `email`, `password`
  - Add a block to display flashed error messages (wrong password, unknown email)
  - Keep all existing visual design

- **Modify**: `templates/base.html`
  - In the navbar, conditionally show:
    - When logged out: "Login" and "Register" links
    - When logged in: the user's name and a "Logout" link
  - Use `session.get('user_id')` to detect auth state (no `g.user` lookup needed)

## Files to change
- `app.py` — upgrade `login()` to `GET`/`POST`; implement `logout()`; add `login_required` decorator
- `database/db.py` — add `get_user_by_email()` helper; update import in `app.py`
- `templates/login.html` — wire up form action/method and flash message display
- `templates/base.html` — conditional navbar links based on session state

## Files to create
None.

## New dependencies
No new dependencies. Uses `werkzeug.security.check_password_hash` (already installed) and Flask's built-in `session`, `flash`, `redirect`, `url_for`.

## Rules for implementation
- No SQLAlchemy or ORMs
- Parameterised queries only — never use f-strings in SQL
- Verify passwords with `werkzeug.security.check_password_hash` — never compare plaintext
- Store only `user_id` (int) and `user_name` (str) in `session` — never the password hash
- The `login_required` decorator must redirect to `url_for('login')` when `session.get('user_id')` is absent
- On login failure, re-render the form with a flashed error — do not redirect
- On login success, `session['user_id']` and `session['user_name']` are set, then redirect to `url_for('profile')`
- `logout()` must call `session.clear()` then redirect to `url_for('landing')`
- All templates extend `base.html`
- Use CSS variables — never hardcode hex values
- Use `url_for()` for every internal link — never hardcode URLs

## Definition of done
- [ ] `GET /login` renders the login form without errors
- [ ] Submitting valid credentials sets `session['user_id']` and redirects to `/profile`
- [ ] Submitting an unknown email re-renders the form with an error message, no session written
- [ ] Submitting a wrong password re-renders the form with an error message, no session written
- [ ] Submitting with any empty field re-renders the form with a validation error, no session written
- [ ] `GET /logout` clears the session and redirects to `/`
- [ ] After logout, navigating to `/logout` again (no session) still redirects safely to `/`
- [ ] Navbar shows "Login" and "Register" when logged out, user name and "Logout" when logged in
- [ ] Demo user (`demo@spendly.com` / `demo123`) can log in successfully
