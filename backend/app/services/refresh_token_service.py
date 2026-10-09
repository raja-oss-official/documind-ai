from datetime import datetime, timezone
import hashlib

from app.core.database import db


refresh_tokens_collection = db.refresh_tokens


def hash_refresh_token(refresh_token: str) -> str:
    """
    Create a one-way SHA-256 hash of the refresh token.

    We store the hash in MongoDB instead of storing
    the actual refresh token.
    """
    return hashlib.sha256(
        refresh_token.encode("utf-8")
    ).hexdigest()


def create_refresh_token_record(
    user_id: str,
    refresh_token: str,
    expires_at: datetime,
):
    """
    Store a refresh token record in MongoDB.
    """

    token_hash = hash_refresh_token(refresh_token)

    record = {
        "user_id": user_id,
        "token_hash": token_hash,
        "created_at": datetime.now(timezone.utc),
        "expires_at": expires_at,
        "revoked_at": None,
    }

    result = refresh_tokens_collection.insert_one(record)

    return str(result.inserted_id)


def get_refresh_token_record(
    refresh_token: str,
):
    """
    Find a refresh token record using its hash.
    """

    token_hash = hash_refresh_token(refresh_token)

    return refresh_tokens_collection.find_one(
        {
            "token_hash": token_hash
        }
    )


def is_refresh_token_active(
    refresh_token: str,
) -> bool:
    """
    Check whether a refresh token is still active.
    """

    record = get_refresh_token_record(
        refresh_token
    )

    if not record:
        return False

    if record.get("revoked_at") is not None:
        return False

    expires_at = record.get("expires_at")

    if not expires_at:
        return False

    now = datetime.now(timezone.utc)

    # MongoDB may return a timezone-naive datetime.
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(
            tzinfo=timezone.utc
        )

    if expires_at <= now:
        return False

    return True


def revoke_refresh_token(
    refresh_token: str,
):
    """
    Revoke a refresh token.
    """

    token_hash = hash_refresh_token(refresh_token)

    result = refresh_tokens_collection.update_one(
        {
            "token_hash": token_hash,
            "revoked_at": None,
        },
        {
            "$set": {
                "revoked_at": datetime.now(
                    timezone.utc
                )
            }
        },
    )

    return result.modified_count > 0


def revoke_all_user_refresh_tokens(
    user_id: str,
):
    """
    Revoke all active refresh tokens belonging
    to a specific user.

    Useful later for:
    - Logout from all devices
    - Password change
    - Security incident
    """

    result = refresh_tokens_collection.update_many(
        {
            "user_id": user_id,
            "revoked_at": None,
        },
        {
            "$set": {
                "revoked_at": datetime.now(
                    timezone.utc
                )
            }
        },
    )

    return result.modified_count