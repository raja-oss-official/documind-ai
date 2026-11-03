import json
import uuid
from datetime import datetime, timedelta, timezone

import pytest
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
from app.services import (
    chat_rag_service,
    chunk_service,
    document_intelligence_service,
    document_tools_service,
    large_document_summary_service,
    ocr_service,
    search_service,
)
from app.services.document_processing_service import (
    recover_interrupted_documents,
)
from app.services.search_service import tokenize_text


# ============================================================
# DATABASE AND CLIENT
# ============================================================
#
# Gemini (answers and embeddings) is replaced with fakes in
# every test, so this module runs offline and quickly.

mongo_client = MongoClient(
    settings.mongodb_url
)

test_db = mongo_client[
    settings.database_name
]

client = TestClient(
    app
)

FAKE_EMBEDDING = [0.1] * 8


# ============================================================
# HELPERS
# ============================================================

def make_user(name: str):
    """Create a user directly in MongoDB and return (id, headers)."""

    user_id = ObjectId()

    test_db.users.insert_one(
        {
            "_id": user_id,
            "name": name,
            "email": f"enh_{uuid.uuid4().hex}@example.com",
            "password_hash": hash_password("Enhance@123"),
            "created_at": datetime.now(timezone.utc),
        }
    )

    token = create_access_token(
        str(user_id)
    )

    return str(user_id), {
        "Authorization": f"Bearer {token}",
    }


def user_email(user_id: str) -> str:
    return test_db.users.find_one(
        {"_id": ObjectId(user_id)}
    )["email"]


def make_document(
    user_id: str,
    filename: str = "notes.txt",
    chunk_texts: list[str] | None = None,
    extracted_text: str | None = None,
):
    """Create a completed document with chunks and embeddings."""

    chunk_texts = chunk_texts or [
        "DocuMind AI helps students revise.",
        "Flashcards improve long-term memory.",
    ]

    document_id = ObjectId()

    test_db.documents.insert_one(
        {
            "_id": document_id,
            "user_id": user_id,
            "filename": filename,
            "file_type": "text/plain",
            "file_size": 100,
            "status": "completed",
            "extracted_text": extracted_text or " ".join(chunk_texts),
            "created_at": datetime.now(timezone.utc),
        }
    )

    test_db.document_chunks.insert_many(
        [
            {
                "document_id": str(document_id),
                "user_id": user_id,
                "chunk_index": index,
                "page_number": 1 + index // 10,
                "text": text,
                "character_count": len(text),
                "word_count": len(text.split()),
                "embedding": FAKE_EMBEDDING,
            }
            for index, text in enumerate(chunk_texts)
        ]
    )

    return str(document_id)


def parse_events(body: str) -> list[tuple[str, dict]]:
    """Parse a Server-Sent Events response body."""

    events = []

    for block in body.strip().split("\n\n"):

        lines = dict(
            line.split(": ", 1)
            for line in block.splitlines()
            if ": " in line
        )

        events.append(
            (lines["event"], json.loads(lines["data"]))
        )

    return events


@pytest.fixture(autouse=True)
def fake_gemini(monkeypatch):
    """Offline embeddings; tests patch answers as needed."""

    limiter.reset()

    monkeypatch.setattr(
        chunk_service,
        "create_embedding",
        lambda text: FAKE_EMBEDDING,
    )

    monkeypatch.setattr(
        search_service,
        "create_embedding",
        lambda text: FAKE_EMBEDDING,
    )


# ============================================================
# MAP-REDUCE SUMMARY
# ============================================================

def test_long_document_uses_map_reduce_summary(monkeypatch):

    user_id, headers = make_user("Summary User")

    chunks = [
        f"Section {index} explains topic {index} in detail. " * 10
        for index in range(80)
    ]

    document_id = make_document(
        user_id,
        chunk_texts=chunks,
        extracted_text="x" * 40000,
    )

    calls = []

    def fake_answer(prompt):
        calls.append(prompt)

        if "final document" in prompt:
            return "SUMMARY:\nWhole document summary.\nKEY POINTS:\n- One\n- Two"

        return "Batch summary."

    monkeypatch.setattr(
        large_document_summary_service,
        "generate_answer",
        fake_answer,
    )

    monkeypatch.setattr(
        document_intelligence_service,
        "generate_answer",
        lambda prompt: pytest.fail("Direct summary should not run"),
    )

    response = client.post(
        f"/api/v1/documents/{document_id}/summary",
        headers=headers,
    )

    assert response.status_code == 200, response.text
    assert response.json()["method"] == "map_reduce"
    assert response.json()["key_points"] == ["One", "Two"]

    # 80 chunks in batches of 24 → 4 batch calls + 1 final call.
    assert len(calls) == 5


