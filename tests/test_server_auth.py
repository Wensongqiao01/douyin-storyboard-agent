"""tests/test_server_auth.py — 密码哈希与 JWT"""

import jwt as pyjwt
import pytest

from server.auth import create_token, decode_token, hash_password, verify_password


def test_hash_and_verify_password():
    h = hash_password("secret123")
    assert h != "secret123"
    assert verify_password("secret123", h) is True
    assert verify_password("wrong", h) is False


def test_verify_password_with_invalid_hash():
    assert verify_password("x", "not-a-bcrypt-hash") is False


def test_create_and_decode_token(monkeypatch):
    from config import config

    monkeypatch.setattr(config, "jwt_secret", "test-secret")
    token = create_token(user_id=42, username="bob")
    payload = decode_token(token)
    assert payload["sub"] == "42"
    assert payload["username"] == "bob"


def test_decode_invalid_token_raises(monkeypatch):
    from config import config

    monkeypatch.setattr(config, "jwt_secret", "test-secret")
    with pytest.raises(pyjwt.InvalidTokenError):
        decode_token("garbage.token.here")
