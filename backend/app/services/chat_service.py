# ============================================================
# IMPORTS
# ============================================================

from datetime import datetime, timezone

from bson import ObjectId

from app.core.database import db

from app.services.document_service import (
    get_user_document
)


# ============================================================
# OBJECT ID VALIDATION
# ============================================================

def is_valid_object_id(
    value: str
):
    """
    Check whether a value is a valid MongoDB ObjectId.
    """

    try:

        ObjectId(value)

        return True

    except Exception:

        return False


# ============================================================
# CREATE CHAT SESSION
# ============================================================

def create_chat_session(
    user_id: str,
    title: str = "New Chat",
    document_id: str | None = None
):
    """
    Create a new chat session.

    If a document is attached, verify that the document
    belongs to the authenticated user.
    """

    title = title.strip()

    if not title:

        title = "New Chat"

    # --------------------------------------------------------
    # Validate document ownership
    # --------------------------------------------------------

    if document_id is not None:

        document = get_user_document(
            document_id=document_id,
            user_id=user_id
        )

        if not document:

            raise ValueError(
                "Document not found or does not belong to the user"
            )

    # --------------------------------------------------------
    # Create session
    # --------------------------------------------------------

    now = datetime.now(
        timezone.utc
    )

    session = {
        "user_id":
            user_id,

        "title":
            title,

        "document_id":
            document_id,

        "created_at":
            now,

        "updated_at":
            now
    }

    result = db.chat_sessions.insert_one(
        session
    )

    return {
        "id":
            str(
                result.inserted_id
            ),

        "user_id":
            user_id,

        "title":
            title,

        "document_id":
            document_id,

        "created_at":
            now,

        "updated_at":
            now
    }


# ============================================================
# GET CHAT SESSION
# ============================================================

def get_chat_session(
    session_id: str,
    user_id: str
):
    """
    Get a chat session belonging to the authenticated user.
    """

    # --------------------------------------------------------
    # Validate ObjectId
    # --------------------------------------------------------

    if not is_valid_object_id(
        session_id
    ):

        return None

    session = db.chat_sessions.find_one({

        "_id":
            ObjectId(
                session_id
            ),

        "user_id":
            user_id
    })

    if not session:

        return None

    return {
        "id":
            str(
                session["_id"]
            ),

        "user_id":
            session["user_id"],

        "title":
            session.get(
                "title",
                "New Chat"
            ),

        "document_id":
            session.get(
                "document_id"
            ),

        "created_at":
            session["created_at"],

        "updated_at":
            session["updated_at"]
    }


# ============================================================
# LIST CHAT SESSIONS
# ============================================================

def list_chat_sessions(
    user_id: str
):
    """
    Return all chat sessions belonging to the user.

    Most recently updated chats are returned first.
    """

    sessions = (
        db.chat_sessions.find(
            {
                "user_id":
                    user_id
            }
        )
        .sort(
            "updated_at",
            -1
        )
    )

    result = []

    for session in sessions:

        result.append({

            "id":
                str(
                    session["_id"]
                ),

            "user_id":
                session["user_id"],

            "title":
                session.get(
                    "title",
                    "New Chat"
                ),

            "document_id":
                session.get(
                    "document_id"
                ),

            "created_at":
                session["created_at"],

            "updated_at":
                session["updated_at"]
        })

    return result


# ============================================================
# UPDATE CHAT SESSION
# ============================================================

def update_chat_session(
    session_id: str,
    user_id: str,
    title: str | None = None,
    document_id: str | None = None
):
    """
    Update chat session title and/or attached document.

    The session must belong to the authenticated user.

    If a new document is supplied, ownership is verified.
    """

    # --------------------------------------------------------
    # Validate session ID
    # --------------------------------------------------------

    if not is_valid_object_id(
        session_id
    ):

        return False

    # --------------------------------------------------------
    # Verify session ownership
    # --------------------------------------------------------

    session = db.chat_sessions.find_one({

        "_id":
            ObjectId(
                session_id
            ),

        "user_id":
            user_id
    })

    if not session:

        return False

    # --------------------------------------------------------
    # Validate title
    # --------------------------------------------------------

    if title is not None:

        title = title.strip()

        if not title:

            raise ValueError(
                "Chat title cannot be empty"
            )

    # --------------------------------------------------------
    # Validate document ownership
    # --------------------------------------------------------

    if document_id is not None:

        document = get_user_document(
            document_id=document_id,
            user_id=user_id
        )

        if not document:

            raise ValueError(
                "Document not found or does not belong to the user"
            )

    # --------------------------------------------------------
    # Prepare update
    # --------------------------------------------------------

    update_data = {}

    if title is not None:

        update_data[
            "title"
        ] = title

    if document_id is not None:

        update_data[
            "document_id"
        ] = document_id

    update_data[
        "updated_at"
    ] = datetime.now(
        timezone.utc
    )

    # --------------------------------------------------------
    # Update session
    # --------------------------------------------------------

    result = db.chat_sessions.update_one(

        {
            "_id":
                ObjectId(
                    session_id
                ),

            "user_id":
                user_id
        },

        {
            "$set":
                update_data
        }
    )

    return result.matched_count > 0