def test_map_reduce_caps_the_number_of_batches(monkeypatch):

    calls = []

    monkeypatch.setattr(
        large_document_summary_service,
        "summarize_chunk_batch",
        lambda batch: calls.append(len(batch)) or "Batch summary.",
    )

    chunks = [
        {"text": f"chunk {index}", "page_number": 1}
        for index in range(1000)
    ]

    large_document_summary_service.generate_large_document_summary(
        chunks
    )

    assert len(calls) <= large_document_summary_service.MAX_BATCHES
    assert sum(calls) == 1000


# ============================================================
# SOURCES SAVED WITH CHAT MESSAGES
# ============================================================

def fake_retrieval(**kwargs):
    source = {
        "chunk_id": "c1",
        "document_id": "d1",
        "chunk_index": 0,
        "page_number": 3,
        "score": 0.9,
        "text": "Flashcards improve long-term memory.",
        "embedding": FAKE_EMBEDDING,
    }

    return {
        "context_chunks": [source],
        "sources": [source],
    }


def test_chat_answers_keep_their_sources(monkeypatch):

    user_id, headers = make_user("Sources User")

    monkeypatch.setattr(
        chat_rag_service,
        "retrieve_document_context",
        fake_retrieval,
    )

    monkeypatch.setattr(
        chat_rag_service,
        "generate_answer",
        lambda prompt: "Flashcards help memory.",
    )

    chat = client.post(
        "/api/v1/chats",
        headers=headers,
        json={"title": "Sources"},
    ).json()

    response = client.post(
        f"/api/v1/chats/{chat['id']}/ask",
        headers=headers,
        json={"question": "Why use flashcards?"},
    )

    assert response.status_code == 200, response.text

    messages = client.get(
        f"/api/v1/chats/{chat['id']}/messages",
        headers=headers,
    ).json()

    assistant = [m for m in messages if m["role"] == "assistant"][0]
    user = [m for m in messages if m["role"] == "user"][0]

    assert assistant["sources"][0]["page_number"] == 3
    assert "embedding" not in assistant["sources"][0]
    assert user["sources"] == []


def test_answer_rules_follow_the_question_language():

    assert "same language as the user's question" in (
        chat_rag_service.ANSWER_GUIDELINES
    )


# ============================================================
# STREAMING ANSWERS
# ============================================================

