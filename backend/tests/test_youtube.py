import uuid
from datetime import datetime, timezone

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
    search_service,
    youtube_service,
)
from app.services.youtube_service import (
    parse_video_id,
    timestamp_seconds,
    transcript_segments,
)


# ============================================================
# DATABASE AND CLIENT
# ============================================================
#
# YouTube and Gemini are replaced with fakes, so these tests
# run offline.

mongo_client = MongoClient(
    settings.mongodb_url
)

test_db = mongo_client[
    settings.database_name
]

client = TestClient(
    app
)

FAKE_TRANSCRIPT = """
[00:00] Welcome to this lesson on photosynthesis.
[00:08] Plants turn light, water and carbon dioxide into sugar.
[00:20] [Visual] A diagram of a leaf labelled chloroplast.
[00:31] Chlorophyll is the green pigment that absorbs light.
this line continues the previous sentence.
[01:05] Oxygen is released as a by-product.
"""


# ============================================================
# HELPERS
# ============================================================

def make_user(name: str):

    user_id = ObjectId()

    test_db.users.insert_one(
        {
            "_id": user_id,
            "name": name,
            "email": f"yt_{uuid.uuid4().hex}@example.com",
            "password_hash": hash_password("YouTube@123"),
            "created_at": datetime.now(timezone.utc),
        }
    )

    return str(user_id), {
        "Authorization": f"Bearer {create_access_token(str(user_id))}",
    }


@pytest.fixture(autouse=True)
def fake_services(monkeypatch):

    limiter.reset()

    fake_info = lambda video_id: {"title": "Photosynthesis in 2 minutes", "author": "Science Channel"}

    # The route imports fetch_video_info by name, so patch both.
    monkeypatch.setattr(
        youtube_service,
        "fetch_video_info",
        fake_info,
    )

    monkeypatch.setattr(
        "app.routes.youtube.fetch_video_info",
        fake_info,
    )

    monkeypatch.setattr(
        youtube_service,
        "generate_from_youtube",
        lambda url, prompt: FAKE_TRANSCRIPT,
    )

    monkeypatch.setattr(
        chunk_service,
        "create_embedding",
        lambda text: [0.1] * 8,
    )

    monkeypatch.setattr(
        search_service,
        "create_embedding",
        lambda text: [0.1] * 8,
    )


# ============================================================
# LINK PARSING
# ============================================================

@pytest.mark.parametrize(
    "url",
    [
        "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        "https://youtube.com/watch?v=dQw4w9WgXcQ&t=42s",
        "youtube.com/watch?v=dQw4w9WgXcQ",
        "https://youtu.be/dQw4w9WgXcQ?si=abc",
        "https://m.youtube.com/watch?v=dQw4w9WgXcQ",
        "https://www.youtube.com/shorts/dQw4w9WgXcQ",
        "https://www.youtube.com/embed/dQw4w9WgXcQ",
        "https://www.youtube.com/live/dQw4w9WgXcQ",
    ],
)
def test_parse_video_id_accepts_youtube_links(url):

    assert parse_video_id(url) == "dQw4w9WgXcQ"


@pytest.mark.parametrize(
    "url",
    [
        "https://vimeo.com/123456",
        "https://www.youtube.com/watch?v=short",
        "https://evil.example.com/watch?v=dQw4w9WgXcQ",
        "https://www.youtube.com/channel/UC123",
        "not a link",
    ],
)
def test_parse_video_id_rejects_other_links(url):

    assert parse_video_id(url) is None


# ============================================================
# TRANSCRIPT SEGMENTS
# ============================================================

def test_timestamps_and_segments():

    assert timestamp_seconds("[01:05] Oxygen") == 65
    assert timestamp_seconds("[1:02:03] Late") == 3723
    assert timestamp_seconds("No time") is None

    segments = transcript_segments(FAKE_TRANSCRIPT)
    text = "\n".join(segment["text"] for segment in segments)

    # Untimed lines join the previous line.
    assert "absorbs light. this line continues" in text

    for segment in segments:
        assert segment["page_number"] is None
        assert segment["text"].startswith("[")
        assert len(segment["text"]) <= 500


