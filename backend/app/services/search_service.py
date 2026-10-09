import math
import re

from app.core.database import db
from app.services.embedding_service import create_embedding
from app.services.vector_search_service import (
    is_vector_search_enabled,
    search_with_vector_database,
)


MIN_SEMANTIC_SCORE = 0.40
DEFAULT_RESULT_LIMIT = 5
MAX_RESULT_LIMIT = 10

SEMANTIC_WEIGHT = 0.75
KEYWORD_WEIGHT = 0.25

NEIGHBOR_TRIGGER_SCORE = 0.60
MIN_NEIGHBOR_SEMANTIC_SCORE = 0.35
MAX_NEIGHBOR_BOOST = 0.08


STOP_WORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "by",
    "for",
    "from",
    "how",
    "in",
    "is",
    "it",
    "of",
    "on",
    "or",
    "that",
    "the",
    "their",
    "them",
    "these",
    "this",
    "to",
    "was",
    "what",
    "when",
    "where",
    "which",
    "who",
    "why",
    "with",
}


# ============================================================
# BASIC VECTOR OPERATIONS
# ============================================================

def cosine_similarity(
    vector_a: list[float],
    vector_b: list[float],
) -> float:
    if not vector_a or not vector_b:
        return 0.0

    if len(vector_a) != len(vector_b):
        return 0.0

    dot_product = sum(
        a * b
        for a, b in zip(vector_a, vector_b)
    )

    magnitude_a = math.sqrt(
        sum(a * a for a in vector_a)
    )

    magnitude_b = math.sqrt(
        sum(b * b for b in vector_b)
    )

    if magnitude_a == 0 or magnitude_b == 0:
        return 0.0

    return dot_product / (
        magnitude_a * magnitude_b
    )


# ============================================================
# KEYWORD SEARCH
# ============================================================

def tokenize_text(
    text: str,
) -> set[str]:
    if not isinstance(text, str):
        return set()

    words = re.findall(
        r"\b[a-zA-Z0-9]+\b",
        text.lower(),
    )

    return {
        word
        for word in words
        if word not in STOP_WORDS
        and len(word) > 1
    }


def calculate_keyword_score(
    query: str,
    text: str,
) -> float:
    query_words = tokenize_text(query)
    text_words = tokenize_text(text)

    if not query_words:
        return 0.0

    matched_words = query_words & text_words

    return (
        len(matched_words)
        / len(query_words)
    )


# ============================================================
# HYBRID SEARCH SCORE
# ============================================================

def calculate_hybrid_score(
    semantic_score: float,
    keyword_score: float,
) -> float:
    return (
        semantic_score * SEMANTIC_WEIGHT
        + keyword_score * KEYWORD_WEIGHT
    )


# ============================================================
# SEARCH RESULT FORMATTER
# ============================================================

def build_search_result(
    chunk: dict,
    semantic_score: float,
    keyword_score: float,
    hybrid_score: float,
    contextual_boost: float = 0.0,
):
    text = chunk.get(
        "text",
        "",
    )

    final_score = min(
        hybrid_score + contextual_boost,
        1.0,
    )

    return {
        "chunk_id": str(
            chunk["_id"]
        ),
        "document_id": chunk.get(
            "document_id"
        ),
        "chunk_index": chunk.get(
            "chunk_index",
            0,
        ),
        "page_number": chunk.get(
            "page_number"
        ),
        "text": text,
        "character_count": chunk.get(
            "character_count",
            len(text),
        ),
        "word_count": chunk.get(
            "word_count",
            len(text.split()),
        ),
        "score": final_score,
        "semantic_score": semantic_score,
        "keyword_score": keyword_score,
        "contextual_boost": contextual_boost,
    }


# ============================================================
# NEIGHBOR CHUNKS
# ============================================================

def find_neighbor_chunks(
    user_id: str,
    document_id: str,
    chunk_indexes: list[int],
):
    if not chunk_indexes:
        return []

    neighbor_indexes = set()

    for chunk_index in chunk_indexes:
        if chunk_index > 0:
            neighbor_indexes.add(
                chunk_index - 1
            )

        neighbor_indexes.add(
            chunk_index + 1
        )

    if not neighbor_indexes:
        return []

    search_filter = {
        "user_id": user_id,
        "document_id": document_id,
        "chunk_index": {
            "$in": list(neighbor_indexes)
        },
        "embedding": {
            "$exists": True
        },
    }

    return list(
        db.document_chunks.find(
            search_filter
        )
    )


def add_contextual_neighbors(
    user_id: str,
    document_id: str,
    query: str,
    query_embedding: list[float],
    results: list[dict],
):
    if not document_id:
        return results

    strong_results = [
        result
        for result in results
        if result["score"]
        >= NEIGHBOR_TRIGGER_SCORE
    ]

    if not strong_results:
        return results

    source_indexes = [
        result["chunk_index"]
        for result in strong_results
    ]

    neighbor_chunks = find_neighbor_chunks(
        user_id=user_id,
        document_id=document_id,
        chunk_indexes=source_indexes,
    )

    if not neighbor_chunks:
        return results

    existing_ids = {
        result["chunk_id"]
        for result in results
    }

    added_neighbor_ids = set()
    neighbor_results = []

    for chunk in neighbor_chunks:
        chunk_id = str(
            chunk["_id"]
        )

        if chunk_id in existing_ids:
            continue

        if chunk_id in added_neighbor_ids:
            continue

        embedding = chunk.get(
            "embedding"
        )

        if not embedding:
            continue

        semantic_score = cosine_similarity(
            query_embedding,
            embedding,
        )

        if (
            semantic_score
            < MIN_NEIGHBOR_SEMANTIC_SCORE
        ):
            continue

        text = chunk.get(
            "text",
            "",
        )

        keyword_score = calculate_keyword_score(
            query,
            text,
        )

        hybrid_score = calculate_hybrid_score(
            semantic_score,
            keyword_score,
        )

        contextual_boost = min(
            MAX_NEIGHBOR_BOOST,
            0.04 + semantic_score * 0.04,
        )

        neighbor_result = build_search_result(
            chunk=chunk,
            semantic_score=semantic_score,
            keyword_score=keyword_score,
            hybrid_score=hybrid_score,
            contextual_boost=contextual_boost,
        )

        neighbor_results.append(
            neighbor_result
        )

        added_neighbor_ids.add(
            chunk_id
        )

    results.extend(
        neighbor_results
    )

    return results


