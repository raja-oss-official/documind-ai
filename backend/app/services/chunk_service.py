# ============================================================
# IMPORTS
# ============================================================

import re

from app.core.database import db
from app.services.embedding_service import create_embedding


# ============================================================
# TEXT CHUNKING
# ============================================================

def chunk_text(
    text: str,
    chunk_size: int = 500,
    chunk_overlap: int = 50
):
    """
    Split text into sentence-aware chunks.

    The chunks use character-based overlap so that
    neighboring chunks retain some shared context.
    """

    if not text:
        return []

    # --------------------------------------------------------
    # Validate chunk settings
    # --------------------------------------------------------

    if chunk_size <= 0:
        raise ValueError(
            "chunk_size must be greater than 0"
        )

    if chunk_overlap < 0:
        raise ValueError(
            "chunk_overlap cannot be negative"
        )

    if chunk_overlap >= chunk_size:
        raise ValueError(
            "chunk_overlap must be smaller than chunk_size"
        )

    # --------------------------------------------------------
    # Normalize whitespace
    # --------------------------------------------------------

    text = re.sub(
        r"[ \t]+",
        " ",
        text
    )

    text = re.sub(
        r"\n{3,}",
        "\n\n",
        text
    )

    text = text.strip()

    if not text:
        return []

    # --------------------------------------------------------
    # Split into sentences
    # --------------------------------------------------------

    sentences = re.split(
        r"(?<=[.!?])\s+",
        text
    )

    sentences = [
        sentence.strip()
        for sentence in sentences
        if sentence.strip()
    ]

    # --------------------------------------------------------
    # Create chunks
    # --------------------------------------------------------

    chunks = []

    current_chunk = ""

    for sentence in sentences:

        # ----------------------------------------------------
        # Handle sentences larger than chunk size
        # ----------------------------------------------------

        if len(sentence) > chunk_size:

            if current_chunk:

                chunks.append(
                    current_chunk.strip()
                )

                current_chunk = ""

            start = 0

            while start < len(sentence):

                end = start + chunk_size

                piece = sentence[
                    start:end
                ].strip()

                if piece:

                    chunks.append(
                        piece
                    )

                start += (
                    chunk_size -
                    chunk_overlap
                )

            continue

        # ----------------------------------------------------
        # Build candidate chunk
        # ----------------------------------------------------

        if current_chunk:

            candidate = (
                current_chunk
                + " "
                + sentence
            )

        else:

            candidate = sentence

        # ----------------------------------------------------
        # Candidate fits
        # ----------------------------------------------------

        if len(candidate) <= chunk_size:

            current_chunk = candidate

            continue

        # ----------------------------------------------------
        # Candidate does not fit
        # ----------------------------------------------------

        if current_chunk:

            chunks.append(
                current_chunk.strip()
            )

        # ----------------------------------------------------
        # Create overlap
        # ----------------------------------------------------

        overlap_text = ""

        if current_chunk and chunk_overlap > 0:

            overlap_text = (
                current_chunk[
                    -chunk_overlap:
                ]
                .strip()
            )

        # ----------------------------------------------------
        # Start next chunk
        # ----------------------------------------------------

        if overlap_text:

            current_chunk = (
                overlap_text
                + " "
                + sentence
            )

        else:

            current_chunk = sentence

        # ----------------------------------------------------
        # Safety handling for unexpected long result
        # ----------------------------------------------------

        if len(current_chunk) > chunk_size:

            start = 0

            while start < len(current_chunk):

                end = start + chunk_size

                piece = current_chunk[
                    start:end
                ].strip()

                if piece:

                    chunks.append(
                        piece
                    )

                start += (
                    chunk_size -
                    chunk_overlap
                )

            current_chunk = ""

    # --------------------------------------------------------
    # Save final chunk
    # --------------------------------------------------------

    if current_chunk:

        chunks.append(
            current_chunk.strip()
        )

    # --------------------------------------------------------
    # Remove empty chunks
    # --------------------------------------------------------

    chunks = [
        chunk.strip()
        for chunk in chunks
        if chunk and chunk.strip()
    ]

    return chunks


# ============================================================
# PAGE-AWARE CHUNKING
# ============================================================

def chunk_pages(
    pages: list[dict],
    chunk_size: int = 500,
    chunk_overlap: int = 50
):
    """
    Split page-aware document text into chunks.

    Every chunk contains:

    - chunk_index
    - page_number
    - text

    Chunk indexes are generated here so that they remain
    sequential across the complete document.
    """

    if not pages:

        return []

    chunks = []

    chunk_index = 0

    for page in pages:

        if not isinstance(page, dict):

            continue

        page_number = page.get(
            "page_number"
        )

        page_text = page.get(
            "text",
            ""
        )

        if not page_text:

            continue

        page_chunks = chunk_text(
            page_text,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap
        )

        for chunk in page_chunks:

            if not chunk.strip():

                continue

            chunks.append({

                "chunk_index":
                    chunk_index,

                "page_number":
                    page_number,

                "text":
                    chunk.strip()
            })

            chunk_index += 1

    return chunks


