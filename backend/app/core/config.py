from pydantic_settings import BaseSettings


class Settings(BaseSettings):

    mongodb_url: str = "mongodb://127.0.0.1:27017"

    database_name: str = "documind_ai"

    jwt_secret_key: str

    gemini_api_key: str

    vector_search_enabled: bool = False

    class Config:
        env_file = ".env"


settings = Settings()