def test_streaming_chat_answer(monkeypatch):

    user_id, headers = make_user("Stream User")

    monkeypatch.setattr(
        chat_rag_service,
        "retrieve_document_context",
        fake_retrieval,
    )

    monkeypatch.setattr(
        chat_rag_service,
        "stream_answer",
        lambda prompt: iter(["Hel", "lo ", "world"]),
    )

    chat = client.post(
        "/api/v1/chats",
        headers=headers,
        json={"title": "Stream"},
    ).json()

    response = client.post(
        f"/api/v1/chats/{chat['id']}/ask/stream",
        headers=headers,
        json={"question": "Say hello"},
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")

    events = parse_events(response.text)
    names = [name for name, _ in events]

    assert names == ["start", "token", "token", "token", "done"]
    assert events[0][1]["sources"][0]["page_number"] == 3
    assert events[-1][1]["assistant_message"]["content"] == "Hello world"

    saved = client.get(
        f"/api/v1/chats/{chat['id']}/messages",
        headers=headers,
    ).json()

    assert saved[-1]["content"] == "Hello world"
    assert saved[-1]["sources"]


def test_streaming_requires_chat_owner():

    _, headers_a = make_user("Stream Owner")
    _, headers_b = make_user("Stream Stranger")

    chat = client.post(
        "/api/v1/chats",
        headers=headers_a,
        json={"title": "Private"},
    ).json()

    response = client.post(
        f"/api/v1/chats/{chat['id']}/ask/stream",
        headers=headers_b,
        json={"question": "Hello?"},
    )

    assert response.status_code == 404


# ============================================================
# BACKGROUND PROCESSING AND ORIGINAL FILE STORAGE
# ============================================================

def test_upload_processes_in_background_and_keeps_original():

    user_id, headers = make_user("Upload User")
    _, other_headers = make_user("Other User")

    content = b"Background processing keeps uploads fast. " * 20

    response = client.post(
        "/api/v1/documents/upload",
        headers=headers,
        files={"file": ("background.txt", content, "text/plain")},
    )

    assert response.status_code == 200, response.text
    assert response.json()["status"] == "processing"

    document_id = response.json()["id"]

    # TestClient runs background tasks before returning.
    document = client.get(
        f"/api/v1/documents/{document_id}",
        headers=headers,
    ).json()

    assert document["status"] == "completed"
    assert document["chunk_count"] > 0

    original = client.get(
        f"/api/v1/documents/{document_id}/file",
        headers=headers,
    )

    assert original.status_code == 200
    assert original.content == content
    assert original.headers["content-type"].startswith("text/plain")

    denied = client.get(
        f"/api/v1/documents/{document_id}/file",
        headers=other_headers,
    )

    assert denied.status_code == 404

    client.delete(
        f"/api/v1/documents/{document_id}",
        headers=headers,
    )

    assert test_db["document_files.files"].count_documents(
        {"metadata.document_id": document_id}
    ) == 0


def test_interrupted_processing_is_marked_failed():

    user_id, _ = make_user("Restart User")

    stuck_id = test_db.documents.insert_one(
        {
            "user_id": user_id,
            "filename": "stuck.pdf",
            "status": "processing",
            "created_at": datetime.now(timezone.utc) - timedelta(minutes=5),
        }
    ).inserted_id

    recover_interrupted_documents()

    stuck = test_db.documents.find_one({"_id": stuck_id})

    assert stuck["status"] == "failed"
    assert "interrupted" in stuck["processing_error"]


# ============================================================
# COMPARE, STUDY AND FACTS
# ============================================================

def test_compare_two_documents(monkeypatch):

    user_id, headers = make_user("Compare User")

    first = make_document(user_id, "plan_v1.txt", ["Budget is 10 lakh."])
    second = make_document(user_id, "plan_v2.txt", ["Budget is 12 lakh."])

    prompts = []

    monkeypatch.setattr(
        document_tools_service,
        "generate_answer",
        lambda prompt: prompts.append(prompt) or "### Differences\n| Topic | A | B |",
    )

    response = client.post(
        "/api/v1/documents/compare",
        headers=headers,
        json={"document_ids": [first, second], "focus": "budget"},
    )

    assert response.status_code == 200, response.text
    assert "plan_v1.txt" in prompts[0] and "plan_v2.txt" in prompts[0]
    assert "10 lakh" in prompts[0] and "12 lakh" in prompts[0]

    same = client.post(
        "/api/v1/documents/compare",
        headers=headers,
        json={"document_ids": [first, first]},
    )

    assert same.status_code == 422


def test_quiz_drops_malformed_questions(monkeypatch):

    user_id, headers = make_user("Quiz User")
    document_id = make_document(user_id)

    monkeypatch.setattr(
        document_tools_service,
        "generate_json",
        lambda prompt: [
            {
                "question": "What improves memory?",
                "options": ["Flashcards", "Noise", "Sleep loss", "Skipping"],
                "answer_index": 0,
                "explanation": "The document says so.",
                "page_number": 1,
            },
            {"question": "Broken", "options": ["A", "B"], "answer_index": 0},
            {"question": "Bad index", "options": ["A", "B", "C", "D"], "answer_index": 7},
        ],
    )

    response = client.post(
        f"/api/v1/documents/{document_id}/study",
        headers=headers,
        json={"type": "quiz", "count": 5},
    )

    assert response.status_code == 200, response.text
    assert len(response.json()["items"]) == 1
    assert response.json()["items"][0]["answer_index"] == 0


def test_flashcards_and_facts(monkeypatch):

    user_id, headers = make_user("Facts User")
    document_id = make_document(user_id)

    monkeypatch.setattr(
        document_tools_service,
        "generate_json",
        lambda prompt: (
            [{"front": "Flashcard", "back": "A memory aid"}, {"front": ""}]
            if "flashcards" in prompt
            else [
                {"category": "deadline", "value": "15 March 2026", "context": "Submission", "page_number": 2},
                {"category": "weird", "value": "₹2,40,000", "context": "Budget"},
                {"category": "date", "value": ""},
            ]
        ),
    )

    cards = client.post(
        f"/api/v1/documents/{document_id}/study",
        headers=headers,
        json={"type": "flashcards"},
    )

    assert cards.status_code == 200, cards.text
    assert cards.json()["items"] == [{"front": "Flashcard", "back": "A memory aid"}]

    facts = client.post(
        f"/api/v1/documents/{document_id}/facts",
        headers=headers,
    )

    assert facts.status_code == 200, facts.text
    rows = facts.json()["facts"]

    assert [row["category"] for row in rows] == ["deadline", "other"]
    assert rows[1]["value"] == "₹2,40,000"


# ============================================================
# SHARED DOCUMENTS AND CHATS
# ============================================================

def test_document_sharing_roles(monkeypatch):

    owner_id, owner = make_user("Owner")
    viewer_id, viewer = make_user("Viewer")
    editor_id, editor = make_user("Editor")
    _, stranger = make_user("Stranger")

    document_id = make_document(owner_id, "shared_plan.txt")

    # Owner shares with a viewer and an editor.
    for email, role in (
        (user_email(viewer_id), "viewer"),
        (user_email(editor_id), "editor"),
    ):
        response = client.post(
            f"/api/v1/documents/{document_id}/shares",
            headers=owner,
            json={"email": email, "role": role},
        )

        assert response.status_code == 200, response.text

    shares = client.get(
        f"/api/v1/documents/{document_id}/shares",
        headers=owner,
    ).json()

    assert {share["role"] for share in shares} == {"viewer", "editor"}

    # The viewer sees the document, labelled as shared.
    listed = client.get("/api/v1/documents", headers=viewer).json()
    shared = [doc for doc in listed if doc["id"] == document_id][0]

    assert shared["shared"] is True
    assert shared["role"] == "viewer"
    assert shared["owner_name"] == "Owner"

    # The viewer can search it but cannot rename or share it.
    results = client.get(
        "/api/v1/documents/search",
        headers=viewer,
        params={"q": "students revise", "document_id": document_id},
    ).json()

    assert results["result_count"] > 0

    rename = client.patch(
        f"/api/v1/documents/{document_id}/rename",
        headers=viewer,
        json={"filename": "hacked.txt"},
    )

    assert rename.status_code == 403

    reshare = client.post(
        f"/api/v1/documents/{document_id}/shares",
        headers=viewer,
        json={"email": user_email(editor_id), "role": "editor"},
    )

    assert reshare.status_code == 403

    # The editor can rename.
    renamed = client.patch(
        f"/api/v1/documents/{document_id}/rename",
        headers=editor,
        json={"filename": "plan_final.txt"},
    )

    assert renamed.status_code == 200, renamed.text

    # Strangers cannot see it at all.
    assert client.get(
        f"/api/v1/documents/{document_id}",
        headers=stranger,
    ).status_code == 404

    # A chat on a shared document is allowed.
    chat = client.post(
        "/api/v1/chats",
        headers=viewer,
        json={"title": "About the plan", "document_id": document_id},
    )

    assert chat.status_code == 200, chat.text

    # After the owner stops sharing, the viewer loses access.
    client.delete(
        f"/api/v1/documents/{document_id}/shares/{viewer_id}",
        headers=owner,
    )

    assert client.get(
        f"/api/v1/documents/{document_id}",
        headers=viewer,
    ).status_code == 404


def test_share_with_unknown_email_or_self():

    owner_id, owner = make_user("Lonely Owner")
    document_id = make_document(owner_id)

    unknown = client.post(
        f"/api/v1/documents/{document_id}/shares",
        headers=owner,
        json={"email": "nobody_here@example.com", "role": "viewer"},
    )

    assert unknown.status_code == 400

    self_share = client.post(
        f"/api/v1/documents/{document_id}/shares",
        headers=owner,
        json={"email": user_email(owner_id), "role": "viewer"},
    )

    assert self_share.status_code == 400


def test_chat_sharing_is_read_only():

    owner_id, owner = make_user("Chat Owner")
    reader_id, reader = make_user("Chat Reader")
    _, stranger = make_user("Chat Stranger")

    chat = client.post(
        "/api/v1/chats",
        headers=owner,
        json={"title": "Team notes"},
    ).json()

    client.post(
        f"/api/v1/chats/{chat['id']}/messages",
        headers=owner,
        json={"content": "Remember the deadline."},
    )

    shared = client.post(
        f"/api/v1/chats/{chat['id']}/shares",
        headers=owner,
        json={"email": user_email(reader_id)},
    )

    assert shared.status_code == 200, shared.text

    listed = client.get("/api/v1/chats/shared", headers=reader).json()

    assert [item["id"] for item in listed] == [chat["id"]]
    assert listed[0]["owner_name"] == "Chat Owner"

    messages = client.get(
        f"/api/v1/chats/shared/{chat['id']}/messages",
        headers=reader,
    )

    assert messages.status_code == 200
    assert messages.json()[0]["content"] == "Remember the deadline."

    # Read-only: the reader cannot post or ask in the chat.
    assert client.post(
        f"/api/v1/chats/{chat['id']}/messages",
        headers=reader,
        json={"content": "Can I write?"},
    ).status_code == 404

    assert client.get(
        f"/api/v1/chats/shared/{chat['id']}/messages",
        headers=stranger,
    ).status_code == 404


# ============================================================
# MULTILINGUAL
# ============================================================

def test_keyword_search_keeps_indic_words_whole():

    words = tokenize_text("தமிழ் ஆவணம் हिन्दी दस्तावेज़ Café")

    assert {"தமிழ்", "ஆவணம்", "हिन्दी", "दस्तावेज़", "café"} <= words


def test_ocr_uses_only_installed_languages(monkeypatch):

    monkeypatch.setattr(
        ocr_service.pytesseract,
        "get_languages",
        lambda config="": ["eng", "tam", "osd"],
    )

    assert ocr_service.ocr_language() == "eng+tam"
