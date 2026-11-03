# ============================================================
# IMPORTS
# ============================================================

from datetime import datetime, timezone

from bson import ObjectId

from app.core.database import db
from app.services.chunk_service import (
    chunk_pages,
    save_chunks,
)
from app.services.document_service import (
    update_document_status,
)
from app.services.file_extraction_service import (
    extract_text_from_file,
)


# ============================================================
# BACKGROUND DOCUMENT PROCESSING
# ============================================================
#
# The upload endpoint saves the file, creates the document
# with status "processing", and returns immediately.
#
# This function then runs as a FastAPI background task:
#
#     extract text (OCR when needed)
#         ↓
#     chunk
#         ↓
#     embed and save chunks
#         ↓
#     status "completed" (or "failed" with a reason)
#
# The frontend polls the document until it leaves the
# "processing" state, so large or scanned files no longer
# risk an HTTP timeout.

def process_document(
    document_id: str,
    user_id: str,
    storage_path: str,
    storage_filename: str,
    extension: str,
    original_filename: str,
):
    """
    Extract, chunk, and embed an uploaded document.

    Never raises: any failure is recorded on the document
    as status "failed" with a processing error.
    """

    try:

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

    except Exception as error:

        print(
            "Document processing failed:"
        )

        print(error)

        update_document_status(

            document_id=document_id,

            user_id=user_id,

            status="failed",

            processing_error=(
                "Processing failed. Please try "
                "uploading the file again."
            ),

        )


# ============================================================
# RECOVER INTERRUPTED PROCESSING
# ============================================================

def recover_interrupted_documents(
    started_at: datetime | None = None
):
    """
    Mark documents left in "processing" by a previous
    server process as failed.

    Background tasks live inside the server process, so a
    restart (for example a free-plan host going to sleep)
    stops them. This runs once at start-up.

    DocuMind AI runs as a single server process, so any
    document created before this process started can no
    longer be processing.
    """

    if started_at is None:
        started_at = datetime.now(
            timezone.utc
        )

    result = db.documents.update_many(
        {
            "status":
                "processing",
            "created_at": {
                "$lt":
                    started_at
            }
        },
        {
            "$set": {
                "status":
                    "failed",
                "processing_error": (
                    "Processing was interrupted because "
                    "the server restarted. Please upload "
                    "the file again."
                )
            }
        }
    )

    return result.modified_count
