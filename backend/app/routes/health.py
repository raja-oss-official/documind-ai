# ============================================================
# IMPORTS
# ============================================================

from fastapi import APIRouter
from app.schemas.health import HealthResponse

# ============================================================
# ROUTER
# ============================================================

router = APIRouter()


# ============================================================
# HEALTH CHECK
# ============================================================

@router.get("/health", response_model=HealthResponse)
def health_check():
    return {
        "status": "healthy",
        "service": "DocuMind AI"
    }