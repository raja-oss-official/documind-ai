# ============================================================
# IMPORTS
# ============================================================

from pydantic_settings import BaseSettings


# ============================================================
# APPLICATION SETTINGS (.ENV)
# ============================================================

class Settings(BaseSettings):

    mongodb_url: str = "mongodb://127.0.0.1:27017"

    database_name: str = "documind_ai"

    jwt_secret_key: str

    gemini_api_key: str

    vector_search_enabled: bool = False

    # Comma-separated browser origins allowed to call the API
    # (e.g. the deployed frontend URL). Defaults to local Vite dev.
    cors_origins: str = (
        "http://localhost:5173,"
        "http://127.0.0.1:5173"
    )

    # Optional regex for extra origins, e.g. Vercel preview URLs:
    # https://documind-ai-.*\.vercel\.app
    cors_origin_regex: str | None = None

    @property
    def cors_origin_list(self) -> list[str]:
        return [
            origin.strip().rstrip("/")
            for origin in self.cors_origins.split(",")
            if origin.strip()
        ]

    class Config:
        env_file = ".env"


# ============================================================
# SETTINGS INSTANCE
# ============================================================

settings = Settings()