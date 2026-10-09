import time
import uuid
from datetime import datetime, timezone, timedelta

from bson import ObjectId
from pymongo import MongoClient

from app.core.config import settings


mongo_client = MongoClient(
    settings.mongodb_url
)

test_db = mongo_client[
    settings.database_name
]


USER_A = str(ObjectId())
USER_B = str(ObjectId())


def setup_function():

    test_db.documents.delete_many(
        {
            "user_id": {
                "$in": [
                    USER_A,
                    USER_B,
                ]
            }
        }
    )

    test_db.chat_sessions.delete_many(
        {
            "user_id": {
                "$in": [
                    USER_A,
                    USER_B,
                ]
            }
        }
    )

    test_db.chat_messages.delete_many(
        {
            "user_id": {
                "$in": [
                    USER_A,
                    USER_B,
                ]
            }
        }
    )

    test_db.refresh_tokens.delete_many(
        {
            "user_id": {
                "$in": [
                    USER_A,
                    USER_B,
                ]
            }
        }
    )


def teardown_function():

    test_db.documents.delete_many(
        {
            "user_id": {
                "$in": [
                    USER_A,
                    USER_B,
                ]
            }
        }
    )

    test_db.chat_sessions.delete_many(
        {
            "user_id": {
                "$in": [
                    USER_A,
                    USER_B,
                ]
            }
        }
    )

    test_db.chat_messages.delete_many(
        {
            "user_id": {
                "$in": [
                    USER_A,
                    USER_B,
                ]
            }
        }
    )

    test_db.refresh_tokens.delete_many(
        {
            "user_id": {
                "$in": [
                    USER_A,
                    USER_B,
                ]
            }
        }
    )


def create_documents(
    user_id: str,
    count: int = 1000,
):

    documents = []

    now = datetime.now(
        timezone.utc
    )

    for index in range(count):

        documents.append(
            {
                "user_id": user_id,
                "filename": (
                    f"test_document_{index}.pdf"
                ),
                "file_type": "pdf",
                "file_size": 1024,
                "status": "completed",
                "created_at": (
                    now + timedelta(
                        seconds=index
                    )
                ),
            }
        )

    test_db.documents.insert_many(
        documents
    )


def create_chat_sessions(
    user_id: str,
    count: int = 500,
):

    sessions = []

    now = datetime.now(
        timezone.utc
    )

    for index in range(count):

        sessions.append(
            {
                "user_id": user_id,
                "title": (
                    f"Test Chat {index}"
                ),
                "document_id": None,
                "created_at": (
                    now + timedelta(
                        seconds=index
                    )
                ),
                "updated_at": (
                    now + timedelta(
                        seconds=index
                    )
                ),
            }
        )

    result = test_db.chat_sessions.insert_many(
        sessions
    )

    return list(
        result.inserted_ids
    )


def create_chat_messages(
    user_id: str,
    session_ids,
):

    messages = []

    now = datetime.now(
        timezone.utc
    )

    for index, session_id in enumerate(
        session_ids
    ):

        messages.append(
            {
                "session_id": session_id,
                "user_id": user_id,
                "role": "user",
                "content": (
                    f"Test message {index}"
                ),
                "document_id": None,
                "created_at": (
                    now + timedelta(
                        seconds=index
                    )
                ),
            }
        )

    if messages:

        test_db.chat_messages.insert_many(
            messages
        )


def test_document_query_is_user_scoped():

    create_documents(
        USER_A,
        1000,
    )

    create_documents(
        USER_B,
        1000,
    )

    start_time = time.perf_counter()

    user_a_documents = list(
        test_db.documents.find(
            {
                "user_id": USER_A
            }
        )
    )

    elapsed_time = (
        time.perf_counter()
        - start_time
    )

    assert len(
        user_a_documents
    ) == 1000

    for document in user_a_documents:

        assert document[
            "user_id"
        ] == USER_A

    print(
        f"\nUser A documents returned: "
        f"{len(user_a_documents)}"
    )

    print(
        f"Document query time: "
        f"{elapsed_time:.4f} seconds"
    )

    assert elapsed_time < 2.0


def test_chat_session_query_is_user_scoped():

    create_chat_sessions(
        USER_A,
        500,
    )

    create_chat_sessions(
        USER_B,
        500,
    )

    start_time = time.perf_counter()

    user_a_sessions = list(
        test_db.chat_sessions.find(
            {
                "user_id": USER_A
            }
        )
    )

    elapsed_time = (
        time.perf_counter()
        - start_time
    )

    assert len(
        user_a_sessions
    ) == 500

    for session in user_a_sessions:

        assert session[
            "user_id"
        ] == USER_A

    print(
        f"\nUser A sessions returned: "
        f"{len(user_a_sessions)}"
    )

    print(
        f"Chat session query time: "
        f"{elapsed_time:.4f} seconds"
    )

    assert elapsed_time < 2.0


def test_chat_message_query_is_user_and_session_scoped():

    user_a_sessions = create_chat_sessions(
        USER_A,
        100,
    )

    user_b_sessions = create_chat_sessions(
        USER_B,
        100,
    )

    create_chat_messages(
        USER_A,
        user_a_sessions,
    )

    create_chat_messages(
        USER_B,
        user_b_sessions,
    )

    target_session = (
        user_a_sessions[0]
    )

    messages = list(
        test_db.chat_messages.find(
            {
                "session_id": target_session,
                "user_id": USER_A,
            }
        )
    )

    assert len(messages) == 1

    for message in messages:

        assert message[
            "user_id"
        ] == USER_A

        assert message[
            "session_id"
        ] == target_session


def test_cross_user_document_data_is_not_returned():

    create_documents(
        USER_A,
        100,
    )

    create_documents(
        USER_B,
        100,
    )

    user_a_documents = list(
        test_db.documents.find(
            {
                "user_id": USER_A
            }
        )
    )

    assert len(
        user_a_documents
    ) == 100

    assert all(
        document["user_id"] == USER_A
        for document in user_a_documents
    )

    assert not any(
        document["user_id"] == USER_B
        for document in user_a_documents
    )


def test_refresh_token_query_is_user_scoped():

    now = datetime.now(
        timezone.utc
    )

    records = []

    for index in range(500):

        records.append(
            {
                "user_id": (
                    USER_A
                    if index % 2 == 0
                    else USER_B
                ),
                "token_hash": (
                    f"test_hash_"
                    f"{uuid.uuid4().hex}"
                ),
                "created_at": now,
                "expires_at": (
                    now + timedelta(
                        days=7
                    )
                ),
                "revoked_at": None,
            }
        )

    test_db.refresh_tokens.insert_many(
        records
    )

    start_time = time.perf_counter()

    user_a_tokens = list(
        test_db.refresh_tokens.find(
            {
                "user_id": USER_A
            }
        )
    )

    elapsed_time = (
        time.perf_counter()
        - start_time
    )

    assert len(
        user_a_tokens
    ) == 250

    for token in user_a_tokens:

        assert token[
            "user_id"
        ] == USER_A

    print(
        f"\nUser A refresh tokens: "
        f"{len(user_a_tokens)}"
    )

    print(
        f"Refresh-token query time: "
        f"{elapsed_time:.4f} seconds"
    )

    assert elapsed_time < 2.0