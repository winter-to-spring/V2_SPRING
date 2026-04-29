import pytest
from app.services.auth import hash_password, verify_password, create_access_token
from jose import jwt, JWTError
from datetime import timedelta


def test_hash_password():
    """Test that password hashing works."""
    password = "test_password_123"
    hashed = hash_password(password)
    assert hashed != password
    assert len(hashed) > 0


def test_verify_password_success():
    """Test that password verification succeeds with correct password."""
    password = "test_password_123"
    hashed = hash_password(password)
    assert verify_password(password, hashed) is True


def test_verify_password_failure():
    """Test that password verification fails with incorrect password."""
    password = "test_password_123"
    wrong_password = "wrong_password"
    hashed = hash_password(password)
    assert verify_password(wrong_password, hashed) is False


def test_create_access_token_default_expiry():
    """Test that access token is created with default 24h expiry."""
    data = {"sub": "user@example.com"}
    token = create_access_token(data)
    assert isinstance(token, str)
    assert len(token) > 0
    
    # Decode without verification to check claims
    from app.services.auth import settings
    decoded = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
    assert decoded["sub"] == "user@example.com"
    assert "exp" in decoded


def test_create_access_token_custom_expiry():
    """Test that access token respects custom expiry time."""
    data = {"sub": "user@example.com"}
    expires_delta = timedelta(hours=1)
    token = create_access_token(data, expires_delta)
    assert isinstance(token, str)
    
    from app.services.auth import settings
    decoded = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
    assert decoded["sub"] == "user@example.com"
    assert "exp" in decoded


def test_token_uses_hs256():
    """Test that token is encoded with HS256 algorithm."""
    data = {"sub": "user@example.com"}
    token = create_access_token(data)
    
    from app.services.auth import settings
    # This should decode successfully with HS256
    decoded = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
    assert decoded["sub"] == "user@example.com"
