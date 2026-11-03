# ============================================================
# IMPORTS
# ============================================================

import json
import re
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, quote, urlparse
from urllib.request import urlopen

from bson import ObjectId

from app.core.database import db
from app.services.chunk_service import (
    chunk_pages,
    save_chunks,
)
from app.services.document_service import (
    update_document_status,
)
from app.services.gemini_service import (
    generate_from_youtube,
)


# ============================================================
# YOUTUBE VIDEOS AS DOCUMENTS
# ============================================================
#
# A YouTube link becomes a document whose text is a
# timestamped transcript written by Gemini, which watches the
# video (speech and frames) directly from the public URL:
#
#     [00:00] Welcome to the course...
#     [00:42] [Visual] A slide titled "Three types of ..."
#
# The transcript then goes through the normal pipeline
# (chunks, embeddings, search, RAG), so video chats work like
# document chats. Answers cite the [mm:ss] timestamps.

VIDEO_ID_PATTERN = re.compile(
    r"^[A-Za-z0-9_-]{11}$"
)

# A line's start time, in any style Gemini writes it:
#   [00:04] text    00:04 text    (00:04) text    **00:04** text
#   00:04 - text    [00:04 - 00:10] text    - 1:02:03: text
TIMESTAMP_PATTERN = re.compile(
    r"^[\s*_>-]*[\[(]?"
    r"(?:(\d{1,2}):)?(\d{1,2}):(\d{2})"
    r"(?:\s*[-–—]\s*(?:\d{1,2}:)?\d{1,2}:\d{2})?"
    r"[\])]?[*_]*\s*[-–—:]?\s*"
)

YOUTUBE_HOSTS = {
    "youtube.com",
    "www.youtube.com",
    "m.youtube.com",
    "music.youtube.com",
    "youtu.be",
    "www.youtu.be",
}

# Transcript segments are kept below the 500-character chunk
# size, so every chunk starts with its own timestamp.
SEGMENT_CHAR_LIMIT = 450

TRANSCRIPT_PROMPT = """
Watch this whole video and write a complete, timestamped
transcript of it.

Rules:
- One line per sentence or short phrase. Start every line
  with the time it begins, as [mm:ss] (or [h:mm:ss] after
  one hour).
- Transcribe the speech accurately, in the language spoken.
- When something important appears on screen (slides, text,
  code, diagrams, charts, demonstrations), add a line:
  [mm:ss] [Visual] a short description, including any text
  shown.
- If there is no speech, describe what happens every 10 to
  20 seconds.
- Output only the transcript lines, with no introduction,
  headings or summary.
"""


# ============================================================
# PARSE A YOUTUBE LINK
# ============================================================

def parse_video_id(
    url: str
) -> str | None:
    """
    Return the 11-character video ID from a YouTube link, or
    None when the link is not a YouTube video.

    Supports watch?v=, youtu.be/, /shorts/, /embed/, /live/
    and /v/ links.
    """

    if not isinstance(
        url,
        str
    ):
        return None

    url = url.strip()

    if not re.match(
        r"^https?://",
        url
    ):
        url = f"https://{url}"

    parsed = urlparse(
        url
    )

    host = (
        parsed.hostname or ""
    ).lower()

    if host not in YOUTUBE_HOSTS:
        return None

    video_id = None

    if host.endswith("youtu.be"):

        video_id = parsed.path.strip("/").split("/")[0]

    elif parsed.path == "/watch":

        video_id = parse_qs(
            parsed.query
        ).get(
            "v",
            [None]
        )[0]

    else:

        parts = parsed.path.strip("/").split("/")

        if len(parts) >= 2 and parts[0] in {
            "shorts",
            "embed",
            "live",
            "v"
        }:
            video_id = parts[1]

    if video_id and VIDEO_ID_PATTERN.match(
        video_id
    ):
        return video_id

    return None


def video_url(
    video_id: str
) -> str:
    """
    Canonical watch URL for a video ID.
    """

    return f"https://www.youtube.com/watch?v={video_id}"


# ============================================================
# VIDEO TITLE (YOUTUBE OEMBED)
# ============================================================

def fetch_video_info(
    video_id: str
) -> dict:
    """
    Return {"title", "author"} for a public video using
    YouTube's oEmbed endpoint (no API key needed).

    Raises ValueError for private, removed, or unknown
    videos, which Gemini could not watch either.
    """

    oembed_url = (
        "https://www.youtube.com/oembed?format=json&url="
        + quote(
            video_url(video_id),
            safe=""
        )
    )

    try:

        with urlopen(
            oembed_url,
            timeout=10
        ) as response:

            data = json.loads(
                response.read().decode("utf-8")
            )

    except HTTPError as error:

        raise ValueError(
            "This video is private, removed, or does not "
            "exist. Only public videos can be added."
        ) from error

    except (URLError, TimeoutError, ValueError) as error:

        raise RuntimeError(
            "Could not reach YouTube to check the video"
        ) from error

    return {
        "title":
            (data.get("title") or "YouTube video").strip(),
        "author":
            (data.get("author_name") or "").strip()
    }


