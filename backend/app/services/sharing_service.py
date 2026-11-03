# ============================================================
# IMPORTS
# ============================================================

from datetime import datetime, timezone

from bson import ObjectId

from app.core.database import db

from app.services.access_service import (
    SHARE_ROLES,
)

from app.services.chat_service import (
    get_chat_messages,
)


# ============================================================
# FIND USER BY EMAIL
# ============================================================

def find_user_by_email(
    email: str
):
    """
    Return the user with this email (normalized the same way
    as registration), or None.
    """

    return db.users.find_one(
        {
            "email":
                email.strip().lower()
        },
        {
            "name":
                1,
            "email":
                1
        }
    )


def user_summaries(
    user_ids: list[str]
) -> dict:
    """
    Return {user_id: {"name", "email"}} for the given IDs.
    """

    object_ids = [
        ObjectId(user_id)
        for user_id in user_ids
        if ObjectId.is_valid(user_id)
    ]

    users = db.users.find(
        {
            "_id": {
                "$in":
                    object_ids
            }
        },
        {
            "name":
                1,
            "email":
                1
        }
    )

    return {
        str(user["_id"]): {
            "name":
                user.get("name"),
            "email":
                user.get("email")
        }
        for user in users
    }


# ============================================================
# SHARE A DOCUMENT
# ============================================================

def share_document(
    document_id: str,
    owner_id: str,
    email: str,
    role: str
):
    """
    Share a document with another user (viewer or editor).

    Sharing again with the same user updates the role.
    Raises ValueError with a user-facing message.
    """

    if role not in SHARE_ROLES:

        raise ValueError(
            "Role must be viewer or editor"
        )

    recipient = find_user_by_email(
        email
    )

    if not recipient:

        raise ValueError(
            "No DocuMind AI account uses that email address"
        )

    recipient_id = str(
        recipient["_id"]
    )

    if recipient_id == owner_id:

        raise ValueError(
            "You already own this document"
        )

    now = datetime.now(
        timezone.utc
    )

    db.document_shares.update_one(
        {
            "document_id":
                document_id,
            "shared_with_user_id":
                recipient_id
        },
        {
            "$set": {
                "role":
                    role,
                "owner_id":
                    owner_id,
                "updated_at":
                    now
            },
            "$setOnInsert": {
                "created_at":
                    now
            }
        },
        upsert=True
    )

    return {
        "user_id":
            recipient_id,
        "name":
            recipient.get("name"),
        "email":
            recipient.get("email"),
        "role":
            role
    }


# ============================================================
# LIST DOCUMENT SHARES
# ============================================================

def list_document_shares(
    document_id: str
) -> list[dict]:
    """
    Return everyone a document is shared with.
    """

    shares = list(
        db.document_shares.find(
            {
                "document_id":
                    document_id
            }
        ).sort(
            "created_at",
            1
        )
    )

    users = user_summaries(
        [
            share["shared_with_user_id"]
            for share in shares
        ]
    )

    return [
        {
            "user_id":
                share["shared_with_user_id"],
            "name":
                users.get(
                    share["shared_with_user_id"],
                    {}
                ).get("name"),
            "email":
                users.get(
                    share["shared_with_user_id"],
                    {}
                ).get("email"),
            "role":
                share.get(
                    "role",
                    "viewer"
                ),
            "created_at":
                share.get(
                    "created_at"
                )
        }
        for share in shares
    ]


# ============================================================
# REMOVE A DOCUMENT SHARE
# ============================================================

def remove_document_share(
    document_id: str,
    shared_with_user_id: str
) -> bool:
    """
    Stop sharing a document with one user.
    """

    result = db.document_shares.delete_one(
        {
            "document_id":
                document_id,
            "shared_with_user_id":
                shared_with_user_id
        }
    )

    return result.deleted_count > 0


# ============================================================
# SHARE A CHAT (READ-ONLY)
# ============================================================

