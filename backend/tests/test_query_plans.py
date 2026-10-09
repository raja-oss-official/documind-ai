from datetime import datetime, timezone

from bson import ObjectId
from pymongo import MongoClient

from app.core.config import settings


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

    test_db.documents.delete_many(
        {
            "user_id": TEST_USER_ID
        }
    )

    test_db.chat_sessions.delete_many(
        {
            "user_id": TEST_USER_ID
        }
    )

    test_db.chat_messages.delete_many(
        {
            "user_id": TEST_USER_ID
        }
    )


def teardown_function():

    test_db.documents.delete_many(
        {
            "user_id": TEST_USER_ID
        }
    )

    test_db.chat_sessions.delete_many(
        {
            "user_id": TEST_USER_ID
        }
    )

    test_db.chat_messages.delete_many(
        {
            "user_id": TEST_USER_ID
        }
    )


def create_test_data():

    now = datetime.now(
        timezone.utc
    )

    documents = []

    for index in range(1000):

        documents.append(
            {
                "user_id": TEST_USER_ID,
                "filename": (
                    f"query_plan_{index}.pdf"
                ),
                "file_type": "pdf",
                "file_size": 1024,
                "status": "completed",
                "created_at": now,
            }
        )

    test_db.documents.insert_many(
        documents
    )

    session_ids = []

    sessions = []

    for index in range(500):

        session_id = ObjectId()

        session_ids.append(
            session_id
        )

        sessions.append(
            {
                "_id": session_id,
                "user_id": TEST_USER_ID,
                "title": (
                    f"Query Plan Chat {index}"
                ),
                "document_id": None,
                "created_at": now,
                "updated_at": now,
            }
        )

    test_db.chat_sessions.insert_many(
        sessions
    )

    messages = []

    for index, session_id in enumerate(
        session_ids
    ):

        messages.append(
            {
                "session_id": session_id,
                "user_id": TEST_USER_ID,
                "role": "user",
                "content": (
                    f"Query plan test message "
                    f"{index}"
                ),
                "document_id": None,
                "created_at": now,
            }
        )

    test_db.chat_messages.insert_many(
        messages
    )

    return session_ids


def explain_find_query(
    collection,
    filter_query,
    sort=None,
):
    """
    Run MongoDB explain using the database
    command API.

    This avoids PyMongo Cursor.explain()
    signature differences between versions.
    """

    command = {
        "explain": {
            "find": collection.name,
            "filter": filter_query,
        },
        "verbosity": "executionStats",
    }

    if sort:
        command["explain"]["sort"] = sort

    return collection.database.command(
        command
    )


def get_stage_names(
    explain_result,
):
    """
    Recursively collect MongoDB execution
    stage names from the winning plan.
    """

    stage_names = []

    def collect_stages(stage):

        if not isinstance(
            stage,
            dict,
        ):
            return

        stage_name = stage.get(
            "stage"
        )

        if stage_name:
            stage_names.append(
                stage_name
            )

        input_stage = stage.get(
            "inputStage"
        )

        if input_stage:
            collect_stages(
                input_stage
            )

        input_stages = stage.get(
            "inputStages",
            []
        )

        for child in input_stages:

            collect_stages(
                child
            )

        shards = stage.get(
            "shards",
            []
        )

        for shard in shards:

            collect_stages(
                shard
            )

    query_planner = (
        explain_result.get(
            "queryPlanner",
            {}
        )
    )

    winning_plan = (
        query_planner.get(
            "winningPlan",
            {}
        )
    )

    collect_stages(
        winning_plan
    )

    execution_stats = (
        explain_result.get(
            "executionStats",
            {}
        )
    )

    execution_stages = (
        execution_stats.get(
            "executionStages",
            {}
        )
    )

    collect_stages(
        execution_stages
    )

    return stage_names


def assert_index_used(
    explain_result,
):

    stage_names = get_stage_names(
        explain_result
    )

    assert stage_names, (
        "MongoDB did not return any "
        "execution stages."
    )

    assert "COLLSCAN" not in (
        stage_names
    ), (
        "MongoDB used COLLSCAN instead "
        "of an index. "
        f"Stages: {stage_names}"
    )

    assert (
        "IXSCAN" in stage_names
        or "DISTINCT_SCAN" in stage_names
        or "COUNT_SCAN" in stage_names
    ), (
        "MongoDB did not report an "
        "index-based execution stage. "
        f"Stages: {stage_names}"
    )


def test_document_user_query_uses_index():

    create_test_data()

    explain_result = explain_find_query(
        test_db.documents,
        {
            "user_id": TEST_USER_ID
        },
    )

    assert_index_used(
        explain_result
    )


def test_document_user_created_query_uses_index():

    create_test_data()

    explain_result = explain_find_query(
        test_db.documents,
        {
            "user_id": TEST_USER_ID
        },
        sort={
            "created_at": -1
        },
    )

    assert_index_used(
        explain_result
    )


def test_chat_session_user_query_uses_index():

    create_test_data()

    explain_result = explain_find_query(
        test_db.chat_sessions,
        {
            "user_id": TEST_USER_ID
        },
    )

    assert_index_used(
        explain_result
    )


def test_chat_session_updated_query_uses_index():

    create_test_data()

    explain_result = explain_find_query(
        test_db.chat_sessions,
        {
            "user_id": TEST_USER_ID
        },
        sort={
            "updated_at": -1
        },
    )

    assert_index_used(
        explain_result
    )


def test_chat_message_session_user_query_uses_index():

    session_ids = create_test_data()

    target_session = (
        session_ids[0]
    )

    explain_result = explain_find_query(
        test_db.chat_messages,
        {
            "session_id": target_session,
            "user_id": TEST_USER_ID,
        },
    )

    assert_index_used(
        explain_result
    )