# ============================================================
# IMPORTS
# ============================================================

from bson import ObjectId
from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Request,
    status,
)
from fastapi.security import HTTPAuthorizationCredentials

from app.core.database import db
from app.core.rate_limiter import limiter
from app.core.security import (
    security,
    verify_access_token,
)
from app.schemas.document import ShareRequest
from app.services.access_service import (
    get_accessible_document,
)
from app.services.chat_service import (
    get_chat_session,
)
from app.services.sharing_service import (
    get_shared_chat_messages,
    list_chat_shares,
    list_document_shares,
    list_shared_chats,
    remove_chat_share,
    remove_document_share,
    share_chat,
    share_document,
)


# ============================================================
# ROUTERS
# ============================================================
#
# document_router is mounted at /api/v1/documents,
# chat_router at /api/v1/chats (before the chats router, so
# /chats/shared is not read as a chat ID).

document_router = APIRouter()

chat_router = APIRouter()


# ============================================================
# AUTHENTICATION
# ============================================================

def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(
        security
    ),
):

    return verify_access_token(
        credentials
    )


# ============================================================
# OWNED DOCUMENT
# ============================================================

def get_owned_document(
    document_id: str,
    user_id: str,
):

    """
    Return a document the user owns. Viewers and editors
    get 403; everyone else 404.
    """

    document = get_accessible_document(
        document_id=document_id,
        user_id=user_id,
    )

    if not document:

        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )

    if document["role"] != "owner":

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the owner can manage sharing",
        )

    return document


# ============================================================
# OWNED CHAT
# ============================================================

def get_owned_chat(
    session_id: str,
    user_id: str,
):

    if not ObjectId.is_valid(
        session_id
    ):

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid chat session ID",
        )

    session = get_chat_session(
        session_id=session_id,
        user_id=user_id,
    )

    if not session:

        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Chat session not found",
        )

    return session


# ============================================================
# DOCUMENT SHARES
# ============================================================

@document_router.get("/{document_id}/shares")
def get_document_shares(
    document_id: str,
    user_id: str = Depends(
        get_current_user
    ),
):

    get_owned_document(
        document_id=document_id,
        user_id=user_id,
    )

    return list_document_shares(
        document_id
    )


@document_router.post("/{document_id}/shares")
@limiter.limit("10/minute")
def add_document_share(
    request: Request,
    document_id: str,
    share: ShareRequest,
    user_id: str = Depends(
        get_current_user
    ),
):

    get_owned_document(
        document_id=document_id,
        user_id=user_id,
    )

    try:

        return share_document(
            document_id=document_id,
            owner_id=user_id,
            email=share.email,
            role=share.role,
        )

    except ValueError as error:

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error),
        )


@document_router.delete("/{document_id}/shares/{shared_user_id}")
def delete_document_share(
    document_id: str,
    shared_user_id: str,
    user_id: str = Depends(
        get_current_user
    ),
):

    """
    The owner can remove anyone; a recipient can remove
    a document shared with them from their own list.
    """

    document = get_accessible_document(
        document_id=document_id,
        user_id=user_id,
    )

    if not document:

        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )

    if document["role"] != "owner" and shared_user_id != user_id:

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the owner can manage sharing",
        )

    if not remove_document_share(
        document_id=document_id,
        shared_with_user_id=shared_user_id,
    ):

        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Share not found",
        )

    return {
        "message": "Sharing removed",
        "document_id": document_id,
        "user_id": shared_user_id,
    }


# ============================================================
# CHATS SHARED WITH ME
# ============================================================

@chat_router.get("/shared")
def get_shared_chats(
    user_id: str = Depends(
        get_current_user
    ),
):

    return list_shared_chats(
        user_id
    )


@chat_router.get("/shared/{session_id}/messages")
def get_shared_messages(
    session_id: str,
    user_id: str = Depends(
        get_current_user
    ),
):

    messages = get_shared_chat_messages(
        session_id=session_id,
        user_id=user_id,
    )

    if messages is None:

        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Chat session not found",
        )

    return messages


# ============================================================
# CHAT SHARES (READ-ONLY)
# ============================================================

@chat_router.get("/{session_id}/shares")
def get_chat_shares(
    session_id: str,
    user_id: str = Depends(
        get_current_user
    ),
):

    get_owned_chat(
        session_id=session_id,
        user_id=user_id,
    )

    return list_chat_shares(
        session_id
    )


@chat_router.post("/{session_id}/shares")
@limiter.limit("10/minute")
def add_chat_share(
    request: Request,
    session_id: str,
    share: ShareRequest,
    user_id: str = Depends(
        get_current_user
    ),
):

    get_owned_chat(
        session_id=session_id,
        user_id=user_id,
    )

    try:

        return share_chat(
            session_id=session_id,
            owner_id=user_id,
            email=share.email,
        )

    except ValueError as error:

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error),
        )


@chat_router.delete("/{session_id}/shares/{shared_user_id}")
def delete_chat_share(
    session_id: str,
    shared_user_id: str,
    user_id: str = Depends(
        get_current_user
    ),
):

    """
    The owner can remove anyone; a recipient can remove a
    chat shared with them from their own list.
    """

    is_owner = ObjectId.is_valid(session_id) and db.chat_sessions.find_one(
        {
            "_id": ObjectId(session_id),
            "user_id": user_id,
        },
        {
            "_id": 1,
        },
    )

    if not is_owner and shared_user_id != user_id:

        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Chat session not found",
        )

    if not remove_chat_share(
        session_id=session_id,
        shared_with_user_id=shared_user_id,
    ):

        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Share not found",
        )

    return {
        "message": "Sharing removed",
        "session_id": session_id,
        "user_id": shared_user_id,
    }
