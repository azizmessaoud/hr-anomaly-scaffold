from pydantic import BaseModel, ConfigDict
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "hr-anomaly-pipeline"
    debug: bool = False

    docling_confidence_threshold: float = 0.75
    docling_confidence_max: float = 1.0

    ollama_base_url: str = "http://127.0.0.1:11434"
    ollama_model: str = "richardyoung/smolvlm2-2.2b-instruct:q4_k_m"
    ollama_timeout_seconds: int = 120

    vlm_default_confidence: float = 0.6

    celery_broker_url: str = "redis://localhost:6379/0"
    celery_result_backend: str = "redis://localhost:6379/1"
    celery_task_soft_time_limit: int = 300
    celery_task_max_retries: int = 3
    celery_task_default_retry_delay: int = 60

    review_timeout_hours: int = 48


class ExtractPipelineConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    docling_confidence_threshold: float
    ollama_base_url: str
    ollama_model: str
    ollama_timeout_seconds: int
    vlm_default_confidence: float


def make_extract_pipeline_config(settings: Settings) -> ExtractPipelineConfig:
    return ExtractPipelineConfig(
        docling_confidence_threshold=settings.docling_confidence_threshold,
        ollama_base_url=settings.ollama_base_url,
        ollama_model=settings.ollama_model,
        ollama_timeout_seconds=settings.ollama_timeout_seconds,
        vlm_default_confidence=settings.vlm_default_confidence,
    )
