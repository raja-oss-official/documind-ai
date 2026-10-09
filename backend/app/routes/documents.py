import os
import re
from pathlib import Path

from bson import ObjectId

from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    UploadFile,
    status,
)
from fastapi.security import HTTPAuthorizationCredentials

from app.core.database import db
from app.core.security import (
    security,
    verify_access_token,
)

from app.schemas.chat import ChatQuestionRequest
from app.schemas.document import (
    DocumentRenameRequest,
)

from app.services.chat_rag_service import (
    ask_document_question,
)

from app.services.chunk_service import (
    chunk_pages,
    save_chunks,
)

from app.services.document_intelligence_service import (
    generate_document_summary,
)

from app.services.document_service import (
    create_document,
    get_user_document,
    is_valid_object_id,
    update_document_status,
    update_document_summary,
)

from app.services.file_extraction_service import (
    extract_text_from_file,
)

from app.services.search_service import (
    search_documents,
)


router = APIRouter()


# ============================================================
# UPLOAD CONFIGURATION
# ============================================================

UPLOAD_DIR = "uploads"

MAX_FILE_SIZE = 10 * 1024 * 1024


# ============================================================
# SUPPORTED FILE TYPES
# ============================================================

SUPPORTED_EXTENSIONS = {

    ".pdf": {
        "file_type": "application/pdf",
    },

    ".docx": {
        "file_type": (
            "application/vnd.openxmlformats-officedocument."
            "wordprocessingml.document"
        ),
    },

    ".txt": {
        "file_type": "text/plain",
    },

    ".csv": {
        "file_type": "text/csv",
    },

    ".xlsx": {
        "file_type": (
            "application/vnd.openxmlformats-officedocument."
            "spreadsheetml.sheet"
        ),
    },

    ".pptx": {
        "file_type": (
            "application/vnd.openxmlformats-officedocument."
            "presentationml.presentation"
        ),
    },

    ".png": {
        "file_type": "image/png",
    },

    ".jpg": {
        "file_type": "image/jpeg",
    },

    ".jpeg": {
        "file_type": "image/jpeg",
    },

}


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
# FILENAME SANITIZATION
# ============================================================

def sanitize_filename(
    filename: str,
) -> str:

    """
    Remove unsafe characters from a filename.
    """

    filename = os.path.basename(
        filename
    )

    filename = re.sub(
        r"[^a-zA-Z0-9.\_-]",
        "_",
        filename,
    )

    filename = filename.strip(".")

    if not filename:

        filename = "uploaded_file"

    return filename


# ============================================================
# FILE SIGNATURE VALIDATION
# ============================================================

def validate_file_signature(
    extension: str,
    file_content: bytes,
):

    """
    Validate basic file signatures.

    PDF:
        %PDF-

    DOCX/XLSX/PPTX:
        ZIP container beginning with PK

    JPG/JPEG:
        FF D8 FF

    PNG:
        89 50 4E 47 0D 0A 1A 0A

    TXT/CSV:
        No fixed binary signature.
    """

    # --------------------------------------------------------
    # PDF
    # --------------------------------------------------------

    if extension == ".pdf":

        if not file_content.startswith(
            b"%PDF-"
        ):

            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid PDF file",
            )

    # --------------------------------------------------------
    # DOCX / XLSX / PPTX
    # --------------------------------------------------------

    elif extension in {
        ".docx",
        ".xlsx",
        ".pptx",
    }:

        if not file_content.startswith(
            b"PK"
        ):

            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Invalid "
                    f"{extension.upper().replace('.', '')} "
                    f"file"
                ),
            )

    # --------------------------------------------------------
    # JPG / JPEG
    # --------------------------------------------------------

    elif extension in {
        ".jpg",
        ".jpeg",
    }:

        if not file_content.startswith(
            b"\xff\xd8\xff"
        ):

            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid JPEG image file",
            )

    # --------------------------------------------------------
    # PNG
    # --------------------------------------------------------

    elif extension == ".png":

        if not file_content.startswith(
            b"\x89PNG\r\n\x1a\n"
        ):

            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid PNG image file",
            )