# ============================================================
# DELETE CHAT SESSION
# ============================================================

def delete_chat_session(
    session_id: str,
    user_id: str
):
    """
    Delete a chat session and all messages belonging to it.
    """

    # --------------------------------------------------------
    # Validate session ID
    # --------------------------------------------------------

    if not is_valid_object_id(
        session_id
    ):

        return False

    # --------------------------------------------------------
    # Delete session
    # --------------------------------------------------------

    result = db.chat_sessions.delete_one({

        "_id":
            ObjectId(
                session_id
            ),

        "user_id":
            user_id
    })

    if result.deleted_count == 0:

        return False

    # --------------------------------------------------------
    # Delete associated messages
    # --------------------------------------------------------

    db.chat_messages.delete_many({

        "session_id":
            session_id,

        "user_id":
            user_id
    })

    return True


# ============================================================
# CREATE CHAT MESSAGE
# ============================================================

def create_chat_message(
    session_id: str,
    user_id: str,
    role: str,
    content: str,
    document_id: str | None = None
):
    """
    Create a user or assistant chat message.

    The message always inherits the document attached
    to the chat session.

    This prevents a caller from attaching an unrelated
    document to an individual message.
    """

    # --------------------------------------------------------
    # Validate session ID
    # --------------------------------------------------------

    if not is_valid_object_id(
        session_id
    ):

        raise ValueError(
            "Invalid chat session ID"
        )

    # --------------------------------------------------------
    # Validate role
    # --------------------------------------------------------

    allowed_roles = {
        "user",
        "assistant"
    }

    if role not in allowed_roles:

        raise ValueError(
            "Invalid chat message role"
        )

    # --------------------------------------------------------
    # Validate content
    # --------------------------------------------------------

    if not isinstance(
        content,
        str
    ):

        raise ValueError(
            "Message content must be text"
        )

    content = content.strip()

    if not content:

        raise ValueError(
            "Message content cannot be empty"
        )

    # --------------------------------------------------------
    # Verify session ownership
    # --------------------------------------------------------

    session = db.chat_sessions.find_one({

        "_id":
            ObjectId(
                session_id
            ),

        "user_id":
            user_id
    })

    if not session:

        raise ValueError(
            "Chat session not found"
        )

    # --------------------------------------------------------
    # Get session document
    # --------------------------------------------------------

    session_document_id = session.get(
        "document_id"
    )

    # --------------------------------------------------------
    # Prevent unrelated document attachment
    # --------------------------------------------------------

    if document_id is not None:

        if document_id != session_document_id:

            raise ValueError(
                "Document does not belong to this chat session"
            )

    # --------------------------------------------------------
    # Always inherit session document
    # --------------------------------------------------------

    document_id = session_document_id

    # --------------------------------------------------------
    # Create message
    # --------------------------------------------------------

    now = datetime.now(
        timezone.utc
    )

    message = {

        "session_id":
            session_id,

        "user_id":
            user_id,

        "role":
            role,

        "content":
            content,

        "document_id":
            document_id,

        "created_at":
            now
    }

    result = db.chat_messages.insert_one(
        message
    )

    # --------------------------------------------------------
    # Update chat activity
    # --------------------------------------------------------

    db.chat_sessions.update_one(

        {
            "_id":
                ObjectId(
                    session_id
                ),

            "user_id":
                user_id
        },

        {
            "$set":
                {
                    "updated_at":
                        now
                }
        }
    )

    return {

        "id":
            str(
                result.inserted_id
            ),

        "session_id":
            session_id,

        "user_id":
            user_id,

        "role":
            role,

        "content":
            content,

        "document_id":
            document_id,

        "created_at":
            now
    }


# ============================================================
# GET CHAT MESSAGES
# ============================================================

def get_chat_messages(
    session_id: str,
    user_id: str
):
    """
    Return all messages belonging to a chat session.

    Messages are returned from oldest to newest so the
    frontend and conversational RAG engine receive the
    conversation in chronological order.
    """

    # --------------------------------------------------------
    # Validate session ID
    # --------------------------------------------------------

    if not is_valid_object_id(
        session_id
    ):

        return []

    # --------------------------------------------------------
    # Verify session ownership
    # --------------------------------------------------------

    session = db.chat_sessions.find_one({

        "_id":
            ObjectId(
                session_id
            ),

        "user_id":
            user_id
    })

    if not session:

        return []

    # --------------------------------------------------------
    # Get messages
    # --------------------------------------------------------

    messages = (
        db.chat_messages.find({

            "session_id":
                session_id,

            "user_id":
                user_id

        })
        .sort(
            "created_at",
            1
        )
    )

    # --------------------------------------------------------
    # Build response
    # --------------------------------------------------------

    result = []

    for message in messages:

        result.append({

            "id":
                str(
                    message["_id"]
                ),

            "session_id":
                message["session_id"],

            "user_id":
                message["user_id"],

            "role":
                message["role"],

            "content":
                message["content"],

            "document_id":
                message.get(
                    "document_id"
                ),

            "created_at":
                message["created_at"]
        })

    return result