"""Password hashing and JWT helpers from app.core.security. No database needed."""

from jose import jwt

from app.core.security import (
    ALGORITHM,
    SECRET_KEY,
    create_access_token,
    hash_password,
    verify_password,
)


def test_password_round_trip() -> None:
    hashed = hash_password("sheva7")
    assert hashed != "sheva7"
    assert verify_password("sheva7", hashed) is True


def test_wrong_password_is_rejected() -> None:
    hashed = hash_password("sheva7")
    assert verify_password("maldini3", hashed) is False


def test_same_password_hashes_differently() -> None:
    assert hash_password("sheva7") != hash_password("sheva7")


def test_access_token_carries_user_and_admin_claims() -> None:
    token = create_access_token(user_id=42, is_admin=True)
    claims = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    assert claims["sub"] == "42"
    assert claims["admin"] is True
    assert claims["exp"] > claims["iat"]
