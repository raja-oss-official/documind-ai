from app.services.chunk_service import (
    chunk_text,
)


def test_large_document_chunking():

    large_text = (
        "DocuMind AI is an AI-powered "
        "document knowledge assistant. "
        "It allows users to upload documents, "
        "search their contents, and ask questions. "
    ) * 10000

    chunks = chunk_text(
        large_text
    )

    assert chunks

    assert len(chunks) > 1

    for chunk in chunks:

        assert isinstance(
            chunk,
            str,
        )

        assert chunk.strip()

        assert len(chunk) <= 1200


def test_large_document_chunking_contains_original_content():

    large_text = (
        "DocuMind AI processes documents "
        "using extraction, chunking, "
        "embedding, and retrieval. "
    ) * 5000

    chunks = chunk_text(
        large_text
    )

    assert chunks

    combined_chunks = "\n".join(
        chunks
    )

    # Important phrases from the original
    # document must remain available in the
    # generated chunks.
    required_phrases = [
        "DocuMind AI processes documents",
        "using extraction, chunking",
        "embedding, and retrieval",
    ]

    for phrase in required_phrases:

        assert phrase in combined_chunks


def test_large_document_chunking_has_no_empty_chunks():

    large_text = (
        "DocuMind AI document processing "
        "supports extraction, chunking, "
        "embedding, and retrieval. "
    ) * 5000

    chunks = chunk_text(
        large_text
    )

    assert chunks

    for chunk in chunks:

        assert chunk.strip()


def test_empty_document_text():

    chunks = chunk_text(
        ""
    )

    assert chunks == []


def test_whitespace_only_document():

    chunks = chunk_text(
        "   \n\n   "
    )

    assert chunks == []


def test_small_document():

    text = (
        "This is a small document."
    )

    chunks = chunk_text(
        text
    )

    assert chunks

    assert "".join(chunks) == text