from google import genai

from app.core.config import settings


# ============================================================
# GEMINI CLIENT
# ============================================================

client = genai.Client(
    api_key=settings.gemini_api_key
)


# ============================================================
# EMBEDDING MODEL
# ============================================================

EMBEDDING_MODEL = "gemini-embedding-2"


# ============================================================
# CREATE EMBEDDING
# ============================================================

def create_embedding(
    text: str
) -> list[float]:
    """
    Generate a vector embedding for the supplied text.

    The same embedding model must be used for:
    - document chunk embeddings
    - future query embeddings

    This is important because vector similarity requires
    both vectors to exist in the same embedding space.
    """

    # --------------------------------------------------------
    # Validate input
    # --------------------------------------------------------

    if not isinstance(
        text,
        str
    ):

        raise ValueError(
            "Embedding text must be a string"
        )

    text = text.strip()

    if not text:

        raise ValueError(
            "Cannot create an embedding for empty text"
        )

    # --------------------------------------------------------
    # Generate embedding
    # --------------------------------------------------------

    try:

        response = client.models.embed_content(

            model=EMBEDDING_MODEL,

            contents=text
        )

    except Exception as error:

        print(
            "Gemini embedding generation failed:"
        )

        print(error)

        raise RuntimeError(
            "Unable to generate document embedding"
        ) from error

    # --------------------------------------------------------
    # Validate response
    # --------------------------------------------------------

    if not response:

        raise RuntimeError(
            "Gemini returned an empty embedding response"
        )

    embeddings = getattr(
        response,
        "embeddings",
        None
    )

    if not embeddings:

        raise RuntimeError(
            "Gemini returned no embeddings"
        )

    first_embedding = embeddings[0]

    values = getattr(
        first_embedding,
        "values",
        None
    )

    if not values:

        raise RuntimeError(
            "Gemini returned an empty embedding vector"
        )

    # --------------------------------------------------------
    # Convert values to normal Python floats
    # --------------------------------------------------------

    embedding = [
        float(value)
        for value in values
    ]

    if not embedding:

        raise RuntimeError(
            "Generated embedding vector is empty"
        )

    return embedding