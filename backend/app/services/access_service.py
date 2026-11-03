# ============================================================
# IMPORTS
# ============================================================

from bson import ObjectId

from app.core.database import db


# ============================================================
# ROLES
# ============================================================
#
# owner  - uploaded the document; can do everything,
#          including delete and share.
#
# editor - can rename and regenerate the summary, plus
#          everything a viewer can do.
#
# viewer - can open, search, ask questions, chat, and use
#          the study and fact tools.
#
# Every document and chunk is still stored with the
# owner's user_id. Shared access is granted through the
# document_shares collection.

ROLE_RANK = {
    "viewer":
        1,
    "editor":
        2,
    "owner":
        3
}

SHARE_ROLES = {
    "viewer",
    "editor"
}


# ============================================================
# ROLE CHECK
# ============================================================

def role_allows(
    role: str | None,
    required: str
) -> bool:
    """
    Return whether a role is at least the required role.
    """

    return ROLE_RANK.get(
        role,
        0
    ) >= ROLE_RANK[required]


# ============================================================
# GET ACCESSIBLE DOCUMENT
# ============================================================

def get_accessible_document(
    document_id: str,
    user_id: str
):
    """
    Return a document the user owns or that was shared
    with them, with two extra fields:

        role      - owner, editor, or viewer
        owner_id  - the user_id the document is stored under

    Returns None when the document does not exist or the
    user has no access. Callers respond with 404 in both
    cases so the existence of other users' documents is
    never revealed.
    """

    if not document_id or not ObjectId.is_valid(
        document_id
    ):
        return None

    document = db.documents.find_one({
        "_id":
            ObjectId(
                document_id
            )
    })

    if not document:
        return None

    owner_id = document.get(
        "user_id"
    )

    # --------------------------------------------------------
    # Owner
    # --------------------------------------------------------

    if owner_id == user_id:

        document["role"] = "owner"
        document["owner_id"] = owner_id

        return document

    # --------------------------------------------------------
    # Shared with this user
    # --------------------------------------------------------

    share = db.document_shares.find_one({
        "document_id":
            document_id,
        "shared_with_user_id":
            user_id
    })

    if not share:
        return None

    document["role"] = share.get(
        "role",
        "viewer"
    )
    document["owner_id"] = owner_id

    return document


# ============================================================
# DOCUMENT OWNER ID
# ============================================================

def document_owner_id(
    document_id: str,
    user_id: str
):
    """
    Return the user_id a document's chunks are stored
    under, or None when the user has no access.
    """

    document = get_accessible_document(
        document_id=document_id,
        user_id=user_id
    )

    if not document:
        return None

    return document["owner_id"]


# ============================================================
# DOCUMENTS SHARED WITH A USER
# ============================================================

def shared_document_ids(
    user_id: str
) -> list[str]:
    """
    Return the IDs of documents shared with the user.
    """

    shares = db.document_shares.find(
        {
            "shared_with_user_id":
                user_id
        },
        {
            "document_id":
                1
        }
    )

    return [
        share["document_id"]
        for share in shares
    ]


# ============================================================
# YOUTUBE VIDEOS (KEPT OUT OF DOCUMENT FEATURES)
# ============================================================

def video_document_ids(
    user_id: str
) -> list[str]:
    """
    Return the IDs of the user's YouTube video documents.

    Videos belong to YT AI Chat only, so AI Chat, Ask AI and
    AI Search across "all documents" leave them out.
    """

    videos = db.documents.find(
        {
            "user_id":
                user_id,
            "processing_type":
                "youtube"
        },
        {
            "_id":
                1
        }
    )

    return [
        str(video["_id"])
        for video in videos
    ]


# ============================================================
# CHUNK ACCESS FILTER
# ============================================================

def chunk_access_filter(
    user_id: str,
    document_id: str | None = None
):
    """
    Build the MongoDB filter for chunks the user may read.

    One document:
        {"user_id": <owner>, "document_id": <id>}
        (uses the document_id + user_id index)

    All documents, nothing shared:
        {"user_id": <user>}
        (unchanged from before sharing existed)

    All documents, some shared:
        own chunks OR chunks of shared documents

    "All documents" never includes YouTube videos: they are
    only used when one video is requested (YT AI Chat).

    Returns None when the user cannot read the document.
    """

    if document_id:

        owner_id = document_owner_id(
            document_id=document_id,
            user_id=user_id
        )

        if not owner_id:
            return None

        return {
            "user_id":
                owner_id,
            "document_id":
                document_id
        }

    shared_ids = shared_document_ids(
        user_id
    )

    if not shared_ids:

        access_filter = {
            "user_id":
                user_id
        }

    else:

        access_filter = {
            "$or": [
                {
                    "user_id":
                        user_id
                },
                {
                    "document_id": {
                        "$in":
                            shared_ids
                    }
                }
            ]
        }

    video_ids = video_document_ids(
        user_id
    )

    if video_ids:

        access_filter[
            "document_id"
        ] = {
            "$nin":
                video_ids
        }

    return access_filter