# ============================================================
# SEARCH DOCUMENTS
# ============================================================

@router.get("/search")
def search_user_documents(

    query: str,

    credentials: HTTPAuthorizationCredentials = Depends(
        security
    ),

):

    user_id = get_current_user(
        credentials
    )

    # --------------------------------------------------------
    # Normalize Search Query
    # --------------------------------------------------------

    query = query.strip()

    # --------------------------------------------------------
    # Validate Search Query
    # --------------------------------------------------------

    if not query:

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Search query cannot be empty",
        )

    if len(query) > 500:

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Search query cannot exceed "
                "500 characters"
            ),
        )

    # --------------------------------------------------------
    # Perform User-Scoped Search
    # --------------------------------------------------------

    return search_documents(
        user_id=user_id,
        query=query,
    )


# ============================================================
# UPLOAD DOCUMENT
# ============================================================

@router.post("/upload")
async def upload_document(

    file: UploadFile = File(...),

    credentials: HTTPAuthorizationCredentials = Depends(
        security
    ),

):

    user_id = get_current_user(
        credentials
    )

    # --------------------------------------------------------
    # Validate filename
    # --------------------------------------------------------

    if not file.filename:

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Filename is required",
        )

    original_filename = sanitize_filename(
        file.filename
    )

    # --------------------------------------------------------
    # Validate sanitized filename
    # --------------------------------------------------------

    if not original_filename:

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid filename",
        )

    extension = Path(
        original_filename
    ).suffix.lower()

    # --------------------------------------------------------
    # Validate extension
    # --------------------------------------------------------

    if extension not in SUPPORTED_EXTENSIONS:

        supported = ", ".join(
            sorted(
                SUPPORTED_EXTENSIONS.keys()
            )
        )

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Unsupported file type. "
                f"Supported types: {supported}"
            ),
        )

    # --------------------------------------------------------
    # Read uploaded file
    # --------------------------------------------------------

    file_content = await file.read()

    if not file_content:

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file is empty",
        )

    # --------------------------------------------------------
    # Validate file size
    # --------------------------------------------------------

    if len(file_content) > MAX_FILE_SIZE:

        raise HTTPException(
            status_code=(
                status.HTTP_413_REQUEST_ENTITY_TOO_LARGE
            ),
            detail="File size exceeds the 10 MB limit",
        )

    # --------------------------------------------------------
    # Validate file signature
    # --------------------------------------------------------

    validate_file_signature(
        extension=extension,
        file_content=file_content,
    )

    # --------------------------------------------------------
    # Create upload directory
    # --------------------------------------------------------

    os.makedirs(
        UPLOAD_DIR,
        exist_ok=True,
    )

    # --------------------------------------------------------
    # Determine MIME type
    # --------------------------------------------------------

    file_type = SUPPORTED_EXTENSIONS[
        extension
    ]["file_type"]

    # --------------------------------------------------------
    # Create database document
    # --------------------------------------------------------

    document = create_document(

        user_id=user_id,

        filename=original_filename,

        file_type=file_type,

        file_size=len(file_content),

        extracted_text="",

        status="processing",

        storage_filename=None,

    )

    document_id = document["id"]

    # --------------------------------------------------------
    # Create physical storage filename
    # --------------------------------------------------------

    storage_filename = (
        f"{document_id}{extension}"
    )

    storage_path = os.path.join(
        UPLOAD_DIR,
        storage_filename,
    )

    # --------------------------------------------------------
    # Update database with storage filename
    # --------------------------------------------------------

    db.documents.update_one(

        {
            "_id": ObjectId(document_id),
            "user_id": user_id,
        },

        {
            "$set": {
                "storage_filename": storage_filename,
            }
        },

    )

    try:

        # ----------------------------------------------------
        # Save physical file
        # ----------------------------------------------------

        with open(
            storage_path,
            "wb",
        ) as saved_file:

            saved_file.write(
                file_content
            )

        # ----------------------------------------------------
        # Extract text
        # ----------------------------------------------------

        extraction_result = (
            extract_text_from_file(
                storage_path,
                extension,
            )
        )

        extracted_text = (
            extraction_result.get(
                "text",
                "",
            )
        )

        pages = extraction_result.get(
            "pages",
            [],
        )

        page_count = extraction_result.get(
            "page_count",
            0,
        )

        is_scanned = extraction_result.get(
            "is_scanned",
            False,
        )

        # ----------------------------------------------------
        # Determine processing type
        # ----------------------------------------------------

        if extension == ".pdf":

            if is_scanned:

                processing_type = "ocr_pdf"

            else:

                processing_type = "text_pdf"

        elif extension == ".docx":

            processing_type = "docx"

        elif extension == ".txt":

            processing_type = "txt"

        elif extension == ".csv":

            processing_type = "csv"

        elif extension == ".xlsx":

            processing_type = "xlsx"

        elif extension == ".pptx":

            processing_type = "pptx"

        elif extension in {
            ".png",
            ".jpg",
            ".jpeg",
        }:

            processing_type = "image_ocr"

        else:

            processing_type = extension.replace(
                ".",
                "",
            )

        # ----------------------------------------------------
        # Make sure text was extracted
        # ----------------------------------------------------

        if not extracted_text.strip():

            update_document_status(

                document_id=document_id,

                user_id=user_id,

                status="failed",

                processing_error=(
                    "No readable text was found "
                    "in the uploaded file"
                ),

            )

            return {

                "id": document_id,

                "filename": original_filename,

                "status": "failed",

                "message": (
                    "No readable text was found "
                    "in the uploaded file"
                ),

            }

        # ----------------------------------------------------
        # Create chunks
        # ----------------------------------------------------

        chunks = chunk_pages(
            pages
        )

        # ----------------------------------------------------
        # Save chunks and embeddings
        # ----------------------------------------------------

        saved_chunk_count = save_chunks(

            document_id=document_id,

            user_id=user_id,

            chunks=chunks,

        )

        # ----------------------------------------------------
        # Calculate statistics
        # ----------------------------------------------------

        character_count = len(
            extracted_text
        )

        word_count = len(
            extracted_text.split()
        )

        # ----------------------------------------------------
        # Update document
        # ----------------------------------------------------

        db.documents.update_one(

            {
                "_id": ObjectId(document_id),
                "user_id": user_id,
            },

            {
                "$set": {

                    "extracted_text": extracted_text,

                    "page_count": page_count,

                    "chunk_count": saved_chunk_count,

                    "character_count": character_count,

                    "word_count": word_count,

                    "processing_type": processing_type,

                    "processing_error": None,

                    "status": "completed",

                    "storage_filename": storage_filename,

                }
            },

        )

        # ----------------------------------------------------
        # Return successful response
        # ----------------------------------------------------

        return {

            "id": document_id,

            "filename": original_filename,

            "file_type": file_type,

            "file_size": len(file_content),

            "status": "completed",

            "processing_type": processing_type,

            "page_count": page_count,

            "chunk_count": saved_chunk_count,

            "character_count": character_count,

            "word_count": word_count,

        }

    except Exception as error:

        print(
            "Document processing failed:"
        )

        print(error)

        update_document_status(

            document_id=document_id,

            user_id=user_id,

            status="failed",

            processing_error=str(error),

        )

        raise HTTPException(

            status_code=(
                status.HTTP_500_INTERNAL_SERVER_ERROR
            ),

            detail="Document processing failed",

        )