# ============================================================
# LOCAL PYTHON VECTOR SEARCH
# ============================================================

def search_with_local_similarity(
    user_id: str,
    query: str,
    query_embedding: list[float],
    limit: int,
    document_id: str | None = None,
):
    search_filter = {
        "user_id": user_id,
        "embedding": {
            "$exists": True
        },
    }

    if document_id:
        search_filter[
            "document_id"
        ] = document_id

    chunks = list(
        db.document_chunks.find(
            search_filter
        )
    )

    if not chunks:
        return []

    results = []

    for chunk in chunks:
        embedding = chunk.get(
            "embedding"
        )

        if not embedding:
            continue

        text = chunk.get(
            "text",
            "",
        )

        semantic_score = cosine_similarity(
            query_embedding,
            embedding,
        )

        keyword_score = calculate_keyword_score(
            query,
            text,
        )

        if (
            semantic_score < MIN_SEMANTIC_SCORE
            and keyword_score <= 0.0
        ):
            continue

        hybrid_score = calculate_hybrid_score(
            semantic_score,
            keyword_score,
        )

        results.append(
            build_search_result(
                chunk=chunk,
                semantic_score=semantic_score,
                keyword_score=keyword_score,
                hybrid_score=hybrid_score,
            )
        )

    if not results:
        return []

    results.sort(
        key=lambda item: item["score"],
        reverse=True,
    )

    return results[:limit]


# ============================================================
# VECTOR SEARCH PROVIDER
# ============================================================

def search_with_vector_provider(
    user_id: str,
    query: str,
    query_embedding: list[float],
    limit: int,
    document_id: str | None = None,
):
    if not is_vector_search_enabled():
        return None

    return search_with_vector_database(
        user_id=user_id,
        query_embedding=query_embedding,
        limit=limit,
        document_id=document_id,
    )


# ============================================================
# MAIN SEARCH FUNCTION
# ============================================================

def search_similar_chunks(
    user_id: str,
    query: str,
    limit: int = DEFAULT_RESULT_LIMIT,
    document_id: str | None = None,
):
    if not isinstance(query, str):
        return []

    query = query.strip()

    if not query:
        return []

    if not user_id:
        return []

    if limit <= 0:
        limit = DEFAULT_RESULT_LIMIT

    if limit > MAX_RESULT_LIMIT:
        limit = MAX_RESULT_LIMIT

    query_embedding = create_embedding(
        query
    )

    if not query_embedding:
        return []

    # --------------------------------------------------------
    # PRODUCTION VECTOR SEARCH
    # --------------------------------------------------------

    vector_results = search_with_vector_provider(
        user_id=user_id,
        query=query,
        query_embedding=query_embedding,
        limit=limit,
        document_id=document_id,
    )

    if vector_results is not None:
        results = vector_results

    # --------------------------------------------------------
    # LOCAL FALLBACK
    # --------------------------------------------------------

    else:
        results = search_with_local_similarity(
            user_id=user_id,
            query=query,
            query_embedding=query_embedding,
            limit=limit,
            document_id=document_id,
        )

    if not results:
        return []

    # --------------------------------------------------------
    # CONTEXTUAL NEIGHBORS
    # --------------------------------------------------------

    if document_id:
        results = add_contextual_neighbors(
            user_id=user_id,
            document_id=document_id,
            query=query,
            query_embedding=query_embedding,
            results=results,
        )

    # --------------------------------------------------------
    # REMOVE DUPLICATES
    # --------------------------------------------------------

    unique_results = []
    seen_chunks = set()

    for result in results:
        chunk_id = result[
            "chunk_id"
        ]

        if chunk_id in seen_chunks:
            continue

        seen_chunks.add(
            chunk_id
        )

        unique_results.append(
            result
        )

    # --------------------------------------------------------
    # FINAL RANKING
    # --------------------------------------------------------

    unique_results.sort(
        key=lambda item: item["score"],
        reverse=True,
    )

    return unique_results[:limit]


# ============================================================
# DOCUMENT SEARCH COMPATIBILITY WRAPPER
# ============================================================

def search_documents(
    user_id: str,
    query: str,
    document_id: str | None = None,
    limit: int = DEFAULT_RESULT_LIMIT,
):
    """
    Compatibility wrapper used by the document search route.

    Keeps the existing search architecture intact while
    providing the search_documents function expected by
    app/routes/documents.py.
    """

    if not user_id:
        raise ValueError(
            "User ID is required"
        )

    if not isinstance(query, str):
        raise ValueError(
            "Search query must be a string"
        )

    query = query.strip()

    if not query:
        raise ValueError(
            "Search query cannot be empty"
        )

    if limit <= 0:
        limit = DEFAULT_RESULT_LIMIT

    if limit > MAX_RESULT_LIMIT:
        limit = MAX_RESULT_LIMIT

    return search_similar_chunks(
        user_id=user_id,
        query=query,
        limit=limit,
        document_id=document_id,
    )