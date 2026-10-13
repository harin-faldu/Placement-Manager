from __future__ import annotations

import hashlib
import hmac
import secrets

import bcrypt
from cryptography.fernet import Fernet, InvalidToken

from app.core.config import settings

_fernet = Fernet(settings.fernet_key.encode() if isinstance(settings.fernet_key, str) else settings.fernet_key)


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode(), password_hash.encode())
    except ValueError:
        return False


def password_problems(password: str) -> str | None:
    if len(password) < 10:
        return "Password must be at least 10 characters"
    if password.lower() == password or password.upper() == password or not any(char.isdigit() for char in password):
        return "Password must include upper case, lower case, and a number"
    return None


def encrypt_mobile(mobile: str) -> str:
    return _fernet.encrypt(mobile.encode()).decode()


def decrypt_mobile(token: str) -> str:
    try:
        return _fernet.decrypt(token.encode()).decode()
    except InvalidToken:
        return ""


def mobile_digest(mobile: str) -> str:
    return hmac.new(settings.secret_key.encode(), mobile.encode(), hashlib.sha256).hexdigest()


def new_token() -> str:
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def mask_mobile(mobile: str | None) -> str | None:
    if not mobile:
        return None
    if len(mobile) <= 4:
        return "••••"
    return "••••" + mobile[-4:]
