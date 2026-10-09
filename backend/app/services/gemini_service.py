from google import genai

from app.core.config import settings


client = genai.Client(
    api_key=settings.gemini_api_key
)


MODELS = [
    "gemini-3.1-flash-lite",
    "gemini-3.1-flash",
    "gemini-3.5-flash-lite",
    "gemini-3.5-flash",
]


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