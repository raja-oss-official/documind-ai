# ============================================================
# IMPORTS
# ============================================================

import os

from gridfs import GridFSBucket
from gridfs.errors import NoFile

from app.core.config import settings
from app.core.database import db


# ============================================================
# STORAGE
# ============================================================
#
# Uploaded files are written to the local uploads/ folder
# for processing (text extraction and OCR need a file path).
#
# A copy is also kept in MongoDB GridFS so the original can
# be previewed later, even on hosts whose disk is wiped on
# restart. Files are at most 10 MB, so GridFS is a good fit.

UPLOAD_DIR = "uploads"

bucket = GridFSBucket(
    db,
    bucket_name="document_files"
)


# ============================================================
# STORE ORIGINAL FILE
# ============================================================

def store_original_file(
    document_id: str,
    owner_id: str,
    filename: str,
    content_type: str,
    content: bytes
) -> bool:
    """
    Save the original upload in GridFS.

    Storage problems never fail the upload: the document is
    still processed, only the preview will be unavailable.
    """

    if not settings.store_original_files:
        return False

    try:

        delete_original_file(
            document_id
        )

        bucket.upload_from_stream(
            filename,
            content,
            metadata={
                "document_id":
                    document_id,
                "owner_id":
                    owner_id,
                "content_type":
                    content_type
            }
        )

        return True

    except Exception as error:

        print(
            "Unable to store original file:"
        )

        print(error)

        return False


# ============================================================
# READ ORIGINAL FILE
# ============================================================

def read_original_file(
    document: dict
):
    """
    Return the original file's bytes for a document, or
    None when it is no longer available.

    GridFS is checked first; files uploaded before GridFS
    storage existed are read from the local uploads/ folder
    if they are still there.
    """

    document_id = str(
        document["_id"]
    )

    # --------------------------------------------------------
    # GridFS copy
    # --------------------------------------------------------

    stored = db["document_files.files"].find_one(
        {
            "metadata.document_id":
                document_id
        },
        sort=[
            (
                "uploadDate",
                -1
            )
        ]
    )

    if stored:

        try:

            return bucket.open_download_stream(
                stored["_id"]
            ).read()

        except NoFile:
            pass

    # --------------------------------------------------------
    # Local file (older uploads)
    # --------------------------------------------------------

    storage_filename = document.get(
        "storage_filename"
    )

    if storage_filename:

        storage_path = os.path.join(
            UPLOAD_DIR,
            storage_filename
        )

        if os.path.exists(
            storage_path
        ):

            with open(
                storage_path,
                "rb"
            ) as saved_file:

                return saved_file.read()

    return None


# ============================================================
# DELETE ORIGINAL FILE
# ============================================================

def delete_original_file(
    document_id: str
):
    """
    Remove every GridFS copy of a document's original file.
    """

    stored_files = db["document_files.files"].find(
        {
            "metadata.document_id":
                document_id
        },
        {
            "_id":
                1
        }
    )

    for stored in stored_files:

        try:

            bucket.delete(
                stored["_id"]
            )

        except NoFile:
            pass
