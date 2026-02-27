import os
import base64
import uuid
from datetime import datetime, timedelta
from typing import Optional

from jose import JWTError, jwt
from passlib.context import CryptContext

SECRET_KEY      = os.getenv("SECRET_KEY", "changeme-use-a-long-random-string")
ALGORITHM       = "HS256"
TOKEN_EXPIRE_HR = 24

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


# ─── PASSWORD ─────────────────────────────────────────────────────────────────

def hash_password(plain: str) -> str:
    return pwd_context.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


# ─── JWT ──────────────────────────────────────────────────────────────────────

def create_access_token(user_id: str, email: str) -> str:
    payload = {
        "sub": user_id,
        "email": email,
        "exp": datetime.utcnow() + timedelta(hours=TOKEN_EXPIRE_HR)
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> Optional[dict]:
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        return None


# ─── IRCTC CREDENTIAL ENCRYPTION ─────────────────────────────────────────────
# Simple XOR + base64 for MVP (use Fernet / AWS KMS in production)

_ENC_KEY = os.getenv("ENCRYPT_KEY", "thirakadha-secret-key-change-this!!")


def _xor_encrypt(text: str, key: str) -> str:
    key_bytes = (key * ((len(text) // len(key)) + 1)).encode()
    xored = bytes(a ^ b for a, b in zip(text.encode(), key_bytes))
    return base64.urlsafe_b64encode(xored).decode()


def _xor_decrypt(encrypted: str, key: str) -> str:
    xored = base64.urlsafe_b64decode(encrypted.encode())
    key_bytes = (key * ((len(xored) // len(key)) + 1)).encode()
    return bytes(a ^ b for a, b in zip(xored, key_bytes)).decode()


def encrypt_irctc_password(plain_password: str) -> str:
    """Encrypt IRCTC password before storing in DB"""
    return _xor_encrypt(plain_password, _ENC_KEY)


def decrypt_irctc_password(encrypted_password: str) -> str:
    """Decrypt IRCTC password when agent needs it"""
    return _xor_decrypt(encrypted_password, _ENC_KEY)


def generate_id() -> str:
    return str(uuid.uuid4())