# ============================================================
# IMPORTS
# ============================================================

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.routes.health import router as health_router
from app.routes.auth import router as auth_router
from app.routes.search import router as search_router
from app.routes.documents import router as documents_router
from app.routes.chats import router as chats_router
from app.routes.document_tools import router as document_tools_router
from app.routes.youtube import router as youtube_router
from app.routes.sharing import (
    chat_router as chat_sharing_router,
    document_router as document_sharing_router,
)

from app.core.config import settings
from app.core.rate_limiter import limiter
from app.core.security_headers import SecurityHeadersMiddleware
from app.core.error_handlers import unhandled_exception_handler
from app.services.document_processing_service import (
    recover_interrupted_documents,
)


# ============================================================
# API DOCUMENTATION TAGS
# ============================================================

openapi_tags = [
    {
        "name": "Health",
        "description": "Check the availability of DocuMind AI.",
    },
    {
        "name": "Authentication",
        "description": (
            "Register users, log in, refresh tokens, "
            "and access protected account endpoints."
        ),
    },
    {
        "name": "Documents",
        "description": (
            "Upload, list, and manage documents belonging "
            "to the authenticated user."
        ),
    },
    {
        "name": "Document Search",
        "description": (
            "Search document content using semantic similarity. "
            "Results are restricted to the authenticated user."
        ),
    },
    {
        "name": "Document Tools",
        "description": (
            "Compare documents, create quizzes and flashcards, "
            "extract key facts, and preview original files."
        ),
    },
    {
        "name": "Sharing",
        "description": (
            "Share documents (viewer or editor) and chats "
            "(read-only) with other users."
        ),
    },
    {
        "name": "YouTube",
        "description": (
            "Add public YouTube videos by link; Gemini watches "
            "them so you can chat about their content."
        ),
    },
    {
        "name": "Chats",
        "description": (
            "Create chat sessions, send messages, and retrieve "
            "conversation history."
        ),
    },
]


# ============================================================
# FASTAPI APPLICATION
# ============================================================

app = FastAPI(
    title="DocuMind AI API",
    summary="AI-powered document knowledge assistant",
    description="""
# DocuMind AI

Welcome to the DocuMind AI backend API.

## Features

- User registration and authentication
- Secure access and refresh tokens
- Document upload and management
- Semantic document search
- Chat sessions and conversation history
- User-specific document and chat access

## Authentication

Protected endpoints require a valid access token.

Use the Authorize button in Swagger UI to provide your bearer token
when prompted.

## API Version

Version: 1.0.0
""",
    version="1.0.0",
    openapi_tags=openapi_tags,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)


# ============================================================
# START-UP: RECOVER INTERRUPTED UPLOADS
# ============================================================

# Background processing stops when the server restarts;
# documents it left in "processing" are marked as failed.
recover_interrupted_documents()


# ============================================================
# EXCEPTION HANDLERS AND RATE LIMITING
# ============================================================

app.add_exception_handler(
    Exception,
    unhandled_exception_handler,
)


app.state.limiter = limiter

app.add_exception_handler(
    RateLimitExceeded,
    _rate_limit_exceeded_handler,
)


# ============================================================
# MIDDLEWARE (SECURITY HEADERS AND CORS)
# ============================================================

app.add_middleware(
    SecurityHeadersMiddleware,
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_origin_regex=settings.cors_origin_regex,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================
# HOME ENDPOINT
# ============================================================

@app.get(
    "/",
    tags=["Health"],
    summary="API welcome endpoint",
    description="Returns the API welcome message and running status.",
)
def home():
    return {
        "message": "Welcome to DocuMind AI",
        "status": "running",
    }


# ============================================================
# ROUTERS
# ============================================================

app.include_router(
    health_router,
    prefix="/api/v1",
    tags=["Health"],
)

app.include_router(
    auth_router,
    prefix="/api/v1/auth",
    tags=["Authentication"],
)

app.include_router(
    search_router,
    prefix="/api/v1/documents",
    tags=["Document Search"],
)

app.include_router(
    document_tools_router,
    prefix="/api/v1/documents",
    tags=["Document Tools"],
)

app.include_router(
    document_sharing_router,
    prefix="/api/v1/documents",
    tags=["Sharing"],
)

app.include_router(
    documents_router,
    prefix="/api/v1/documents",
    tags=["Documents"],
)

app.include_router(
    youtube_router,
    prefix="/api/v1/youtube",
    tags=["YouTube"],
)

# Before the chats router so /chats/shared is not read
# as a chat ID.
app.include_router(
    chat_sharing_router,
    prefix="/api/v1/chats",
    tags=["Sharing"],
)

app.include_router(
    chats_router,
    prefix="/api/v1/chats",
    tags=["Chats"],
)