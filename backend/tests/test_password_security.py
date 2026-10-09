import uuid

from bson import ObjectId
from fastapi.testclient import TestClient
from pymongo import MongoClient

from app.main import app
from app.core.config import settings
from app.core.rate_limiter import limiter
from app.core.security import hash_password


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
    f"password_test_{uuid.uuid4().hex}"
    "@example.com"
)

TEST_NAME = "Password Test User"

CURRENT_PASSWORD = "CurrentPassword@123"

NEW_PASSWORD = "NewPassword@456"


# ============================================================
# TEST CLIENT
# ============================================================

client = TestClient(
    app,
    client=(
        "127.0.0.100",
        50000,
    ),
)


# ============================================================
# TEST USER SETUP
# ============================================================

def setup_test_user():

    # Remove any previous test user.
    test_db.users.delete_many(
        {
            "email": TEST_EMAIL
        }
    )

    # Remove previous refresh tokens.
    test_db.refresh_tokens.delete_many(
        {
            "user_id": str(TEST_USER_ID)
        }
    )

    # Create a real MongoDB user.
    test_db.users.insert_one(
        {
            "_id": TEST_USER_ID,
            "name": TEST_NAME,
            "email": TEST_EMAIL,
            "password_hash": hash_password(
                CURRENT_PASSWORD
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
# TEST SETUP / TEARDOWN
# ============================================================

def setup_function():

    # Reset only the in-memory rate limiter state
    # between tests.
    #
    # This does NOT change the production rate limit.
    limiter.reset()

    setup_test_user()


def teardown_function():

    cleanup_test_user()


# ============================================================
# LOGIN HELPER
# ============================================================

def login_test_user():

    response = client.post(
        "/api/v1/auth/login",
        json={
            "email": TEST_EMAIL,
            "password": CURRENT_PASSWORD,
        },
    )

    assert response.status_code == 200

    return response.json()


# ============================================================
# WEAK PASSWORD TESTS
# ============================================================

def test_register_with_short_password():

    response = client.post(
        "/api/v1/auth/register",
        json={
            "name": "Weak Password User",
            "email": (
                f"weak_short_{uuid.uuid4().hex}"
                "@example.com"
            ),
            "password": "123",
        },
    )

    assert response.status_code == 422


def test_register_with_empty_password():

    response = client.post(
        "/api/v1/auth/register",
        json={
            "name": "Weak Password User",
            "email": (
                f"weak_empty_{uuid.uuid4().hex}"
                "@example.com"
            ),
            "password": "",
        },
    )

    assert response.status_code == 422


def test_register_with_password_without_uppercase():

    response = client.post(
        "/api/v1/auth/register",
        json={
            "name": "Weak Password User",
            "email": (
                f"weak_lower_{uuid.uuid4().hex}"
                "@example.com"
            ),
            "password": "password@123",
        },
    )

    assert response.status_code in {
        400,
        422,
    }


def test_register_with_password_without_lowercase():

    response = client.post(
        "/api/v1/auth/register",
        json={
            "name": "Weak Password User",
            "email": (
                f"weak_upper_{uuid.uuid4().hex}"
                "@example.com"
            ),
            "password": "PASSWORD@123",
        },
    )

    assert response.status_code in {
        400,
        422,
    }


def test_register_with_common_weak_password():

    response = client.post(
        "/api/v1/auth/register",
        json={
            "name": "Weak Password User",
            "email": (
                f"weak_common_{uuid.uuid4().hex}"
                "@example.com"
            ),
            "password": "Password123",
        },
    )

    assert response.status_code in {
        400,
        422,
    }


# ============================================================
# PASSWORD CHANGE TEST
# ============================================================

def test_change_password_with_wrong_current_password():

    tokens = login_test_user()

    access_token = tokens[
        "access_token"
    ]

    response = client.post(
        "/api/v1/auth/change-password",
        headers={
            "Authorization": (
                f"Bearer {access_token}"
            )
        },
        json={
            "current_password": "WrongPassword@123",
            "new_password": NEW_PASSWORD,
        },
    )

    # The current API contract returns 400
    # when the current password is incorrect.
    assert response.status_code == 400

    assert response.json()["detail"] == (
        "Current password is incorrect"
    )


def test_change_password_reuse_current_password():

    tokens = login_test_user()

    access_token = tokens[
        "access_token"
    ]

    response = client.post(
        "/api/v1/auth/change-password",
        headers={
            "Authorization": (
                f"Bearer {access_token}"
            )
        },
        json={
            "current_password": CURRENT_PASSWORD,
            "new_password": CURRENT_PASSWORD,
        },
    )

    assert response.status_code == 400

    assert response.json()["detail"] == (
        "New password must be different "
        "from the current password"
    )


def test_change_password_success():

    tokens = login_test_user()

    access_token = tokens[
        "access_token"
    ]

    response = client.post(
        "/api/v1/auth/change-password",
        headers={
            "Authorization": (
                f"Bearer {access_token}"
            )
        },
        json={
            "current_password": CURRENT_PASSWORD,
            "new_password": NEW_PASSWORD,
        },
    )

    assert response.status_code == 200

    assert response.json()["message"] == (
        "Password changed successfully. "
        "Please log in again."
    )

    # --------------------------------------------------------
    # Verify that the new password can be used.
    # --------------------------------------------------------

    login_response = client.post(
        "/api/v1/auth/login",
        json={
            "email": TEST_EMAIL,
            "password": NEW_PASSWORD,
        },
    )

    assert login_response.status_code == 200


def test_password_change_revokes_existing_refresh_token():

    # --------------------------------------------------------
    # Import token helpers.
    #
    # We create tokens directly so this test does not need
    # another /login request.
    # --------------------------------------------------------

    from app.core.security import (
        create_access_token,
        create_refresh_token,
        verify_refresh_token,
    )

    from app.services.refresh_token_service import (
        create_refresh_token_record,
    )

    # --------------------------------------------------------
    # Create a valid access token.
    # --------------------------------------------------------

    access_token = create_access_token(
        str(TEST_USER_ID)
    )

    # --------------------------------------------------------
    # Create a refresh token.
    # --------------------------------------------------------

    old_refresh_token = create_refresh_token(
        str(TEST_USER_ID)
    )

    # --------------------------------------------------------
    # Decode the refresh token so we can obtain its
    # expiration time.
    # --------------------------------------------------------

    refresh_payload = verify_refresh_token(
        old_refresh_token
    )

    # --------------------------------------------------------
    # Store the refresh token in MongoDB.
    # --------------------------------------------------------

    create_refresh_token_record(
        user_id=str(TEST_USER_ID),
        refresh_token=old_refresh_token,
        expires_at=refresh_payload[
            "expires_at"
        ],
    )

    # --------------------------------------------------------
    # Confirm the refresh token exists.
    # --------------------------------------------------------

    refresh_record_before = (
        test_db.refresh_tokens.find_one(
            {
                "user_id": str(TEST_USER_ID)
            }
        )
    )

    assert refresh_record_before is not None

    assert refresh_record_before[
        "revoked_at"
    ] is None

    # --------------------------------------------------------
    # Change the password.
    # --------------------------------------------------------

    response = client.post(
        "/api/v1/auth/change-password",
        headers={
            "Authorization": (
                f"Bearer {access_token}"
            )
        },
        json={
            "current_password": CURRENT_PASSWORD,
            "new_password": NEW_PASSWORD,
        },
    )

    assert response.status_code == 200

    assert response.json()["message"] == (
        "Password changed successfully. "
        "Please log in again."
    )

    # --------------------------------------------------------
    # Confirm that the refresh token was revoked.
    # --------------------------------------------------------

    refresh_record_after = (
        test_db.refresh_tokens.find_one(
            {
                "user_id": str(TEST_USER_ID)
            }
        )
    )

    assert refresh_record_after is not None

    assert refresh_record_after[
        "revoked_at"
    ] is not None

    # --------------------------------------------------------
    # Try to use the old refresh token.
    #
    # It must no longer work.
    # --------------------------------------------------------

    refresh_response = client.post(
        "/api/v1/auth/refresh",
        params={
            "refresh_token": old_refresh_token
        },
    )

    assert refresh_response.status_code == 401

    assert refresh_response.json()["detail"] == (
        "Refresh token has been revoked or expired"
    )