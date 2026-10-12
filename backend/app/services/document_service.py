# ============================================================
# IMPORTS
# ============================================================

from datetime import datetime, timezone

from bson import ObjectId

from app.core.database import db


# ============================================================
# OBJECT ID VALIDATION
# ============================================================

def is_valid_object_id(
    value: str
):
    """
    Check whether a string is a valid MongoDB ObjectId.
    """

    try:

        ObjectId(value)

        return True

    except Exception:

        return False


# ============================================================
# CREATE DOCUMENT
# ============================================================

def create_document(
    user_id: str,
    filename: str,
    file_type: str,
    file_size: int,
    extracted_text: str = "",
    status: str = "uploaded",
    storage_filename: str | None = None
):
    """
    Create a new document record.

    This helper is kept consistent with the current
    document structure used by the upload route.
    """

    created_at = datetime.now(
        timezone.utc
    )

    document = {

        "user_id":
            user_id,

        # User-visible filename
        "filename":
            filename,

        # Physical storage filename
        "storage_filename":
            storage_filename,

        "file_type":
            file_type,

        "file_size":
            file_size,

        "status":
            status,

        "extracted_text":
            extracted_text,

        "created_at":
            created_at,

        # ----------------------------------------------------
        # Document statistics
        # ----------------------------------------------------

        "page_count":
            0,

        "chunk_count":
            0,

        "character_count":
            0,

        "word_count":
            0,

        # ----------------------------------------------------
        # Processing information
        # ----------------------------------------------------

        "processing_type":
            None,

        "processing_error":
            None,

        # ----------------------------------------------------
        # Document intelligence
        # ----------------------------------------------------

        "summary":
            None,

        "key_points":
            [],

        "summary_generated_at":
            None,

        "summary_method":
            None
    }

    result = db.documents.insert_one(
        document
    )

    return {

        "id":
            str(
                result.inserted_id
            ),

        "user_id":
            user_id,

        "filename":
            filename,

        "storage_filename":
            storage_filename,

        "file_type":
            file_type,

        "file_size":
            file_size,

        "status":
            status,

        "created_at":
            created_at,

        "page_count":
            0,

        "chunk_count":
            0,

        "character_count":
            0,

        "word_count":
            0,

        "processing_type":
            None,

        "processing_error":
            None,

        "summary":
            None,

        "key_points":
            [],

        "summary_generated_at":
            None,

        "summary_method":
            None
    }


# ============================================================
# UPDATE DOCUMENT STATUS
# ============================================================

def update_document_status(
    document_id: str,
    user_id: str,
    status: str,
    processing_error: str | None = None
):
    """
    Update the processing status of a document.

    Only the authenticated user's document can be updated.

    Returns True when the document exists and belongs
    to the authenticated user.
    """

    # --------------------------------------------------------
    # Validate ObjectId
    # --------------------------------------------------------

    if not is_valid_object_id(
        document_id
    ):

        return False

    # --------------------------------------------------------
    # Prepare update
    # --------------------------------------------------------

    update_data = {

        "status":
            status
    }

    # --------------------------------------------------------
    # Store processing error
    # --------------------------------------------------------

    if processing_error is not None:

        update_data[
            "processing_error"
        ] = processing_error

    # --------------------------------------------------------
    # Clear old error when processing starts
    # --------------------------------------------------------

    elif status == "processing":

        update_data[
            "processing_error"
        ] = None

    # --------------------------------------------------------
    # Update document
    # --------------------------------------------------------

    result = db.documents.update_one(

        {
            "_id":
                ObjectId(
                    document_id
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
# UPDATE DOCUMENT SUMMARY
# ============================================================

def update_document_summary(
    document_id: str,
    user_id: str,
    summary: str,
    key_points: list[str],
    summary_method: str = "direct"
):
    """
    Store AI-generated document summary,
    key points and summary metadata.

    Returns True when the document exists and
    belongs to the authenticated user.
    """

    # --------------------------------------------------------
    # Validate ObjectId
    # --------------------------------------------------------

    if not is_valid_object_id(
        document_id
    ):

        return False

    # --------------------------------------------------------
    # Update summary
    # --------------------------------------------------------

    result = db.documents.update_one(

        {
            "_id":
                ObjectId(
                    document_id
                ),

            "user_id":
                user_id
        },

        {
            "$set": {

                "summary":
                    summary,

                "key_points":
                    key_points,

                "summary_generated_at":
                    datetime.now(
                        timezone.utc
                    ),

                "summary_method":
                    summary_method
            }
        }
    )

    # --------------------------------------------------------
    # matched_count is intentional.
    #
    # modified_count can be 0 when the new data is
    # identical to the existing data even though the
    # document was successfully found.
    # --------------------------------------------------------

    return result.matched_count > 0


# ============================================================
# GET USER DOCUMENT
# ============================================================

def get_user_document(
    document_id: str,
    user_id: str
):
    """
    Return a document only if it belongs
    to the authenticated user.

    Returns None when:
    - the ObjectId is invalid
    - the document does not exist
    - the document belongs to another user
    """

    if not is_valid_object_id(
        document_id
    ):

        return None

    document = db.documents.find_one(

        {
            "_id":
                ObjectId(
                    document_id
                ),

            "user_id":
                user_id
        }
    )

    return document