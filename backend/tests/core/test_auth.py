"""
Unit tests for core/auth.py -- password hashing/verification and JWT
handling. verify_password() specifically was previously untested: every
other test in this suite mints tokens directly via create_access_token,
bypassing the real /auth/login flow (and its call to verify_password)
entirely.
"""

import uuid

import pytest

from app.core.auth import (
    hash_password,
    verify_password,
    create_access_token,
    decode_access_token,
    InvalidToken,
)


def test_verify_password_accepts_correct_password():
    hashed = hash_password("correct horse battery staple")
    assert verify_password("correct horse battery staple", hashed) is True


def test_verify_password_rejects_incorrect_password():
    hashed = hash_password("correct horse battery staple")
    assert verify_password("wrong password", hashed) is False


def test_create_and_decode_access_token_round_trip():
    user_id = uuid.uuid4()
    token = create_access_token(user_id)
    assert decode_access_token(token) == user_id


def test_decode_access_token_rejects_garbage_token():
    with pytest.raises(InvalidToken):
        decode_access_token("not.a.valid.jwt")