def share_chat(
    session_id: str,
    owner_id: str,
    email: str
):
    """
    Share a chat with another user, who can read it.
    Raises ValueError with a user-facing message.
    """

    recipient = find_user_by_email(
        email
    )

    if not recipient:

        raise ValueError(
            "No DocuMind AI account uses that email address"
        )

    recipient_id = str(
        recipient["_id"]
    )

    if recipient_id == owner_id:

        raise ValueError(
            "You already own this chat"
        )

    now = datetime.now(
        timezone.utc
    )

    db.chat_shares.update_one(
        {
            "session_id":
                session_id,
            "shared_with_user_id":
                recipient_id
        },
        {
            "$set": {
                "owner_id":
                    owner_id,
                "updated_at":
                    now
            },
            "$setOnInsert": {
                "created_at":
                    now
            }
        },
        upsert=True
    )

    return {
        "user_id":
            recipient_id,
        "name":
            recipient.get("name"),
        "email":
            recipient.get("email"),
        "role":
            "viewer"
    }


# ============================================================
# LIST CHAT SHARES
# ============================================================

def list_chat_shares(
    session_id: str
) -> list[dict]:
    """
    Return everyone a chat is shared with.
    """

    shares = list(
        db.chat_shares.find(
            {
                "session_id":
                    session_id
            }
        ).sort(
            "created_at",
            1
        )
    )

    users = user_summaries(
        [
            share["shared_with_user_id"]
            for share in shares
        ]
    )

    return [
        {
            "user_id":
                share["shared_with_user_id"],
            "name":
                users.get(
                    share["shared_with_user_id"],
                    {}
                ).get("name"),
            "email":
                users.get(
                    share["shared_with_user_id"],
                    {}
                ).get("email"),
            "role":
                "viewer",
            "created_at":
                share.get(
                    "created_at"
                )
        }
        for share in shares
    ]


# ============================================================
# REMOVE A CHAT SHARE
# ============================================================

def remove_chat_share(
    session_id: str,
    shared_with_user_id: str
) -> bool:
    """
    Stop sharing a chat with one user.
    """

    result = db.chat_shares.delete_one(
        {
            "session_id":
                session_id,
            "shared_with_user_id":
                shared_with_user_id
        }
    )

    return result.deleted_count > 0


# ============================================================
# CHATS SHARED WITH A USER
# ============================================================

def list_shared_chats(
    user_id: str
) -> list[dict]:
    """
    Return chats other users shared with this user, most
    recently active first.
    """

    shares = list(
        db.chat_shares.find(
            {
                "shared_with_user_id":
                    user_id
            }
        )
    )

    session_ids = [
        ObjectId(share["session_id"])
        for share in shares
        if ObjectId.is_valid(share["session_id"])
    ]

    sessions = list(
        db.chat_sessions.find(
            {
                "_id": {
                    "$in":
                        session_ids
                }
            }
        ).sort(
            "updated_at",
            -1
        )
    )

    owners = user_summaries(
        [
            session["user_id"]
            for session in sessions
        ]
    )

    return [
        {
            "id":
                str(session["_id"]),
            "title":
                session.get("title"),
            "document_id":
                session.get("document_id"),
            "created_at":
                session.get("created_at"),
            "updated_at":
                session.get("updated_at"),
            "owner_name":
                owners.get(
                    session["user_id"],
                    {}
                ).get("name"),
            "shared":
                True,
            "role":
                "viewer"
        }
        for session in sessions
    ]


# ============================================================
# MESSAGES OF A SHARED CHAT
# ============================================================

def get_shared_chat(
    session_id: str,
    user_id: str
):
    """
    Return a chat session shared with the user, or None.
    """

    if not ObjectId.is_valid(
        session_id
    ):
        return None

    share = db.chat_shares.find_one(
        {
            "session_id":
                session_id,
            "shared_with_user_id":
                user_id
        }
    )

    if not share:
        return None

    return db.chat_sessions.find_one(
        {
            "_id":
                ObjectId(session_id)
        }
    )


def get_shared_chat_messages(
    session_id: str,
    user_id: str
):
    """
    Return the messages of a chat shared with the user, or
    None when the chat is not shared with them.
    """

    session = get_shared_chat(
        session_id=session_id,
        user_id=user_id
    )

    if not session:
        return None

    return get_chat_messages(
        session_id=session_id,
        user_id=session["user_id"]
    )
