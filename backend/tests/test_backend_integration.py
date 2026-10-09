import uuid

import pytest
from fastapi.testclient import TestClient

from app.main import app


# Give this test run a unique client IP so its requests do not share
# the login rate-limit bucket used by other test modules.
_ip_suffix = uuid.uuid4().int
TEST_CLIENT_IP = (
    f"198.18.{(_ip_suffix >> 8) % 256}.{(_ip_suffix % 253) + 1}"
)

client = TestClient(
    app,
    client=(TEST_CLIENT_IP, 50000),
)


def create_valid_pdf() -> bytes:
    """Generate a valid one-page PDF without external dependencies."""

    content = (
        b"BT\n"
        b"/F1 18 Tf\n"
        b"72 720 Td\n"
        b"(DocuMind AI Integration Test) Tj\n"
        b"0 -30 Td\n"
        b"/F1 12 Tf\n"
        b"(Testing document upload and PDF processing.) Tj\n"
        b"ET\n"
    )

    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        (
            b"<< /Type /Page /Parent 2 0 R "
            b"/MediaBox [0 0 612 792] "
            b"/Resources << /Font << /F1 4 0 R >> >> "
            b"/Contents 5 0 R >>"
        ),
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        (
            b"<< /Length "
            + str(len(content)).encode("ascii")
            + b" >>\nstream\n"
            + content
            + b"endstream"
        ),
    ]

    pdf = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = [0]

    for number, obj in enumerate(objects, start=1):
        offsets.append(len(pdf))
        pdf.extend(f"{number} 0 obj\n".encode("ascii"))
        pdf.extend(obj)
        pdf.extend(b"\nendobj\n")

    xref_offset = len(pdf)

    pdf.extend(f"xref\n0 {len(objects) + 1}\n".encode("ascii"))
    pdf.extend(b"0000000000 65535 f \n")

    for offset in offsets[1:]:
        pdf.extend(f"{offset:010d} 00000 n \n".encode("ascii"))

    pdf.extend(
        (
            f"trailer\n"
            f"<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
            f"startxref\n"
            f"{xref_offset}\n"
            f"%%EOF\n"
        ).encode("ascii")
    )

    return bytes(pdf)


def register_and_login(email: str, name: str, password: str):
    """Register a user and log in using the JSON API contract."""

    register_response = client.post(
        "/api/v1/auth/register",
        json={
            "name": name,
            "email": email,
            "password": password,
        },
    )

    assert register_response.status_code in (200, 201), (
        f"Registration failed: {register_response.status_code} "
        f"{register_response.text}"
    )

    login_response = client.post(
        "/api/v1/auth/login",
        json={
            "email": email,
            "password": password,
        },
    )

    assert login_response.status_code == 200, (
        f"Login failed: {login_response.status_code} "
        f"{login_response.text}"
    )

    tokens = login_response.json()
    access_token = tokens.get("access_token")

    assert access_token, f"Access token missing: {tokens}"

    headers = {
        "Authorization": f"Bearer {access_token}",
    }

    return tokens, headers


def get_resource_id(data: dict):
    """Extract an identifier from common API response formats."""

    for key in (
        "id",
        "_id",
        "chat_id",
        "document_id",
        "session_id",
    ):
        if data.get(key) is not None:
            return str(data[key])

    for key in ("chat", "document", "session", "data"):
        nested = data.get(key)

        if isinstance(nested, dict):
            result = get_resource_id(nested)
            if result:
                return result

    return None


def test_complete_backend_flow():
    """Test authentication, chat, PDF upload, search and user isolation."""

    suffix = uuid.uuid4().hex[:12]
    password = "IntegrationTestPassword!2026"

    email_a = f"integration_a_{suffix}@example.com"
    email_b = f"integration_b_{suffix}@example.com"

    # 1. Register and authenticate user A.
    tokens_a, headers_a = register_and_login(
        email_a,
        "Integration User A",
        password,
    )

    # 2. Verify the authenticated user's profile.
    response = client.get(
        "/api/v1/auth/me",
        headers=headers_a,
    )

    assert response.status_code == 200, (
        f"Profile request failed: {response.status_code} {response.text}"
    )
    assert response.json()["email"] == email_a

    # 3. Create a chat.
    chat_response = client.post(
        "/api/v1/chats/",
        headers=headers_a,
        json={"title": "Integration Test Chat"},
    )

    if chat_response.status_code == 404:
        chat_response = client.post(
            "/api/v1/chats",
            headers=headers_a,
            json={"title": "Integration Test Chat"},
        )

    assert chat_response.status_code in (200, 201), (
        f"Chat creation failed: {chat_response.status_code} "
        f"{chat_response.text}"
    )

    chat_id = get_resource_id(chat_response.json())
    assert chat_id, f"Chat ID missing: {chat_response.json()}"

    # 4. List chats.
    response = client.get(
        "/api/v1/chats/",
        headers=headers_a,
    )

    if response.status_code == 404:
        response = client.get(
            "/api/v1/chats",
            headers=headers_a,
        )

    assert response.status_code == 200, (
        f"Chat listing failed: {response.status_code} {response.text}"
    )

    # 5. Create a message.
    response = client.post(
        f"/api/v1/chats/{chat_id}/messages",
        headers=headers_a,
        json={"content": "Integration test message"},
    )

    assert response.status_code in (200, 201), (
        f"Message creation failed: {response.status_code} {response.text}"
    )

    # 6. Retrieve messages.
    response = client.get(
        f"/api/v1/chats/{chat_id}/messages",
        headers=headers_a,
    )

    assert response.status_code == 200, (
        f"Message retrieval failed: {response.status_code} {response.text}"
    )

    # 7. Upload a valid PDF.
    upload_response = client.post(
        "/api/v1/documents/upload",
        headers=headers_a,
        files={
            "file": (
                "integration_test.pdf",
                create_valid_pdf(),
                "application/pdf",
            )
        },
    )

    assert upload_response.status_code in (200, 201), (
        f"Document upload failed: {upload_response.status_code} "
        f"{upload_response.text}"
    )

    # 8. Search documents.
    search_response = client.get(
        "/api/v1/documents/search",
        headers=headers_a,
        params={
            "q": "integration test",
            "limit": 5,
        },
    )

    assert search_response.status_code == 200, (
        f"Document search failed: {search_response.status_code} "
        f"{search_response.text}"
    )

    # 9. Register and authenticate user B.
    tokens_b, headers_b = register_and_login(
        email_b,
        "Integration User B",
        password,
    )

    # 10. User B must not access user A's chat messages.
    cross_user_response = client.get(
        f"/api/v1/chats/{chat_id}/messages",
        headers=headers_b,
    )

    assert cross_user_response.status_code in (403, 404), (
        "Cross-user chat access was not denied: "
        f"{cross_user_response.status_code} {cross_user_response.text}"
    )

    # 11. Refresh user A's access token if a refresh token is returned.
    refresh_token_a = tokens_a.get("refresh_token")

    if refresh_token_a:
        refresh_response = client.post(
            "/api/v1/auth/refresh",
            params={"refresh_token": refresh_token_a},
        )

        assert refresh_response.status_code == 200, (
            f"Token refresh failed: {refresh_response.status_code} "
            f"{refresh_response.text}"
        )

    # 12. Log out user B if a refresh token is returned.
    refresh_token_b = tokens_b.get("refresh_token")

    if refresh_token_b:
        logout_response = client.post(
            "/api/v1/auth/logout",
            params={"refresh_token": refresh_token_b},
        )

        assert logout_response.status_code in (200, 204), (
            f"Logout failed: {logout_response.status_code} "
            f"{logout_response.text}"
        )