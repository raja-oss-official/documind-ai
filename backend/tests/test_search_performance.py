import time
import uuid

from bson import ObjectId
from pymongo import MongoClient

from app.core.config import settings
from app.services.search_service import search_documents


mongo_client = MongoClient(
    settings.mongodb_url
)

test_db = mongo_client[
    settings.database_name
]


TEST_USER_ID = str(
    ObjectId()
)


def setup_function():

    test_db.document_chunks.delete_many(
        {
            "user_id": TEST_USER_ID
        }
    )


def teardown_function():

    test_db.document_chunks.delete_many(
        {
            "user_id": TEST_USER_ID
        }
    )


def create_test_chunks(
    count: int = 500
):

    documents = []

    for index in range(count):

        documents.append(
            {
                "user_id": TEST_USER_ID,
                "document_id": str(
                    ObjectId()
                ),
                "chunk_index": index,
                "text": (
                    f"DocuMind AI test document "
                    f"chunk {index}. "
                    f"This document contains "
                    f"information about artificial "
                    f"intelligence, document search, "
                    f"security and retrieval."
                ),
                "embedding": [],
                "chunk_id": (
                    f"chunk_{uuid.uuid4().hex}"
                ),
            }
        )

    if documents:

        test_db.document_chunks.insert_many(
            documents
        )


def test_search_performance():

    create_test_chunks(
        500
    )

    start_time = time.perf_counter()

    results = search_documents(
        user_id=TEST_USER_ID,
        query="document search",
        limit=5,
    )

    elapsed_time = (
        time.perf_counter() - start_time
    )

    assert isinstance(
        results,
        list,
    )

    print(
        f"\nChunks searched: 500"
    )

    print(
        f"Results returned: "
        f"{len(results)}"
    )

    print(
        f"Search time: "
        f"{elapsed_time:.4f} seconds"
    )

    assert elapsed_time < 5.0


def test_search_respects_user_isolation():

    create_test_chunks(
        100
    )

    other_user_id = str(
        ObjectId()
    )

    test_db.document_chunks.insert_one(
        {
            "user_id": other_user_id,
            "document_id": str(
                ObjectId()
            ),
            "chunk_index": 0,
            "text": (
                "SECRET DATA FROM ANOTHER USER"
            ),
            "embedding": [],
            "chunk_id": (
                f"other_{uuid.uuid4().hex}"
            ),
        }
    )

    results = search_documents(
        user_id=TEST_USER_ID,
        query="SECRET DATA",
        limit=10,
    )

    for result in results:

        assert (
            result.get("user_id")
            != other_user_id
        )