# ============================================================
# IMPORTS
# ============================================================

from datetime import datetime, timezone

from bson import ObjectId
from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    HTTPException,
    Request,
    status,
)
from fastapi.security import HTTPAuthorizationCredentials

from app.core.database import db
from app.core.rate_limiter import limiter
from app.core.security import (
    security,
    verify_access_token,
)
from app.schemas.document import YouTubeRequest
from app.services.youtube_service import (
    fetch_video_info,
    parse_video_id,
    process_youtube_document,
    video_url,
)


# ============================================================
# ROUTER
# ============================================================

router = APIRouter()


# ============================================================
# AUTHENTICATION
# ============================================================

def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(
        security
    ),
):

    return verify_access_token(
        credentials
    )


# ============================================================
# ADD A YOUTUBE VIDEO
# ============================================================

@router.post("")
@limiter.limit("10/minute")
def add_youtube_video(
    request: Request,
    video: YouTubeRequest,
    background_tasks: BackgroundTasks,
    user_id: str = Depends(
        get_current_user
    ),
):

    """
    Add a public YouTube video by link.

    The video is checked and saved as a document with status
    "processing"; Gemini transcribes it in the background.
    Adding the same video again returns the existing one
    (unless it failed, in which case it is retried).
    """

    # --------------------------------------------------------
    # Validate link
    # --------------------------------------------------------

    video_id = parse_video_id(
        video.url
    )

    if not video_id:

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Paste a YouTube video link, e.g. https://www.youtube.com/watch?v=…",
        )

    # --------------------------------------------------------
    # Already added
    # --------------------------------------------------------

    existing = db.documents.find_one(
        {
            "user_id": user_id,
            "video_id": video_id,
        }
    )

    if existing and existing.get("status") != "failed":

        return {
            "id": str(existing["_id"]),
            "filename": existing.get("filename"),
            "status": existing.get("status"),
            "video_id": video_id,
            "already_added": True,
        }

    # --------------------------------------------------------
    # Public video check and title
    # --------------------------------------------------------

    try:

        info = fetch_video_info(
            video_id
        )

    except ValueError as error:

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error),
        )

    except RuntimeError as error:

        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(error),
        )

    # --------------------------------------------------------
    # Create (or reset) the video document
    # --------------------------------------------------------

    fields = {
        "user_id": user_id,
        "filename": info["title"],
        "file_type": "video/youtube",
        "file_size": 0,
        "status": "processing",
        "processing_type": "youtube",
        "processing_error": None,
        "extracted_text": "",
        "video_id": video_id,
        "source_url": video_url(video_id),
        "author": info["author"],
        "created_at": datetime.now(timezone.utc),
    }

    if existing:

        document_id = str(existing["_id"])

        db.document_chunks.delete_many(
            {
                "document_id": document_id,
                "user_id": user_id,
            }
        )

        db.documents.update_one(
            {
                "_id": ObjectId(document_id),
            },
            {
                "$set": fields,
            },
        )

    else:

        document_id = str(
            db.documents.insert_one(
                fields
            ).inserted_id
        )

    # --------------------------------------------------------
    # Transcribe in the background
    # --------------------------------------------------------

    background_tasks.add_task(

        process_youtube_document,

        document_id=document_id,

        user_id=user_id,

        video_id=video_id,

    )

    return {

        "id": document_id,

        "filename": info["title"],

        "status": "processing",

        "video_id": video_id,

        "already_added": False,

    }
