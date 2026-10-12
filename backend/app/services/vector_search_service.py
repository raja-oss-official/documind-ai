# ============================================================
# IMPORTS
# ============================================================

from app.core.config import settings


# ============================================================
# VECTOR SEARCH ENABLED CHECK
# ============================================================

def is_vector_search_enabled() -> bool:
    """
    Check whether production vector search is enabled.

    Local development currently uses the existing
    Python cosine-similarity implementation.
    """

    return settings.vector_search_enabled


# ============================================================
# SEARCH WITH VECTOR DATABASE
# ============================================================

def search_with_vector_database(
    user_id: str,
    query_embedding: list[float],
    limit: int = 5,
    document_id: str | None = None
):
    """
    Production vector-search provider.

    This function is intentionally not connected to the
    local MongoDB instance yet.

    When DocuMind is deployed on a MongoDB environment
    with supported Vector Search functionality, this
    function will perform the actual $vectorSearch query.

    Keeping this provider separate prevents the current
    local search implementation from being affected.
    """

    if not user_id:
        return []

    if not query_embedding:
        return []

    if limit <= 0:
        limit = 5

    if not is_vector_search_enabled():
        return []

    raise RuntimeError(
        "Vector Search is enabled, but the production "
        "MongoDB Vector Search provider has not been "
        "configured yet."
    )


# ============================================================
# VECTOR SEARCH AVAILABILITY
# ============================================================

def vector_search_available() -> bool:
    """
    Return whether the Vector Search provider is currently
    enabled in configuration.
    """

    return is_vector_search_enabled()