# ============================================================
# TIMESTAMPS
# ============================================================

def timestamp_seconds(
    line: str
) -> int | None:
    """
    Return the start time of a "[mm:ss]" or "[h:mm:ss]"
    transcript line in seconds, or None.
    """

    match = TIMESTAMP_PATTERN.match(
        line.strip()
    )

    if not match:
        return None

    hours, minutes, seconds = match.groups()

    return (
        int(hours or 0) * 3600
        + int(minutes) * 60
        + int(seconds)
    )


def format_timestamp(
    seconds: int
) -> str:
    """
    Seconds as "mm:ss", or "h:mm:ss" after one hour.
    """

    hours, rest = divmod(
        seconds,
        3600
    )

    minutes, secs = divmod(
        rest,
        60
    )

    if hours:
        return f"{hours}:{minutes:02d}:{secs:02d}"

    return f"{minutes:02d}:{secs:02d}"


def normalize_line(
    line: str
) -> str | None:
    """
    Rewrite a timestamped line to the standard form
    "[mm:ss] text", or return None when it has no time.
    """

    match = TIMESTAMP_PATTERN.match(
        line
    )

    if not match:
        return None

    seconds = timestamp_seconds(
        line
    )

    text = line[match.end():].strip()

    return f"[{format_timestamp(seconds)}] {text}".strip()


# ============================================================
# TRANSCRIPT TO SEGMENTS
# ============================================================

def transcript_segments(
    transcript: str
) -> list[dict]:
    """
    Group transcript lines into segments of up to about
    450 characters, each starting at a timestamped line.

    Returns page-like dicts for chunk_pages(); videos have no
    page numbers, so page_number is None.
    """

    # --------------------------------------------------------
    # Join lines without a timestamp to the previous line
    # --------------------------------------------------------

    lines = []

    for raw_line in transcript.splitlines():

        line = raw_line.strip().strip("`").strip()

        if not line:
            continue

        normalized = normalize_line(
            line
        )

        if normalized is not None:

            lines.append(
                normalized
            )

        elif lines:

            lines[-1] = f"{lines[-1]} {line}"

    # --------------------------------------------------------
    # Group lines into segments
    # --------------------------------------------------------

    segments = []
    current = []
    current_length = 0

    for line in lines:

        if current and current_length + len(line) > SEGMENT_CHAR_LIMIT:

            segments.append(
                "\n".join(current)
            )

            current = []
            current_length = 0

        current.append(
            line
        )

        current_length += len(line) + 1

    if current:

        segments.append(
            "\n".join(current)
        )

    return [
        {
            "page_number":
                None,
            "text":
                segment
        }
        for segment in segments
    ]


# ============================================================
# PROCESS A VIDEO (BACKGROUND TASK)
# ============================================================

def process_youtube_document(
    document_id: str,
    user_id: str,
    video_id: str,
):
    """
    Transcribe a video with Gemini, then chunk and embed the
    transcript. Never raises: failures are saved on the
    document as status "failed" with a reason.
    """

    try:

        transcript = generate_from_youtube(
            video_url(video_id),
            TRANSCRIPT_PROMPT
        )

        pages = transcript_segments(
            transcript or ""
        )

        if not pages:

            update_document_status(
                document_id=document_id,
                user_id=user_id,
                status="failed",
                processing_error=(
                    "No speech or content could be read "
                    "from this video"
                ),
            )

            return

        chunks = chunk_pages(
            pages
        )

        saved_chunk_count = save_chunks(
            document_id=document_id,
            user_id=user_id,
            chunks=chunks,
        )

        text = "\n".join(
            page["text"]
            for page in pages
        )

        timestamps = [
            seconds
            for seconds in (
                timestamp_seconds(line)
                for line in text.splitlines()
            )
            if seconds is not None
        ]

        db.documents.update_one(
            {
                "_id":
                    ObjectId(document_id),
                "user_id":
                    user_id
            },
            {
                "$set": {
                    "extracted_text":
                        text,
                    "chunk_count":
                        saved_chunk_count,
                    "character_count":
                        len(text),
                    "word_count":
                        len(text.split()),
                    "duration_seconds":
                        max(timestamps) if timestamps else 0,
                    "processing_error":
                        None,
                    "status":
                        "completed"
                }
            }
        )

    except Exception as error:

        print(
            "YouTube processing failed:"
        )

        print(error)

        update_document_status(
            document_id=document_id,
            user_id=user_id,
            status="failed",
            processing_error=(
                "Gemini could not watch this video. It may be "
                "too long, age-restricted, or unavailable."
            ),
        )
