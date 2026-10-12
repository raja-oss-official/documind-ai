# ============================================================
# IMPORTS
# ============================================================

from bson import ObjectId

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    status,
)

from app.schemas.chat import (
    ChatSessionCreate,
    ChatSessionUpdate,
    ChatSessionResponse,
    ChatMessageCreate,
    ChatMessageResponse,
    ChatQuestionRequest,
)

from app.core.security import (
    security,
    verify_access_token,
)

from app.services.chat_service import (
    create_chat_session,
    get_chat_session,
    list_chat_sessions,
    update_chat_session,
    delete_chat_session,
    create_chat_message,
    get_chat_messages,
)

from app.services.chat_rag_service import (
    ask_chat_question,
)


# ============================================================
# ROUTER
# ============================================================

router = APIRouter()


# ============================================================
# SESSION ID VALIDATION
# ============================================================

def validate_session_id(
    session_id: str,
):
    """
    Validate that the chat session ID is a valid
    MongoDB ObjectId.

    This prevents malformed IDs from reaching
    the database/service layer.
    """

    if not session_id:

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Session ID is required",
        )

    if not ObjectId.is_valid(
        session_id
    ):

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid chat session ID",
        )


# ============================================================
# AUTHENTICATION
# ============================================================

def get_current_user(
    credentials=Depends(security),
):

    return verify_access_token(
        credentials
    )


# ============================================================
# CREATE CHAT
# ============================================================

@router.post(
    "",
    response_model=ChatSessionResponse,
)
def create_chat(
    request: ChatSessionCreate,
    user_id: str = Depends(
        get_current_user
    ),
):

    try:

        session = create_chat_session(

            user_id=user_id,

            title=request.title,

            document_id=request.document_id,

        )

        return session

    except ValueError as error:

        raise HTTPException(

            status_code=status.HTTP_400_BAD_REQUEST,

            detail=str(error),

        )


# ============================================================
# LIST CHATS
# ============================================================

@router.get(
    "",
    response_model=list[ChatSessionResponse],
)
def get_chats(
    user_id: str = Depends(
        get_current_user
    ),
):

    sessions = list_chat_sessions(
        user_id
    )

    return sessions


# ============================================================
# GET CHAT
# ============================================================

