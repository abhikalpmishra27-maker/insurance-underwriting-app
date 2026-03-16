"""
Tests for the user authentication system.
"""

import os
import tempfile

import pytest

# Use a temporary database for tests
_db_fd, _db_path = tempfile.mkstemp(suffix=".db")
os.environ["DATABASE_PATH"] = _db_path

from app import app  # noqa: E402
from models import init_db  # noqa: E402


@pytest.fixture(autouse=True)
def reset_db():
    """Re-create the database before every test."""
    import sqlite3
    conn = sqlite3.connect(_db_path)
    conn.execute("DROP TABLE IF EXISTS users")
    conn.close()
    init_db()
    yield


@pytest.fixture()
def client():
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


# ── Registration ──────────────────────────────────────────────────────────────


def test_register_success(client):
    resp = client.post("/api/auth/register", json={"username": "alice", "password": "password123"})
    assert resp.status_code == 201
    data = resp.get_json()
    assert data["success"] is True
    assert data["user"]["username"] == "alice"


def test_register_missing_fields(client):
    resp = client.post("/api/auth/register", json={"username": "alice"})
    assert resp.status_code == 400
    assert "required" in resp.get_json()["error"].lower()


def test_register_short_password(client):
    resp = client.post("/api/auth/register", json={"username": "alice", "password": "short"})
    assert resp.status_code == 400
    assert "8 characters" in resp.get_json()["error"]


def test_register_invalid_username(client):
    resp = client.post("/api/auth/register", json={"username": "a!", "password": "password123"})
    assert resp.status_code == 400
    assert "letters, numbers" in resp.get_json()["error"]


def test_register_duplicate_username(client):
    client.post("/api/auth/register", json={"username": "alice", "password": "password123"})
    resp = client.post("/api/auth/register", json={"username": "alice", "password": "password456"})
    assert resp.status_code == 409
    assert "already taken" in resp.get_json()["error"]


# ── Login ─────────────────────────────────────────────────────────────────────


def test_login_success(client):
    client.post("/api/auth/register", json={"username": "bob", "password": "password123"})
    # Logout first to test fresh login
    client.post("/api/auth/logout")
    resp = client.post("/api/auth/login", json={"username": "bob", "password": "password123"})
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["success"] is True
    assert data["user"]["username"] == "bob"


def test_login_wrong_password(client):
    client.post("/api/auth/register", json={"username": "bob", "password": "password123"})
    client.post("/api/auth/logout")
    resp = client.post("/api/auth/login", json={"username": "bob", "password": "wrong"})
    assert resp.status_code == 401
    assert "Invalid" in resp.get_json()["error"]


def test_login_nonexistent_user(client):
    resp = client.post("/api/auth/login", json={"username": "nobody", "password": "password123"})
    assert resp.status_code == 401


# ── Logout ────────────────────────────────────────────────────────────────────


def test_logout_success(client):
    client.post("/api/auth/register", json={"username": "carol", "password": "password123"})
    resp = client.post("/api/auth/logout")
    assert resp.status_code == 200
    assert resp.get_json()["success"] is True


def test_logout_requires_auth(client):
    resp = client.post("/api/auth/logout")
    assert resp.status_code == 401


# ── Auth Status ───────────────────────────────────────────────────────────────


def test_status_authenticated(client):
    client.post("/api/auth/register", json={"username": "dave", "password": "password123"})
    resp = client.get("/api/auth/status")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["authenticated"] is True
    assert data["user"]["username"] == "dave"


def test_status_unauthenticated(client):
    resp = client.get("/api/auth/status")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["authenticated"] is False


# ── Protected Routes ──────────────────────────────────────────────────────────


def test_underwrite_requires_auth(client):
    resp = client.post("/api/underwrite", json={"name": "Test"})
    assert resp.status_code == 401


def test_extract_requires_auth(client):
    resp = client.post("/api/extract")
    assert resp.status_code == 401


def test_health_does_not_require_auth(client):
    resp = client.get("/api/health")
    assert resp.status_code == 200


def test_index_does_not_require_auth(client):
    resp = client.get("/")
    assert resp.status_code == 200


# ── Underwrite works when authenticated ───────────────────────────────────────


def test_underwrite_when_authenticated(client):
    client.post("/api/auth/register", json={"username": "eve", "password": "password123"})
    payload = {
        "name": "Eve Smith",
        "gender": "Female",
        "dob": "15/06/1990",
        "place_of_residence": "Mumbai",
        "profession": "Engineer",
        "height_cm": 165,
        "weight_kg": 60,
        "yearly_income": 1200000,
        "source_of_income": "salary",
        "base_cover": 5000000,
        "cir_cover": 1000000,
        "accident_cover": 2000000,
        "parent_health_status": "both_above_65",
        "health_conditions": {},
        "habits": {},
        "risky_occupations": [],
    }
    resp = client.post("/api/underwrite", json=payload)
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["success"] is True
    assert "report" in data
