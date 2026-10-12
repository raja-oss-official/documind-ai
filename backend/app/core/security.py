# ============================================================
# IMPORTS
# ============================================================

from datetime import datetime, timedelta, timezone
import uuid

import jwt
from fastapi import HTTPException, status
from fastapi.security import (
    HTTPBearer,
    HTTPAuthorizationCredentials,
)
from pwdlib import PasswordHash

from app.core.config import settings


# ============================================================
# PASSWORD HASHER AND BEARER AUTH
# ============================================================

password_hash = PasswordHash.recommended()

security = HTTPBearer()


# ============================================================
# HASH PASSWORD
# ============================================================

def hash_password(password: str) -> str:
    return password_hash.hash(password)


# ============================================================
# VERIFY PASSWORD
# ============================================================

def verify_password(
    password: str,
    hashed_password: str,
) -> bool:
    return password_hash.verify(
        password,
        hashed_password,
    )


# ============================================================
# CREATE ACCESS TOKEN
# ============================================================

def create_access_token(user_id: str) -> str:
    expire = (
        datetime.now(timezone.utc)
        + timedelta(minutes=30)
    )

    payload = {
        "sub": user_id,
        "type": "access",
        "exp": expire,
    }

    token = jwt.encode(
        payload,
        settings.jwt_secret_key,
        algorithm="HS256",
    )

    return token


# ============================================================
# CREATE REFRESH TOKEN
# ============================================================

def create_refresh_token(user_id: str) -> str:
    expire = (
        datetime.now(timezone.utc)
        + timedelta(days=7)
    )

    jti = str(uuid.uuid4())

    payload = {
        "sub": user_id,
        "type": "refresh",
        "jti": jti,
        "exp": expire,
    }

    token = jwt.encode(
        payload,
        settings.jwt_secret_key,
        algorithm="HS256",
    )

    return token


# ============================================================
# VERIFY ACCESS TOKEN
# ============================================================

def verify_access_token(
    credentials: HTTPAuthorizationCredentials,
):
    token = credentials.credentials

    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=["HS256"],
        )

        user_id = payload.get("sub")
        token_type = payload.get("type")

        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token",
            )

        if token_type != "access":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid access token",
            )

        return user_id

    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
        )

    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
        )


# ============================================================
# VERIFY REFRESH TOKEN
# ============================================================

def verify_refresh_token(
    refresh_token: str,
):
    try:
        payload = jwt.decode(
            refresh_token,
            settings.jwt_secret_key,
            algorithms=["HS256"],
        )

        user_id = payload.get("sub")
        token_type = payload.get("type")
        jti = payload.get("jti")

        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid refresh token",
            )

        if token_type != "refresh":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid refresh token",
            )

        if not jti:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid refresh token",
            )

        return {
            "user_id": user_id,
            "jti": jti,
            "expires_at": datetime.fromtimestamp(
                payload["exp"],
                tz=timezone.utc,
            ),
        }

    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token has expired",
        )

    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
        )