# ============================================================
# ASK QUESTION
# ============================================================

@router.post("/ask")
def ask_question_about_document(

    request: ChatQuestionRequest,

    credentials: HTTPAuthorizationCredentials = Depends(
        security
    ),

):

    user_id = get_current_user(
        credentials
    )

    question = request.question.strip()

    if not question:

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Question cannot be empty",
        )

    return ask_document_question(

        user_id=user_id,

        question=question,

    )


# ============================================================
# GENERATE SUMMARY
# ============================================================

@router.post("/{document_id}/summary")
def generate_summary(

    document_id: str,

    credentials: HTTPAuthorizationCredentials = Depends(
        security
    ),

):

    user_id = get_current_user(
        credentials
    )

    # --------------------------------------------------------
    # Validate document ID
    # --------------------------------------------------------

    if not is_valid_object_id(
        document_id
    ):

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid document ID",
        )

    # --------------------------------------------------------
    # Get user's document
    # --------------------------------------------------------

    document = get_user_document(

        document_id=document_id,

        user_id=user_id,

    )

    if not document:

        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )

    try:

        # ----------------------------------------------------
        # Generate summary using extracted document text
        # ----------------------------------------------------

        result = generate_document_summary(

            document_text=document.get(
                "extracted_text",
                "",
            )

        )

        # ----------------------------------------------------
        # Save summary to database
        # ----------------------------------------------------

        update_document_summary(

            document_id=document_id,

            user_id=user_id,

            summary=result["summary"],

            key_points=result.get(
                "key_points",
                [],
            ),

            summary_method=result.get(
                "method",
                "direct",
            ),

        )

        # ----------------------------------------------------
        # Return summary
        # ----------------------------------------------------

        return {

            "document_id": document_id,

            "summary": result["summary"],

            "key_points": result.get(
                "key_points",
                [],
            ),

            "method": result.get(
                "method",
                "direct",
            ),

        }

    except Exception as error:

        print(
            "Document summary failed:"
        )

        print(error)

        raise HTTPException(

            status_code=(
                status.HTTP_500_INTERNAL_SERVER_ERROR
            ),

            detail=(
                "Unable to generate "
                "document summary"
            ),

        )


