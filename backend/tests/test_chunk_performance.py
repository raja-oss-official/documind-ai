import time

from app.services.chunk_service import (
    chunk_text,
)


def test_large_document_chunking_performance():

    # Simulate approximately a large document.
    large_text = (
        "DocuMind AI is an AI-powered "
        "document knowledge assistant. "
        "It extracts information from documents, "
        "creates searchable chunks, generates "
        "embeddings, and helps users ask questions. "
    ) * 20000

    start_time = time.perf_counter()

    chunks = chunk_text(
        large_text
    )

    elapsed_time = (
        time.perf_counter() - start_time
    )

    assert chunks

    assert len(chunks) > 1

    print(
        f"\nDocument size: "
        f"{len(large_text):,} characters"
    )

    print(
        f"Chunks created: "
        f"{len(chunks):,}"
    )

    print(
        f"Chunking time: "
        f"{elapsed_time:.4f} seconds"
    )

    # Chunking should complete within a
    # reasonable local-development time.
    assert elapsed_time < 5.0


def test_medium_document_chunking_performance():

    medium_text = (
        "DocuMind AI processes documents "
        "using extraction and chunking. "
    ) * 5000

    start_time = time.perf_counter()

    chunks = chunk_text(
        medium_text
    )

    elapsed_time = (
        time.perf_counter() - start_time
    )

    assert chunks

    print(
        f"\nMedium document size: "
        f"{len(medium_text):,} characters"
    )

    print(
        f"Chunks created: "
        f"{len(chunks):,}"
    )

    print(
        f"Chunking time: "
        f"{elapsed_time:.4f} seconds"
    )

    assert elapsed_time < 2.0