# ============================================================
# SAVE CHUNKS + EMBEDDINGS
# ============================================================

def save_chunks(
    document_id: str,
    user_id: str,
    chunks: list
):
    """
    Create embeddings and save document chunks.

    The complete embedding batch is prepared before
    inserting anything into MongoDB.

    Returns the number of saved chunks.
    """

    if not document_id:

        raise ValueError(
            "document_id is required"
        )

    if not user_id:

        raise ValueError(
            "user_id is required"
        )

    if not chunks:

        return 0

    chunk_documents = []

    # --------------------------------------------------------
    # Build complete chunk batch
    # --------------------------------------------------------

    for index, chunk in enumerate(chunks):

        # ----------------------------------------------------
        # Page-aware chunk
        # ----------------------------------------------------

        if isinstance(chunk, dict):

            chunk_text_value = chunk.get(
                "text",
                ""
            )

            page_number = chunk.get(
                "page_number"
            )

        # ----------------------------------------------------
        # Backward compatibility
        # ----------------------------------------------------

        else:

            chunk_text_value = chunk

            page_number = None

        # ----------------------------------------------------
        # Validate text
        # ----------------------------------------------------

        if not isinstance(
            chunk_text_value,
            str
        ):

            continue

        chunk_text_value = (
            chunk_text_value.strip()
        )

        if not chunk_text_value:

            continue

        # ----------------------------------------------------
        # Calculate statistics
        # ----------------------------------------------------

        character_count = len(
            chunk_text_value
        )

        word_count = len(
            chunk_text_value.split()
        )

        # ----------------------------------------------------
        # Generate embedding
        # ----------------------------------------------------

        embedding = create_embedding(
            chunk_text_value
        )

        if not embedding:

            raise ValueError(
                "Embedding generation returned empty data"
            )

        # ----------------------------------------------------
        # Create MongoDB document
        # ----------------------------------------------------

        chunk_document = {

            "document_id":
                document_id,

            "user_id":
                user_id,

            # Always generate sequential indexes here
            "chunk_index":
                len(chunk_documents),

            "text":
                chunk_text_value,

            "character_count":
                character_count,

            "word_count":
                word_count,

            "embedding":
                embedding
        }

        # ----------------------------------------------------
        # Preserve page number
        # ----------------------------------------------------

        if page_number is not None:

            chunk_document[
                "page_number"
            ] = page_number

        chunk_documents.append(
            chunk_document
        )

    # --------------------------------------------------------
    # Nothing valid to save
    # --------------------------------------------------------

    if not chunk_documents:

        return 0

    # --------------------------------------------------------
    # Prevent accidental duplicate processing
    #
    # If chunks already exist for this document, do not
    # insert another complete set.
    # --------------------------------------------------------

    existing_count = db.document_chunks.count_documents({

        "document_id":
            document_id,

        "user_id":
            user_id
    })

    if existing_count > 0:

        raise ValueError(
            "Document chunks already exist"
        )

    # --------------------------------------------------------
    # Insert complete batch
    # --------------------------------------------------------

    db.document_chunks.insert_many(
        chunk_documents
    )

    return len(
        chunk_documents
    )


# ============================================================
# ADD EMBEDDINGS TO OLD CHUNKS
# ============================================================

def add_embeddings_to_existing_chunks(
    user_id: str
):
    """
    Add embeddings to existing chunks that do not
    already contain embeddings.

    Only chunks belonging to the authenticated user
    are processed.
    """

    if not user_id:

        raise ValueError(
            "user_id is required"
        )

    chunks = db.document_chunks.find({

        "user_id":
            user_id,

        "$or": [

            {
                "embedding":
                    {
                        "$exists":
                            False
                    }
            },

            {
                "embedding":
                    None
            },

            {
                "embedding":
                    []
            }
        ]
    })

    updated_count = 0

    for chunk in chunks:

        text = chunk.get(
            "text",
            ""
        )

        if not isinstance(
            text,
            str
        ):

            continue

        text = text.strip()

        if not text:

            continue

        # ----------------------------------------------------
        # Generate embedding
        # ----------------------------------------------------

        embedding = create_embedding(
            text
        )

        if not embedding:

            continue

        # ----------------------------------------------------
        # Update only this exact chunk
        # ----------------------------------------------------

        result = db.document_chunks.update_one(

            {
                "_id":
                    chunk["_id"],

                "user_id":
                    user_id
            },

            {
                "$set": {

                    "embedding":
                        embedding
                }
            }
        )

        if result.matched_count > 0:

            updated_count += 1

    return updated_count