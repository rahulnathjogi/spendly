# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Run the development server (port 5001)
python app.py

# Run all tests
pytest

# Run a single test file
pytest tests/test_auth.py

# Run a single test by name
pytest -k "test_login"
```

## Architecture

**Spendly** is a Flask expense tracker structured as a step-by-step learning scaffold (Steps 1–9). Most application logic is intentionally not yet implemented.

### Stack
- **Backend**: Python + Flask 3.0.3, SQLite via `sqlite3` (no ORM)
- **Frontend**: Jinja2 templates, plain CSS/JS — no frontend framework
- **Testing**: pytest 8.3.5 + pytest-flask 1.3.0

### Key files
- `app.py` — Flask app with all routes. Active routes: `/`, `/register`, `/login`, `/terms`, `/privacy`. Stub routes: `/logout`, `/profile`, `/expenses/add|edit|delete`.
- `database/db.py` — **stub file**; students implement `get_db()`, `init_db()`, and `seed_db()`. `get_db()` should return a SQLite connection with `row_factory = sqlite3.Row` and `PRAGMA foreign_keys = ON`.
- `templates/base.html` — shared layout with navbar and footer. All pages extend this.
- `static/css/style.css` — all styles; no CSS framework used.
- `static/js/main.js` — placeholder; per-page JS is inlined in `{% block scripts %}`.

### Database
SQLite file is `expense_tracker.db` (gitignored). Created by `init_db()` once that is implemented. Connection is opened per-request (no connection pooling).

### Template conventions
Page-specific CSS goes in `{% block head %}` as a `<style>` tag (see `landing.html`). Page-specific JS goes in `{% block scripts %}`. Inline scripts use IIFEs.

### Currency
The app targets INR (₹). Use ₹ in all UI copy and formatting.
