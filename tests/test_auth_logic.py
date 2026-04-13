from tempfile import TemporaryDirectory

from sidecar.auth import create_session_token, hash_password, verify_password
from sidecar.database import DatabaseService


def test_password_hash_round_trip():
    hashed = hash_password("super-secret-password")

    assert hashed != "super-secret-password"
    assert verify_password("super-secret-password", hashed) is True
    assert verify_password("wrong-password", hashed) is False


def test_user_and_session_lifecycle():
    with TemporaryDirectory() as tmpdir:
        db = DatabaseService(db_path=f"{tmpdir}/auth.db")

        created = db.create_user(
            name="Alice Example",
            email="Alice@Example.com",
            password_hash=hash_password("super-secret-password"),
        )
        assert created is not None
        assert created["email"] == "alice@example.com"

        duplicate = db.create_user(
            name="Alice Example",
            email="alice@example.com",
            password_hash=hash_password("another-password"),
        )
        assert duplicate is None

        stored = db.get_user_by_email("alice@example.com")
        assert stored is not None
        assert verify_password("super-secret-password", stored["password_hash"]) is True

        token = create_session_token()
        assert db.create_auth_session(created["id"], token, "2999-01-01T00:00:00") is True

        session_user = db.get_user_by_session(token)
        assert session_user is not None
        assert session_user["email"] == "alice@example.com"

        assert db.delete_auth_session(token) is True
        assert db.get_user_by_session(token) is None
