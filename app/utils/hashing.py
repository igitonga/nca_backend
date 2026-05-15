import hashlib
import secrets

def hash_token(token: str) -> str:
    """
    Hash a token using SHA-256
    Returns a hexadecimal digest
    """
    return hashlib.sha256(token.encode()).hexdigest()

def verify_token(raw_token: str, hashed_token: str) -> bool:
    """Verify a raw token against its hash"""
    return hash_token(raw_token) == hashed_token

def generate_token() -> str:
    """Generate a secure random token"""
    return secrets.token_urlsafe(32)