# ============================================================
# LIST DOCUMENTS
# ============================================================

@router.get("")
def list_documents(

    credentials: HTTPAuthorizationCredentials = Depends(
        security
    ),

):

    user_id = get_current_user(
        credentials
    )

    documents = list(

        db.documents.find(
            {
                "user_id": user_id,
            }
        ).sort(
            "created_at",
            -1,
        )

    )

    results = []

    for document in documents:

        results.append(

            {

                "id": str(
                    document["_id"]
                ),

                "filename": document.get(
                    "filename"
                ),

                "storage_filename": document.get(
                    "storage_filename"
                ),

                "file_type": document.get(
                    "file_type"
                ),

                "file_size": document.get(
                    "file_size",
                    0,
                ),

                "status": document.get(
                    "status",
                    "uploaded",
                ),

                "created_at": document.get(
                    "created_at"
                ),

                "page_count": document.get(
                    "page_count",
                    0,
                ),

                "chunk_count": document.get(
                    "chunk_count",
                    0,
                ),

                "character_count": document.get(
                    "character_count",
                    0,
                ),

                "word_count": document.get(
                    "word_count",
                    0,
                ),

                "processing_type": document.get(
                    "processing_type"
                ),

                "processing_error": document.get(
                    "processing_error"
                ),

                "summary": document.get(
                    "summary"
                ),

                "key_points": document.get(
                    "key_points",
                    [],
                ),

                "summary_generated_at": document.get(
                    "summary_generated_at"
                ),

                "summary_method": document.get(
                    "summary_method"
                ),

            }

        )

    return results


# ============================================================
# GET SINGLE DOCUMENT
# ============================================================

@router.get("/{document_id}")
def get_document(

    document_id: str,

    credentials: HTTPAuthorizationCredentials = Depends(
        security
    ),

):

    user_id = get_current_user(
        credentials
    )

    # --------------------------------------------------------
    # Validate document ID
    # --------------------------------------------------------

    if not is_valid_object_id(
        document_id
    ):

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid document ID",
        )

    # --------------------------------------------------------
    # Get document
    # --------------------------------------------------------

    document = get_user_document(

        document_id=document_id,

        user_id=user_id,

    )

    if not document:

        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )

    return {

        "id": str(
            document["_id"]
        ),

        "filename": document.get(
            "filename"
        ),

        "storage_filename": document.get(
            "storage_filename"
        ),

        "file_type": document.get(
            "file_type"
        ),

        "file_size": document.get(
            "file_size",
            0,
        ),

        "status": document.get(
            "status"
        ),

        "created_at": document.get(
            "created_at"
        ),

        "page_count": document.get(
            "page_count",
            0,
        ),

        "chunk_count": document.get(
            "chunk_count",
            0,
        ),

        "character_count": document.get(
            "character_count",
            0,
        ),

        "word_count": document.get(
            "word_count",
            0,
        ),

        "processing_type": document.get(
            "processing_type"
        ),

        "processing_error": document.get(
            "processing_error"
        ),

        "summary": document.get(
            "summary"
        ),

        "key_points": document.get(
            "key_points",
            [],
        ),

        "summary_generated_at": document.get(
            "summary_generated_at"
        ),

        "summary_method": document.get(
            "summary_method"
        ),

    }


