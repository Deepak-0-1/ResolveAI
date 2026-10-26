from resolveai_db.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)


def test_password_hash_roundtrip() -> None:
    hashed = hash_password("secret-value")
    assert hashed != "secret-value"
    assert verify_password("secret-value", hashed)
    assert not verify_password("other", hashed)


def test_jwt_roundtrip() -> None:
    token = create_access_token(subject="user-1", role="admin", email="a@b.com")
    payload = decode_access_token(token)
    assert payload["sub"] == "user-1"
    assert payload["role"] == "admin"
    assert payload["email"] == "a@b.com"
