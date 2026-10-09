import uuid

from bson import ObjectId
from fastapi.testclient import TestClient
from pymongo import MongoClient

from app.main import app
from app.core.config import settings
from app.core.security import (
    hash_password,
    create_access_token,
    create_refresh_token,
    verify_refresh_token,
)
from app.services.refresh_token_service import (
    create_refresh_token_record,
)


# ============================================================
# DATABASE
# ============================================================

mongo_client = MongoClient(
    settings.mongodb_url
)

test_db = mongo_client[
    settings.database_name
]


# ============================================================
# TEST USER
# ============================================================

TEST_USER_ID = ObjectId()

TEST_EMAIL = (
    f"refresh_test_{uuid.uuid4().hex}"
    "@example.com"
)

TEST_PASSWORD = "RefreshTest@123"

TEST_NAME = "Refresh Test User"


# ============================================================
# TEST CLIENT
# ============================================================

client = TestClient(
    app
)


# ============================================================
# TEST USER SETUP
# ============================================================

def setup_test_user():

    # --------------------------------------------------------
    # Remove any previous test data.
    # --------------------------------------------------------

    test_db.users.delete_many(
        {
            "email": TEST_EMAIL
        }
    )

    test_db.refresh_tokens.delete_many(
        {
            "user_id": str(TEST_USER_ID)
        }
    )

    # --------------------------------------------------------
    # Create the user directly in MongoDB.
    #
    # We intentionally do NOT call /register because that
    # endpoint is rate limited in production.
    # --------------------------------------------------------

    test_db.users.insert_one(
        {
            "_id": TEST_USER_ID,
            "name": TEST_NAME,
            "email": TEST_EMAIL,
            "password_hash": hash_password(
                TEST_PASSWORD
            ),
        }
    )


# ============================================================
# TEST USER CLEANUP
# ============================================================

def cleanup_test_user():

    test_db.users.delete_many(
        {
            "_id": TEST_USER_ID
        }
    )

    test_db.refresh_tokens.delete_many(
        {
            "user_id": str(TEST_USER_ID)
        }
    )


# ============================================================
# PYTEST SETUP / TEARDOWN
# ============================================================

def setup_function():

    setup_test_user()


def teardown_function():

    cleanup_test_user()


# ============================================================
# CREATE ACTIVE REFRESH TOKEN
# ============================================================

def create_test_refresh_token():

    refresh_token = create_refresh_token(
        str(TEST_USER_ID)
    )

    refresh_payload = verify_refresh_token(
        refresh_token
    )

    create_refresh_token_record(
        user_id=str(TEST_USER_ID),
        refresh_token=refresh_token,
        expires_at=refresh_payload[
            "expires_at"
        ],
    )

    return refresh_token


# ============================================================
# TEST 1
# ============================================================

def test_refresh_token():

    refresh_token = (
        create_test_refresh_token()
    )

    response = client.post(
        "/api/v1/auth/refresh",
        params={
            "refresh_token": refresh_token
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert "access_token" in data

    assert "refresh_token" in data

    assert data["token_type"] == "bearer"

    assert data["refresh_token"] != (
        refresh_token
    )


# ============================================================
# TEST 2
# ============================================================

def test_refresh_token_rotation():

    old_refresh_token = (
        create_test_refresh_token()
    )

    # --------------------------------------------------------
    # First refresh.
    # --------------------------------------------------------

    first_response = client.post(
        "/api/v1/auth/refresh",
        params={
            "refresh_token": old_refresh_token
        },
    )

    assert first_response.status_code == 200

    first_data = first_response.json()

    new_refresh_token = first_data[
        "refresh_token"
    ]

    assert new_refresh_token != (
        old_refresh_token
    )

    # --------------------------------------------------------
    # The old token must now be revoked.
    # --------------------------------------------------------

    second_response = client.post(
        "/api/v1/auth/refresh",
        params={
            "refresh_token": old_refresh_token
        },
    )

    assert second_response.status_code == 401

    assert second_response.json()["detail"] == (
        "Refresh token has been revoked or expired"
    )


# ============================================================
# TEST 3
# ============================================================

def test_rotated_refresh_token_works():

    old_refresh_token = (
        create_test_refresh_token()
    )

    # --------------------------------------------------------
    # Rotate the original refresh token.
    # --------------------------------------------------------

    first_response = client.post(
        "/api/v1/auth/refresh",
        params={
            "refresh_token": old_refresh_token
        },
    )

    assert first_response.status_code == 200

    new_refresh_token = (
        first_response.json()[
            "refresh_token"
        ]
    )

    assert new_refresh_token != (
        old_refresh_token
    )

    # --------------------------------------------------------
    # The newly generated refresh token must work.
    # --------------------------------------------------------

    second_response = client.post(
        "/api/v1/auth/refresh",
        params={
            "refresh_token": new_refresh_token
        },
    )

    assert second_response.status_code == 200

    data = second_response.json()

    assert "access_token" in data

    assert "refresh_token" in data

    assert data["token_type"] == "bearer"

    assert data["refresh_token"] != (
        new_refresh_token
    )


# ============================================================
# TEST 4
# ============================================================

def test_logout_revokes_refresh_token():

    refresh_token = (
        create_test_refresh_token()
    )

    # --------------------------------------------------------
    # Confirm token exists before logout.
    # --------------------------------------------------------

    token_hash_record = (
        test_db.refresh_tokens.find_one(
            {
                "user_id": str(TEST_USER_ID)
            }
        )
    )

    assert token_hash_record is not None

    assert token_hash_record[
        "revoked_at"
    ] is None

    # --------------------------------------------------------
    # Logout.
    # --------------------------------------------------------

    logout_response = client.post(
        "/api/v1/auth/logout",
        params={
            "refresh_token": refresh_token
        },
    )

    assert logout_response.status_code == 200

    assert logout_response.json()["message"] == (
        "Logout successful"
    )

    # --------------------------------------------------------
    # Confirm the token was revoked in MongoDB.
    # --------------------------------------------------------

    revoked_record = (
        test_db.refresh_tokens.find_one(
            {
                "user_id": str(TEST_USER_ID)
            }
        )
    )

    assert revoked_record is not None

    assert revoked_record[
        "revoked_at"
    ] is not None

    # --------------------------------------------------------
    # Try to use the revoked token.
    # --------------------------------------------------------

    refresh_response = client.post(
        "/api/v1/auth/refresh",
        params={
            "refresh_token": refresh_token
        },
    )

    assert refresh_response.status_code == 401

    assert refresh_response.json()["detail"] == (
        "Refresh token has been revoked or expired"
    )


# ============================================================
# TEST 5
# ============================================================

def test_invalid_refresh_token():

    response = client.post(
        "/api/v1/auth/refresh",
        params={
            "refresh_token": (
                "invalid-refresh-token"
            )
        },
    )

    assert response.status_code == 401

    assert response.json()["detail"] == (
        "Invalid refresh token"
    )


# ============================================================
# TEST 6
# ============================================================

def test_access_token_cannot_be_used_as_refresh_token():

    # --------------------------------------------------------
    # Create a normal access token directly.
    # --------------------------------------------------------

    access_token = create_access_token(
        str(TEST_USER_ID)
    )

    # --------------------------------------------------------
    # Attempt to use the access token as a refresh token.
    # --------------------------------------------------------

    response = client.post(
        "/api/v1/auth/refresh",
        params={
            "refresh_token": access_token
        },
    )

    assert response.status_code == 401

    assert response.json()["detail"] == (
        "Invalid refresh token"
    )