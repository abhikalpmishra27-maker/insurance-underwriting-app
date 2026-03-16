"""
User model and database helpers for authentication.
Uses SQLite for lightweight persistence.
"""

import os
import sqlite3
from contextlib import contextmanager

import bcrypt
from flask_login import UserMixin

DATABASE_PATH = os.environ.get("DATABASE_PATH", "users.db")


@contextmanager
def get_db():
    """Yield a database connection that auto-commits and closes."""
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    """Create the users table if it does not exist."""
    with get_db() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                username    TEXT    NOT NULL UNIQUE COLLATE NOCASE,
                password    TEXT    NOT NULL,
                created_at  TEXT    NOT NULL DEFAULT (datetime('now'))
            )
            """
        )


class User(UserMixin):
    """Flask-Login compatible user object."""

    def __init__(self, id: int, username: str):
        self.id = id
        self.username = username

    def get_id(self) -> str:
        return str(self.id)


def get_user_by_id(user_id: int) -> User | None:
    """Look up a user by primary key."""
    with get_db() as conn:
        row = conn.execute("SELECT id, username FROM users WHERE id = ?", (user_id,)).fetchone()
    if row:
        return User(id=row["id"], username=row["username"])
    return None


def get_user_by_username(username: str) -> dict | None:
    """Return the full row (incl. hashed password) for *username*, or None."""
    with get_db() as conn:
        row = conn.execute(
            "SELECT id, username, password FROM users WHERE username = ?", (username,)
        ).fetchone()
    if row:
        return dict(row)
    return None


def create_user(username: str, password: str) -> User:
    """Hash *password* and insert a new user.  Returns the User object."""
    hashed = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt())
    with get_db() as conn:
        cursor = conn.execute(
            "INSERT INTO users (username, password) VALUES (?, ?)",
            (username, hashed.decode("utf-8")),
        )
        user_id = cursor.lastrowid
    return User(id=user_id, username=username)


def verify_password(plain: str, hashed: str) -> bool:
    """Check a plain-text password against a bcrypt hash."""
    return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