def test_long_transcripts_split_into_timestamped_segments():

    transcript = "\n".join(
        f"[{minute:02d}:00] " + "word " * 30
        for minute in range(40)
    )

    segments = transcript_segments(transcript)

    assert len(segments) > 5
    assert all(segment["text"].startswith("[") for segment in segments)


# ============================================================
# ADD A VIDEO
# ============================================================

def test_add_video_creates_a_searchable_transcript():

    user_id, headers = make_user("Video User")

    response = client.post(
        "/api/v1/youtube",
        headers=headers,
        json={"url": "https://youtu.be/dQw4w9WgXcQ"},
    )

    assert response.status_code == 200, response.text
    assert response.json()["status"] == "processing"

    document = client.get(
        f"/api/v1/documents/{response.json()['id']}",
        headers=headers,
    ).json()

    assert document["status"] == "completed"
    assert document["filename"] == "Photosynthesis in 2 minutes"
    assert document["processing_type"] == "youtube"
    assert document["video_id"] == "dQw4w9WgXcQ"
    assert document["author"] == "Science Channel"
    assert document["duration_seconds"] == 65

    chunks = list(
        test_db.document_chunks.find(
            {"document_id": response.json()["id"]}
        )
    )

    assert chunks
    assert all(chunk["text"].startswith("[") for chunk in chunks)

    # Adding the same video again returns the existing one.
    again = client.post(
        "/api/v1/youtube",
        headers=headers,
        json={"url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"},
    )

    assert again.json()["already_added"] is True
    assert again.json()["id"] == response.json()["id"]


def test_add_video_rejects_bad_links_and_private_videos(monkeypatch):

    _, headers = make_user("Bad Link User")

    bad = client.post(
        "/api/v1/youtube",
        headers=headers,
        json={"url": "https://vimeo.com/123456"},
    )

    assert bad.status_code == 400

    def private(video_id):
        raise ValueError("This video is private, removed, or does not exist.")

    monkeypatch.setattr(
        youtube_service,
        "fetch_video_info",
        private,
    )

    monkeypatch.setattr(
        "app.routes.youtube.fetch_video_info",
        private,
    )

    hidden = client.post(
        "/api/v1/youtube",
        headers=headers,
        json={"url": "https://youtu.be/aaaaaaaaaaa"},
    )

    assert hidden.status_code == 400
    assert "private" in hidden.json()["detail"]


def test_failed_transcription_is_reported(monkeypatch):

    _, headers = make_user("Failing Video User")

    def broken(url, prompt):
        raise RuntimeError("video too long")

    monkeypatch.setattr(
        youtube_service,
        "generate_from_youtube",
        broken,
    )

    response = client.post(
        "/api/v1/youtube",
        headers=headers,
        json={"url": "https://youtu.be/bbbbbbbbbbb"},
    )

    document = client.get(
        f"/api/v1/documents/{response.json()['id']}",
        headers=headers,
    ).json()

    assert document["status"] == "failed"
    assert "could not watch" in document["processing_error"]


# ============================================================
# VERY BRIEF ANSWERS FOR VIDEO CHATS
# ============================================================

def test_video_chats_use_brief_answer_rules(monkeypatch):

    _, headers = make_user("Brief User")

    video = client.post(
        "/api/v1/youtube",
        headers=headers,
        json={"url": "https://youtu.be/ccccccccccc"},
    ).json()

    prompts = []

    monkeypatch.setattr(
        chat_rag_service,
        "generate_answer",
        lambda prompt: prompts.append(prompt) or "Chlorophyll absorbs light [00:31].",
    )

    chat = client.post(
        "/api/v1/chats",
        headers=headers,
        json={"title": "Video chat", "document_id": video["id"]},
    ).json()

    response = client.post(
        f"/api/v1/chats/{chat['id']}/ask",
        headers=headers,
        json={"question": "What absorbs light?"},
    )

    assert response.status_code == 200, response.text
    assert "VERY BRIEF" in prompts[0]
    assert "[00:31] Chlorophyll" in prompts[0]

    # Normal document chats keep the detailed style.
    plain_chat = client.post(
        "/api/v1/chats",
        headers=headers,
        json={"title": "All documents"},
    ).json()

    client.post(
        f"/api/v1/chats/{plain_chat['id']}/ask",
        headers=headers,
        json={"question": "What absorbs light?"},
    )

    assert "VERY BRIEF" not in prompts[1]
