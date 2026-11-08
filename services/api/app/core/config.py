from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_JWT_SECRET = "dev-only-jwt-secret-change-me-before-any-real-use"
DEFAULT_FILE_SECRET = "dev-only-file-secret-change-me-before-any-real-use"


ROOT_ENV = Path(__file__).resolve().parents[4] / ".env"  # repo root: the only .env


class Settings(BaseSettings):
    # Reads the single repo-root .env (see ROOT_ENV) or real environment variables.
    model_config = SettingsConfigDict(env_file=ROOT_ENV, extra="ignore")

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
    photo_embedder: str = "fastembed"  # fastembed | fake | none (seller claim check by photo)
    photo_embedding_model: str = "google/siglip2-base-patch16-224"
    search_min_similarity: float = 0.35
    hold_minutes: int = 15
    default_commission_bps: int = 500  # demo value (5%), configurable by admin
    buyer_service_fee_idr: int = 0  # buyer-visible platform fee; zero until configured
    prompt_interpreter: str = "rules"  # rules | llm (llm always falls back to rules on failure)
    llm_provider: str = "openrouter"  # openai | openrouter | ollama
    llm_model: str = "openai/gpt-6-luna"
    openai_api_key: str = ""
    openrouter_api_key: str = ""
    pose_model_path: str = "./models/pose_landmarker_full.task"
    photo_default_retention_minutes: int = 60  # raw body photos are purged after this by default
    photo_max_retention_days: int = 7
    photo_max_bytes: int = 8_000_000
    vlm_timeout_seconds: int = 90
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"  # comma separated
    upload_max_bytes: int = 8_000_000
    claim_window_days: int = 14  # demo policy: claims open until N days after delivery
    partner_response_sla_hours: int = 48  # demo policy: partner must react within N hours


settings = Settings()


def assert_production_safe(s: Settings) -> None:
    if s.app_env != "development" and (
        s.jwt_secret == DEFAULT_JWT_SECRET or s.file_url_secret == DEFAULT_FILE_SECRET
    ):
        raise RuntimeError("Set JWT_SECRET and FILE_URL_SECRET outside development")
