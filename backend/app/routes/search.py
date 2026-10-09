from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query
)

from app.core.security import (
    security,
    verify_access_token
)

from app.services.search_service import (
    search_similar_chunks
)


router = APIRouter()


# ============================================================
# SEARCH DOCUMENTS
# ============================================================

@router.get("/search")
async def search_documents(
    q: str = Query(
        ...,
        min_length=1,
        description="Search query"
    ),
    document_id: str | None = Query(
        None,
        description="Optional document ID"
    ),
    limit: int = Query(
        5,
        ge=1,
        le=20,
        description="Number of results"
    ),
    credentials=Depends(security)
):
    """
    Search document chunks using semantic similarity.

    The search is restricted to documents belonging
    to the authenticated user.
    """

    user_id = verify_access_token(
        credentials
    )

    query = q.strip()

    if not query:

        raise HTTPException(
            status_code=400,
            detail="Search query cannot be empty"
        )

    try:

        results = search_similar_chunks(
            user_id=user_id,
            query=query,
            limit=limit,
            document_id=document_id
        )

    except Exception as error:

        print(
            "Document search failed:"
        )

        print(error)

        raise HTTPException(
            status_code=500,
            detail="Unable to search documents"
        )

    return {
        "query": query,
        "document_id": document_id,
        "result_count": len(results),
        "results": results
    }