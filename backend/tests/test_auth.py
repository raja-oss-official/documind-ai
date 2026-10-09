from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


# ============================================================
# TEST DATA
# ============================================================

TEST_EMAIL = "test_auth_user@example.com"

TEST_PASSWORD = "TestPassword@123"

TEST_NAME = "Test Auth User"


# ============================================================
# REGISTER
# ============================================================

def test_register_user():

    response = client.post(
        "/api/v1/auth/register",
        json={
            "name": TEST_NAME,
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD,
        },
    )

    # The test user may already exist if the test
    # was executed previously.
    #
    # Therefore both successful registration and
    # already-registered responses are acceptable.

    assert response.status_code in {
        200,
        201,
        400,
    }


# ============================================================
# LOGIN
# ============================================================

def test_login_user():

    # Make sure the test user exists.
    register_response = client.post(
        "/api/v1/auth/register",
        json={
            "name": TEST_NAME,
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD,
        },
    )

    assert register_response.status_code in {
        200,
        201,
        400,
    }

    # Login.
    response = client.post(
        "/api/v1/auth/login",
        json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD,
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"


# ============================================================
# INVALID PASSWORD
# ============================================================

def test_login_with_invalid_password():

    response = client.post(
        "/api/v1/auth/login",
        json={
            "email": TEST_EMAIL,
            "password": "WrongPassword@123",
        },
    )

    assert response.status_code == 401

    data = response.json()

    assert data["detail"] == (
        "Invalid email or password"
    )


# ============================================================
# INVALID EMAIL
# ============================================================

def test_login_with_unknown_email():

    response = client.post(
        "/api/v1/auth/login",
        json={
            "email": "does_not_exist@example.com",
            "password": TEST_PASSWORD,
        },
    )

    assert response.status_code == 401

    data = response.json()

    assert data["detail"] == (
        "Invalid email or password"
    )


# ============================================================
# ACCESS PROTECTED ROUTE WITHOUT TOKEN
# ============================================================

def test_me_without_token():

    response = client.get(
        "/api/v1/auth/me"
    )

    # HTTPBearer returns 401 when no Authorization
    # header is supplied.
    assert response.status_code == 401


# ============================================================
# ACCESS PROTECTED ROUTE WITH INVALID TOKEN
# ============================================================

def test_me_with_invalid_token():

    response = client.get(
        "/api/v1/auth/me",
        headers={
            "Authorization": "Bearer invalid-token"
        },
    )

    assert response.status_code == 401


# ============================================================
# SUCCESSFUL /ME
# ============================================================

def test_me_with_valid_token():

    # Login.
    response = client.post(
        "/api/v1/auth/login",
        json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD,
        },
    )

    assert response.status_code == 200

    data = response.json()

    access_token = data[
        "access_token"
    ]

    # Call protected endpoint.
    response = client.get(
        "/api/v1/auth/me",
        headers={
            "Authorization": (
                f"Bearer {access_token}"
            )
        },
    )

    assert response.status_code == 200

    user = response.json()

    assert user["email"] == TEST_EMAIL
    assert user["name"] == TEST_NAME
    assert "id" in user