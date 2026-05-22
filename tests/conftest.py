import pytest
import sqlite3
import database.db as _db

from app import app as flask_app


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
