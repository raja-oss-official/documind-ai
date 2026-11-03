# ============================================================
# IMPORTS
# ============================================================

import json

from google import genai
from google.genai import types

from app.core.config import settings


# ============================================================
# GEMINI CLIENT
# ============================================================

client = genai.Client(
    api_key=settings.gemini_api_key
)


# ============================================================
# GEMINI MODELS (TRIED IN ORDER)
# ============================================================

# Strongest model first for detailed answers; lighter models are fallbacks.
MODELS = [
    "gemini-3.5-flash",
    "gemini-3.1-flash",
    "gemini-3.5-flash-lite",
    "gemini-3.1-flash-lite",
]


# ============================================================
# GENERATE ANSWER
# ============================================================

def generate_answer(prompt: str) -> str:
    last_error = None

    for model in MODELS:
        try:
            response = client.models.generate_content(
                model=model,
                contents=prompt
            )

            if response.text:
                return response.text

        except Exception as error:
            last_error = error
            print(f"Gemini model failed: {model}")
            print(error)

    raise RuntimeError(
        f"All Gemini models failed. Last error: {last_error}"
    )


# ============================================================
# STREAM ANSWER
# ============================================================

def stream_answer(prompt: str):
    """
    Yield the answer text piece by piece as Gemini writes it.

    Models are tried in the same order as generate_answer().
    A model that fails before sending any text is skipped;
    once text has been sent, a failure is raised so the
    caller can keep what it already has.
    """

    last_error = None

    for model in MODELS:
        sent_text = False

        try:
            for chunk in client.models.generate_content_stream(
                model=model,
                contents=prompt
            ):
                if chunk.text:
                    sent_text = True
                    yield chunk.text

            if sent_text:
                return

        except Exception as error:
            if sent_text:
                raise

            last_error = error
            print(f"Gemini model failed: {model}")
            print(error)

    raise RuntimeError(
        f"All Gemini models failed. Last error: {last_error}"
    )


# ============================================================
# GENERATE JSON
# ============================================================

def generate_json(prompt: str):
    """
    Ask Gemini for a JSON answer and parse it.

    Code fences around the JSON are removed. Raises
    ValueError when the response is not valid JSON.
    """

    text = generate_answer(prompt).strip()

    if text.startswith("```"):
        text = text.split("\n", 1)[-1]
        text = text.rsplit("```", 1)[0]

    try:
        return json.loads(text)

    except json.JSONDecodeError as error:
        raise ValueError(
            "Gemini did not return valid JSON"
        ) from error


# ============================================================
# GENERATE FROM A YOUTUBE VIDEO
# ============================================================

def generate_from_youtube(video_url: str, prompt: str) -> str:
    """
    Ask Gemini about a public YouTube video (audio and frames).

    Low media resolution uses about a third of the tokens per
    second of video, so longer videos fit in one request.
    Models are tried in the same order as generate_answer().
    """

    last_error = None

    contents = types.Content(
        parts=[
            types.Part(
                file_data=types.FileData(
                    file_uri=video_url
                )
            ),
            types.Part(
                text=prompt
            ),
        ]
    )

    config = types.GenerateContentConfig(
        media_resolution=types.MediaResolution.MEDIA_RESOLUTION_LOW
    )

    for model in MODELS:
        try:
            response = client.models.generate_content(
                model=model,
                contents=contents,
                config=config
            )

            if response.text:
                return response.text

        except Exception as error:
            last_error = error
            print(f"Gemini model failed on video: {model}")
            print(error)

    raise RuntimeError(
        f"All Gemini models failed. Last error: {last_error}"
    )
