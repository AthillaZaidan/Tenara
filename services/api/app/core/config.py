from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_JWT_SECRET = "dev-only-jwt-secret-change-me-before-any-real-use"
DEFAULT_FILE_SECRET = "dev-only-file-secret-change-me-before-any-real-use"


class Settings(BaseSettings):
    # Reads the repo-root .env (two levels above services/api) or real env vars.
    model_config = SettingsConfigDict(env_file=("../../.env", ".env"), extra="ignore")

    app_env: str = "development"
    database_url: str = "postgresql+psycopg://tenara:tenara@localhost:5432/tenara"
    test_database_url: str = "postgresql+psycopg://tenara:tenara@localhost:5432/tenara_test"
    jwt_secret: str = DEFAULT_JWT_SECRET
    jwt_algorithm: str = "HS256"
    access_token_hours: int = 12
    file_url_secret: str = DEFAULT_FILE_SECRET
    file_url_ttl_seconds: int = 300
    storage_dir: str = "./storage"
    embedder: str = "fastembed"  # fastembed | fake | none
    embedding_model: str = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    search_min_similarity: float = 0.35


settings = Settings()


def assert_production_safe(s: Settings) -> None:
    if s.app_env != "development" and (
        s.jwt_secret == DEFAULT_JWT_SECRET or s.file_url_secret == DEFAULT_FILE_SECRET
    ):
        raise RuntimeError("Set JWT_SECRET and FILE_URL_SECRET outside development")
