import os

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    rime_api_key: str = ""
    rime_speaker: str = "nadi"
    rime_model: str = "coda"

    hf_token: str = ""

    openai_api_key: str = ""
    openai_base_url: str = "https://api.openai.com/v1"
    openai_model: str = "gpt-4o-mini"

    qdrant_url: str = "http://localhost:6333"
    qdrant_collection: str = "complaint_vectors"
    qdrant_location_weight: float = 0.45
    qdrant_platform_weight: float = 0.30
    qdrant_time_weight: float = 0.25
    qdrant_pattern_threshold: float = 0.65
    qdrant_min_cluster_size: int = 2

    database_url: str = "sqlite:///./data/database/wagelens.db"
    api_port: int = 8080

    crew_verbose: bool = False
    log_level: str = "INFO"
    log_format: str = "text"
    log_file: str = "./data/logs/wagelens.log"
    cors_origins: str = (
        "http://localhost:3000,http://127.0.0.1:3000,"
        "http://localhost:8080,http://127.0.0.1:8080"
    )

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def real_services_enabled(self) -> bool:
        return bool(self.rime_api_key) and bool(self.openai_api_key)


settings = Settings()

if settings.hf_token:
    os.environ.setdefault("HF_TOKEN", settings.hf_token)
    os.environ.setdefault("HUGGING_FACE_HUB_TOKEN", settings.hf_token)
