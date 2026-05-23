import math
import sqlite3
import functools
from datetime import date as _date, datetime, timedelta
from flask import Flask, abort, flash, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash
from database.db import get_db, init_db, seed_db, create_user, get_user_by_email
from database.queries import get_user_by_id, get_summary_stats, get_recent_transactions, get_category_breakdown, insert_expense, get_expense_by_id, update_expense, delete_expense

ALLOWED_CATEGORIES = ["Food", "Transport", "Bills", "Health", "Entertainment", "Shopping", "Other"]

app = Flask(__name__)
app.secret_key = "spendly-dev-secret"


@app.template_filter("inr")
def inr_filter(value):
    return f"₹{value:,.2f}"

with app.app_context():
    init_db()
    seed_db()


# ------------------------------------------------------------------ #
# Auth helper                                                         #
# ------------------------------------------------------------------ #

def login_required(f):
    @functools.wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("user_id"):
            flash("Please sign in to continue.")
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated


# ------------------------------------------------------------------ #
# Routes                                                              #
# ------------------------------------------------------------------ #

@app.route("/")
def landing():
    return render_template("landing.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name     = request.form.get("name", "").strip()
        email    = request.form.get("email", "").strip()
        password = request.form.get("password", "")
        confirm  = request.form.get("confirm_password", "")

        if not name or not email or not password or not confirm:
            flash("All fields are required.")
            return render_template("register.html")

        if password != confirm:
            flash("Passwords do not match.")
            return render_template("register.html")

        try:
            create_user(name, email, password)
            flash("Account created! Please sign in.")
            return redirect(url_for("login"))
        except sqlite3.IntegrityError:
            flash("Email already registered.")
            return render_template("register.html")

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email    = request.form.get("email", "").strip()
        password = request.form.get("password", "")

        if not email or not password:
            flash("Email and password are required.")
            return render_template("login.html")

        user = get_user_by_email(email)
        if user is None:
            flash("No account found with that email.")
            return render_template("login.html")

        if not check_password_hash(user["password_hash"], password):
            flash("Incorrect password.")
            return render_template("login.html")

        session["user_id"]   = user["id"]
        session["user_name"] = user["name"]
        return redirect(url_for("profile"))

    return render_template("login.html")


# ------------------------------------------------------------------ #
# Placeholder routes — students will implement these                  #
# ------------------------------------------------------------------ #

@app.route("/terms")
def terms():
    return render_template("terms.html")


@app.route("/privacy")
def privacy():
    return render_template("privacy.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("landing"))


@app.route("/profile")
@login_required
def profile():
    uid    = session["user_id"]
    today  = _date.today()

    def _calendar_months_ago(d, n):
        month = d.month - n
        year  = d.year + (month - 1) // 12
        month = ((month - 1) % 12) + 1
        return d.replace(year=year, month=month, day=1)

    # Resolve preset → date_from / date_to
    preset = request.args.get("preset", "all")
    if preset == "month":
        date_from = today.replace(day=1).isoformat()
        date_to   = today.isoformat()
    elif preset == "3months":
        date_from = _calendar_months_ago(today, 3).isoformat()
        date_to   = today.isoformat()
    elif preset == "6months":
        date_from = _calendar_months_ago(today, 6).isoformat()
        date_to   = today.isoformat()
    else:
        date_from = request.args.get("date_from", "").strip()
        date_to   = request.args.get("date_to", "").strip()

    # Validate custom dates — silently drop malformed values
    def _parse(val):
        try:
            datetime.strptime(val, "%Y-%m-%d")
            return val
        except ValueError:
            return None

    date_from = _parse(date_from) if date_from else None
    date_to   = _parse(date_to)   if date_to   else None

    # Inverted range: flash error, reset filter and preset
    if date_from and date_to and date_from > date_to:
        flash("Start date must be before end date.", "error")
        date_from = date_to = None
        preset = "all"

    # Require both bounds; clear single-sided input so UI reflects reality
    if not (date_from and date_to):
        date_from = date_to = None

    user         = get_user_by_id(uid)
    stats        = get_summary_stats(uid, date_from, date_to)
    transactions = get_recent_transactions(uid, date_from=date_from, date_to=date_to)
    categories   = get_category_breakdown(uid, date_from, date_to)

    return render_template("profile.html", user=user, stats=stats,
                           transactions=transactions, categories=categories,
                           date_from=date_from or "", date_to=date_to or "",
                           preset=preset)


@app.route("/expenses/add", methods=["GET", "POST"])
@login_required
def add_expense():
    if request.method == "POST":
        raw_amount      = request.form.get("amount", "").strip()
        category        = request.form.get("category", "").strip()
        raw_date        = request.form.get("date", "").strip()
        description     = request.form.get("description", "").strip() or None
        form            = {"amount": raw_amount, "category": category,
                           "date": raw_date, "description": description or ""}

        try:
            amount = float(raw_amount)
            if amount <= 0 or not math.isfinite(amount):
                raise ValueError
        except ValueError:
            flash("Amount must be a positive number.")
            return render_template("add_expense.html", form=form,
                                   categories=ALLOWED_CATEGORIES)

        if category not in ALLOWED_CATEGORIES:
            flash("Please select a valid category.")
            return render_template("add_expense.html", form=form,
                                   categories=ALLOWED_CATEGORIES)

        try:
            datetime.strptime(raw_date, "%Y-%m-%d")
        except ValueError:
            flash("Please enter a valid date.")
            return render_template("add_expense.html", form=form,
                                   categories=ALLOWED_CATEGORIES)

        try:
            insert_expense(session["user_id"], amount, category, raw_date, description)
        except sqlite3.Error:
            flash("Could not save expense. Please try again.", "error")
            return render_template("add_expense.html", form=form,
                                   categories=ALLOWED_CATEGORIES)
        flash("Expense added.", "success")
        return redirect(url_for("profile"))

    today = _date.today().isoformat()
    form  = {"amount": "", "category": "", "date": today, "description": ""}
    return render_template("add_expense.html", form=form, categories=ALLOWED_CATEGORIES)


@app.route("/expenses/<int:id>/edit", methods=["GET", "POST"])
@login_required
def edit_expense(id):
    expense = get_expense_by_id(id, session["user_id"])
    if expense is None:
        abort(404)

    if request.method == "POST":
        raw_amount  = request.form.get("amount", "").strip()
        category    = request.form.get("category", "").strip()
        raw_date    = request.form.get("date", "").strip()
        description = request.form.get("description", "").strip() or None
        form        = {"id": id, "amount": raw_amount, "category": category,
                       "date": raw_date, "description": description or ""}

        try:
            amount = float(raw_amount)
            if amount <= 0 or not math.isfinite(amount):
                raise ValueError
        except ValueError:
            flash("Amount must be a positive number.")
            return render_template("edit_expense.html", form=form,
                                   categories=ALLOWED_CATEGORIES)

        if category not in ALLOWED_CATEGORIES:
            flash("Please select a valid category.")
            return render_template("edit_expense.html", form=form,
                                   categories=ALLOWED_CATEGORIES)

        try:
            datetime.strptime(raw_date, "%Y-%m-%d")
        except ValueError:
            flash("Please enter a valid date.")
            return render_template("edit_expense.html", form=form,
                                   categories=ALLOWED_CATEGORIES)

        try:
            update_expense(id, session["user_id"], amount, category, raw_date, description)
        except sqlite3.Error:
            flash("Could not save changes. Please try again.", "error")
            return render_template("edit_expense.html", form=form,
                                   categories=ALLOWED_CATEGORIES)
        flash("Expense updated.", "success")
        return redirect(url_for("profile"))

    form = dict(expense)
    return render_template("edit_expense.html", form=form, categories=ALLOWED_CATEGORIES)


@app.route("/expenses/<int:id>/delete", methods=["POST"])
@login_required
def delete_expense_route(id):
    expense = get_expense_by_id(id, session["user_id"])
    if expense is None:
        abort(404)
    delete_expense(id, session["user_id"])
    flash("Expense deleted.", "success")
    return redirect(url_for("profile"))


if __name__ == "__main__":
    app.run(debug=True, port=5001)
