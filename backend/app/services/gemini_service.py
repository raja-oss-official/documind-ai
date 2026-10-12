# ============================================================
# IMPORTS
# ============================================================

from google import genai

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