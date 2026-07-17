"""
Auth core logic — password hashing and JWT handling.
Kept separate from routes, same philosophy as core/bidding.py.
"""

import uuid
from datetime import datetime, timedelta, timezone

import jwt
from passlib.context import CryptContext

# TODO: move to .env before submission. Never commit a real secret key.
SECRET_KEY = "dev-only-secret-change-before-submission"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 24 hours, generous for demo/dev purposes

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, password_hash: str) -> bool:
    return pwd_context.verify(plain_password, password_hash)


def create_access_token(user_id: uuid.UUID) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {"sub": str(user_id), "exp": expire}
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


class InvalidToken(Exception):
    pass


def decode_access_token(token: str) -> uuid.UUID:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return uuid.UUID(payload["sub"])
    except (jwt.PyJWTError, KeyError, ValueError) as e:
        raise InvalidToken(str(e))