# ============================================================
# DELETE DOCUMENT
# ============================================================

@router.delete("/{document_id}")
def delete_document(

    document_id: str,

    credentials: HTTPAuthorizationCredentials = Depends(
        security
    ),

):

    user_id = get_current_user(
        credentials
    )

    # --------------------------------------------------------
    # Validate document ID
    # --------------------------------------------------------

    if not is_valid_object_id(
        document_id
    ):

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid document ID",
        )

    # --------------------------------------------------------
    # Get document
    # --------------------------------------------------------

    document = get_user_document(

        document_id=document_id,

        user_id=user_id,

    )

    if not document:

        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )

    # --------------------------------------------------------
    # Delete physical file
    # --------------------------------------------------------

    storage_filename = document.get(
        "storage_filename"
    )

    if storage_filename:

        storage_path = os.path.join(

            UPLOAD_DIR,

            storage_filename,

        )

        if os.path.exists(
            storage_path
        ):

            try:

                os.remove(
                    storage_path
                )

            except OSError as error:

                print(
                    "Unable to delete physical file:"
                )

                print(error)

    # --------------------------------------------------------
    # Delete document chunks
    # --------------------------------------------------------

    db.document_chunks.delete_many(

        {
            "document_id": document_id,
            "user_id": user_id,
        }

    )

    # --------------------------------------------------------
    # Delete document
    # --------------------------------------------------------

    db.documents.delete_one(

        {
            "_id": ObjectId(document_id),
            "user_id": user_id,
        }

    )

    return {

        "message": (
            "Document deleted successfully"
        ),

        "document_id": document_id,

    }


# ============================================================
# RENAME DOCUMENT
# ============================================================

@router.patch("/{document_id}/rename")
def rename_document(

    document_id: str,

    request: DocumentRenameRequest,

    credentials: HTTPAuthorizationCredentials = Depends(
        security
    ),

):

    user_id = get_current_user(
        credentials
    )

    # --------------------------------------------------------
    # Validate document ID
    # --------------------------------------------------------

    if not is_valid_object_id(
        document_id
    ):

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid document ID",
        )

    # --------------------------------------------------------
    # Get document
    # --------------------------------------------------------

    document = get_user_document(

        document_id=document_id,

        user_id=user_id,

    )

    if not document:

        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )

    # --------------------------------------------------------
    # Sanitize new filename
    # --------------------------------------------------------

    new_filename = sanitize_filename(
        request.filename
    )

    if not new_filename:

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Filename cannot be empty",
        )

    # --------------------------------------------------------
    # Preserve original extension
    # --------------------------------------------------------

    original_filename = document.get(
        "filename",
        "",
    )

    original_extension = Path(
        original_filename
    ).suffix.lower()

    new_extension = Path(
        new_filename
    ).suffix.lower()

    # If extension is not provided,
    # preserve the existing extension.

    if (
        not new_extension
        and original_extension
    ):

        new_filename = (
            new_filename
            + original_extension
        )

    # Prevent changing file type.

    elif (
        new_extension
        and original_extension
        and new_extension != original_extension
    ):

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Renaming cannot change "
                "the document file type"
            ),
        )

    # --------------------------------------------------------
    # Update filename
    # --------------------------------------------------------

    result = db.documents.update_one(

        {
            "_id": ObjectId(document_id),
            "user_id": user_id,
        },

        {
            "$set": {
                "filename": new_filename,
            }
        },

    )

    if result.matched_count == 0:

        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )

    return {

        "message": (
            "Document renamed successfully"
        ),

        "id": document_id,

        "filename": new_filename,

    }