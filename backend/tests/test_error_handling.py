import uuid

from bson import ObjectId
from fastapi.testclient import TestClient
from pymongo import MongoClient

from app.main import app
from app.core.config import settings
from app.core.rate_limiter import limiter
from app.core.security import (
    create_access_token,
    hash_password,
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
    f"error_test_{uuid.uuid4().hex}"
    "@example.com"
)

TEST_PASSWORD = "ErrorTest@123"

TEST_NAME = "Error Test User"


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

    limiter.reset()

    setup_test_user()


def teardown_function():

    cleanup_test_user()


# ============================================================
# HELPER
# ============================================================

def get_access_token():

    return create_access_token(
        str(TEST_USER_ID)
    )


# ============================================================
# 401 — AUTHENTICATION
# ============================================================

def test_protected_endpoint_without_token():

    response = client.get(
        "/api/v1/auth/me"
    )

    assert response.status_code == 401


def test_protected_endpoint_with_invalid_token():

    response = client.get(
        "/api/v1/auth/me",
        headers={
            "Authorization": (
                "Bearer invalid-token"
            )
        },
    )

    assert response.status_code == 401


def test_protected_endpoint_with_wrong_token_type():

    from app.core.security import (
        create_refresh_token,
    )

    refresh_token = create_refresh_token(
        str(TEST_USER_ID)
    )

    response = client.get(
        "/api/v1/auth/me",
        headers={
            "Authorization": (
                f"Bearer {refresh_token}"
            )
        },
    )

    assert response.status_code == 401


# ============================================================
# 400 — BAD REQUEST
# ============================================================

def test_password_change_wrong_current_password():

    access_token = get_access_token()

    response = client.post(
        "/api/v1/auth/change-password",
        headers={
            "Authorization": (
                f"Bearer {access_token}"
            )
        },
        json={
            "current_password": (
                "WrongPassword@123"
            ),
            "new_password": (
                "NewPassword@456"
            ),
        },
    )

    assert response.status_code == 400

    assert response.json()["detail"] == (
        "Current password is incorrect"
    )


def test_password_change_reuses_current_password():

    access_token = get_access_token()

    response = client.post(
        "/api/v1/auth/change-password",
        headers={
            "Authorization": (
                f"Bearer {access_token}"
            )
        },
        json={
            "current_password": TEST_PASSWORD,
            "new_password": TEST_PASSWORD,
        },
    )

    assert response.status_code == 400

    assert response.json()["detail"] == (
        "New password must be different "
        "from the current password"
    )


# ============================================================
# 404 — NOT FOUND
# ============================================================

def test_document_not_found():

    fake_document_id = str(
        ObjectId()
    )

    access_token = get_access_token()

    response = client.get(
        f"/api/v1/documents/{fake_document_id}",
        headers={
            "Authorization": (
                f"Bearer {access_token}"
            )
        },
    )

    assert response.status_code == 404


def test_chat_session_not_found():

    fake_session_id = str(
        ObjectId()
    )

    access_token = get_access_token()

    response = client.get(
        f"/api/v1/chats/{fake_session_id}",
        headers={
            "Authorization": (
                f"Bearer {access_token}"
            )
        },
    )

    assert response.status_code == 404


# ============================================================
# INVALID OBJECT IDS
# ============================================================

def test_invalid_document_id():

    access_token = get_access_token()

    response = client.get(
        "/api/v1/documents/not-a-valid-id",
        headers={
            "Authorization": (
                f"Bearer {access_token}"
            )
        },
    )

    assert response.status_code == 400


def test_invalid_chat_session_id():

    access_token = get_access_token()

    response = client.get(
        "/api/v1/chats/not-a-valid-id",
        headers={
            "Authorization": (
                f"Bearer {access_token}"
            )
        },
    )

    assert response.status_code == 400


# ============================================================
# 422 — VALIDATION ERROR
# ============================================================

def test_register_invalid_email():

    response = client.post(
        "/api/v1/auth/register",
        json={
            "name": "Validation Test",
            "email": "not-an-email",
            "password": (
                "ValidPassword@123"
            ),
        },
    )

    assert response.status_code == 422


def test_register_missing_password():

    response = client.post(
        "/api/v1/auth/register",
        json={
            "name": "Validation Test",
            "email": (
                f"missing_password_"
                f"{uuid.uuid4().hex}"
                "@example.com"
            ),
        },
    )

    assert response.status_code == 422


def test_login_invalid_email():

    response = client.post(
        "/api/v1/auth/login",
        json={
            "email": "not-an-email",
            "password": TEST_PASSWORD,
        },
    )

    assert response.status_code == 422


# ============================================================
# EXTRA FIELDS — REQUEST VALIDATION
# ============================================================

def test_register_rejects_extra_fields():

    response = client.post(
        "/api/v1/auth/register",
        json={
            "name": "Extra Field Test",
            "email": (
                f"extra_{uuid.uuid4().hex}"
                "@example.com"
            ),
            "password": (
                "ValidPassword@123"
            ),
            "unexpected_field": "should fail",
        },
    )

    assert response.status_code == 422


# ============================================================
# UNKNOWN ROUTE
# ============================================================

def test_unknown_route():

    response = client.get(
        "/api/v1/this-route-does-not-exist"
    )

    assert response.status_code == 404