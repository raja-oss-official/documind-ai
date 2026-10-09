from pymongo import MongoClient

from app.core.config import settings


mongo_client = MongoClient(
    settings.mongodb_url
)

test_db = mongo_client[
    settings.database_name
]


def get_index_names(
    collection_name: str,
) -> set[str]:

    indexes = test_db[
        collection_name
    ].list_indexes()

    return {
        index["name"]
        for index in indexes
    }


def test_users_indexes():

    indexes = get_index_names(
        "users"
    )

    assert "email_1" in indexes


def test_refresh_token_indexes():

    indexes = get_index_names(
        "refresh_tokens"
    )

    assert "token_hash_1" in indexes

    assert "expires_at_1" in indexes

    assert "user_id_1" in indexes


def test_document_indexes():

    indexes = get_index_names(
        "documents"
    )

    assert "user_id_1" in indexes

    assert (
        "user_id_1_created_at_-1"
        in indexes
    )


def test_document_chunk_indexes():

    indexes = get_index_names(
        "document_chunks"
    )

    assert (
        "document_id_1_user_id_1"
        in indexes
    )

    assert "user_id_1" in indexes


def test_chat_session_indexes():

    indexes = get_index_names(
        "chat_sessions"
    )

    assert "user_id_1" in indexes

    assert (
        "user_id_1_updated_at_-1"
        in indexes
    )


def test_chat_message_indexes():

    indexes = get_index_names(
        "chat_messages"
    )

    assert (
        "session_id_1_user_id_1"
        in indexes
    )

    assert (
        "session_id_1_created_at_1"
        in indexes
    )