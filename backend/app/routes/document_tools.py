# ============================================================
# IMPORTS
# ============================================================

import re
from urllib.parse import quote

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Response,
    status,
)
from fastapi.security import HTTPAuthorizationCredentials

from app.core.security import (
    security,
    verify_access_token,
)
from app.schemas.document import (
    CompareRequest,
    StudyRequest,
)
from app.services.access_service import (
    get_accessible_document,
)
from app.services.document_tools_service import (
    compare_documents,
    extract_key_facts,
    generate_study_set,
)
from app.services.file_storage_service import (
    read_original_file,
)


# ============================================================
# ROUTER
# ============================================================
#
# Document tools: compare, quiz and flashcards, key facts,
# and the original-file preview. Every tool works on
# documents the user owns or that were shared with them.

router = APIRouter()


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
# GET A READY DOCUMENT
# ============================================================

def get_ready_document(
    document_id: str,
    user_id: str,
):

    """
    Return a processed document the user can read, or raise
    404 (no access) / 400 (still processing or failed).
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

    if document.get("status") != "completed":

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This document has not finished processing",
        )

    return document


# ============================================================
# COMPARE TWO DOCUMENTS
# ============================================================

@router.post("/compare")
def compare(
    request: CompareRequest,
    user_id: str = Depends(
        get_current_user
    ),
):

    documents = [
        get_ready_document(
            document_id=document_id,
            user_id=user_id,
        )
        for document_id in request.document_ids
    ]

    try:

        answer = compare_documents(
            user_id=user_id,
            documents=documents,
            focus=request.focus,
        )

    except ValueError as error:

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error),
        )

    except Exception as error:

        print(
            "Document comparison failed:"
        )

        print(error)

        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Unable to compare the documents right now",
        )

    return {

        "documents": [
            {
                "id": str(document["_id"]),
                "filename": document.get("filename"),
            }
            for document in documents
        ],

        "focus": request.focus,

        "answer": answer,

    }


# ============================================================
# QUIZ AND FLASHCARDS
# ============================================================

@router.post("/{document_id}/study")
def study(
    document_id: str,
    request: StudyRequest,
    user_id: str = Depends(
        get_current_user
    ),
):

    document = get_ready_document(
        document_id=document_id,
        user_id=user_id,
    )

    try:

        items = generate_study_set(
            user_id=user_id,
            document_id=document_id,
            study_type=request.type,
            count=request.count,
        )

    except ValueError as error:

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error),
        )

    except Exception as error:

        print(
            "Study set generation failed:"
        )

        print(error)

        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Unable to create study material right now",
        )

    return {

        "document_id": document_id,

        "filename": document.get("filename"),

        "type": request.type,

        "items": items,

    }


# ============================================================
# KEY FACTS
# ============================================================

@router.post("/{document_id}/facts")
def facts(
    document_id: str,
    user_id: str = Depends(
        get_current_user
    ),
):

    document = get_ready_document(
        document_id=document_id,
        user_id=user_id,
    )

    try:

        rows = extract_key_facts(
            user_id=user_id,
            document_id=document_id,
        )

    except ValueError as error:

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error),
        )

    except Exception as error:

        print(
            "Key fact extraction failed:"
        )

        print(error)

        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Unable to extract facts right now",
        )

    return {

        "document_id": document_id,

        "filename": document.get("filename"),

        "facts": rows,

    }


# ============================================================
# ORIGINAL FILE (PREVIEW)
# ============================================================

@router.get("/{document_id}/file")
def original_file(
    document_id: str,
    user_id: str = Depends(
        get_current_user
    ),
):

    """
    Return the original uploaded file for previewing.

    The browser fetches it with the access token and shows
    it from a local blob URL (PDFs open at a given page).
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

    content = read_original_file(
        document
    )

    if content is None:

        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                "The original file is no longer available. "
                "Upload it again to preview it."
            ),
        )

    # --------------------------------------------------------
    # Safe Content-Disposition filename
    # --------------------------------------------------------

    filename = document.get("filename") or "document"

    ascii_name = re.sub(
        r"[^A-Za-z0-9._-]",
        "_",
        filename,
    )

    return Response(

        content=content,

        media_type=document.get(
            "file_type",
            "application/octet-stream",
        ),

        headers={
            "Content-Disposition": (
                f'inline; filename="{ascii_name}"; '
                f"filename*=UTF-8''{quote(filename)}"
            ),
            "Cache-Control": "private, no-store",
        },

    )