@router.get(
    "/{session_id}",
    response_model=ChatSessionResponse,
)
def get_chat(

    session_id: str,

    user_id: str = Depends(
        get_current_user
    ),

):

    validate_session_id(
        session_id
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
# UPDATE CHAT
# ============================================================

@router.patch(
    "/{session_id}",
    response_model=ChatSessionResponse,
)
def update_chat(

    session_id: str,

    request: ChatSessionUpdate,

    user_id: str = Depends(
        get_current_user
    ),

):

    validate_session_id(
        session_id
    )

    # --------------------------------------------------------
    # Verify ownership
    # --------------------------------------------------------

    session = get_chat_session(

        session_id=session_id,

        user_id=user_id,

    )

    if not session:

        raise HTTPException(

            status_code=status.HTTP_404_NOT_FOUND,

            detail="Chat session not found",

        )

    # --------------------------------------------------------
    # Make sure something was provided
    # --------------------------------------------------------

    if (
        request.title is None
        and request.document_id is None
    ):

        raise HTTPException(

            status_code=status.HTTP_400_BAD_REQUEST,

            detail=(
                "No chat fields were provided "
                "for update"
            ),

        )

    try:

        updated = update_chat_session(

            session_id=session_id,

            user_id=user_id,

            title=request.title,

            document_id=request.document_id,

        )

        if not updated:

            raise HTTPException(

                status_code=status.HTTP_404_NOT_FOUND,

                detail="Chat session not found",

            )

    except ValueError as error:

        raise HTTPException(

            status_code=status.HTTP_400_BAD_REQUEST,

            detail=str(error),

        )

    # --------------------------------------------------------
    # Return updated session
    # --------------------------------------------------------

    updated_session = get_chat_session(

        session_id=session_id,

        user_id=user_id,

    )

    if not updated_session:

        raise HTTPException(

            status_code=status.HTTP_404_NOT_FOUND,

            detail="Chat session not found",

        )

    return updated_session


# ============================================================
# GET CHAT MESSAGES
# ============================================================

@router.get(
    "/{session_id}/messages",
    response_model=list[ChatMessageResponse],
)
def get_messages(

    session_id: str,

    user_id: str = Depends(
        get_current_user
    ),

):

    validate_session_id(
        session_id
    )

    # --------------------------------------------------------
    # Verify chat ownership
    # --------------------------------------------------------

    session = get_chat_session(

        session_id=session_id,

        user_id=user_id,

    )

    if not session:

        raise HTTPException(

            status_code=status.HTTP_404_NOT_FOUND,

            detail="Chat session not found",

        )

    messages = get_chat_messages(

        session_id=session_id,

        user_id=user_id,

    )

    return messages


# ============================================================
# CREATE USER MESSAGE
# ============================================================

@router.post(
    "/{session_id}/messages",
    response_model=ChatMessageResponse,
)
def create_message(

    session_id: str,

    request: ChatMessageCreate,

    user_id: str = Depends(
        get_current_user
    ),

):

    validate_session_id(
        session_id
    )

    # --------------------------------------------------------
    # Verify chat ownership
    # --------------------------------------------------------

    session = get_chat_session(

        session_id=session_id,

        user_id=user_id,

    )

    if not session:

        raise HTTPException(

            status_code=status.HTTP_404_NOT_FOUND,

            detail="Chat session not found",

        )

    content = request.content.strip()

    if not content:

        raise HTTPException(

            status_code=status.HTTP_400_BAD_REQUEST,

            detail="Message content cannot be empty",

        )

    try:

        message = create_chat_message(

            session_id=session_id,

            user_id=user_id,

            role="user",

            content=content,

            document_id=session.get(
                "document_id"
            ),

        )

        return message

    except ValueError as error:

        raise HTTPException(

            status_code=status.HTTP_400_BAD_REQUEST,

            detail=str(error),

        )


# ============================================================
# ASK QUESTION IN CHAT
# ============================================================

@router.post(
    "/{session_id}/ask",
)
def ask_question_in_chat(

    session_id: str,

    request: ChatQuestionRequest,

    user_id: str = Depends(
        get_current_user
    ),

):

    validate_session_id(
        session_id
    )

    # --------------------------------------------------------
    # Verify chat ownership
    # --------------------------------------------------------

    session = get_chat_session(

        session_id=session_id,

        user_id=user_id,

    )

    if not session:

        raise HTTPException(

            status_code=status.HTTP_404_NOT_FOUND,

            detail="Chat session not found",

        )

    question = request.question.strip()

    if not question:

        raise HTTPException(

            status_code=status.HTTP_400_BAD_REQUEST,

            detail="Question cannot be empty",

        )

    try:

        result = ask_chat_question(

            user_id=user_id,

            session_id=session_id,

            question=question,

        )

        return result

    except ValueError as error:

        raise HTTPException(

            status_code=status.HTTP_400_BAD_REQUEST,

            detail=str(error),

        )

    except Exception as error:

        print(
            "Chat question processing failed:"
        )

        print(error)

        raise HTTPException(

            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,

            detail="Unable to process chat question",

        )


# ============================================================
# DELETE CHAT
# ============================================================

@router.delete(
    "/{session_id}",
)
def delete_chat(

    session_id: str,

    user_id: str = Depends(
        get_current_user
    ),

):

    validate_session_id(
        session_id
    )

    deleted = delete_chat_session(

        session_id=session_id,

        user_id=user_id,

    )

    if not deleted:

        raise HTTPException(

            status_code=status.HTTP_404_NOT_FOUND,

            detail="Chat session not found",

        )

    return {

        "message": (
            "Chat session deleted successfully"
        ),

        "session_id": session_id,

    }