from pydantic import BaseModel, ConfigDict
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "hr-anomaly-pipeline"
    debug: bool = False

    docling_confidence_threshold: float = 0.75
    docling_confidence_max: float = 1.0

    rapidocr_enabled: bool = True

    rapidocr_model_path: str = "models/rapidocr/en_ppocr_server_v2.0_infer.onnx"
    rapidocr_timeout_seconds: int = 30

    rapidocr_default_confidence: float = 0.6

    celery_broker_url: str = "redis://localhost:6379/0"
    celery_result_backend: str = "redis://localhost:6379/1"
    celery_task_soft_time_limit: int = 300
    celery_task_max_retries: int = 3
    celery_task_default_retry_delay: int = 60

    review_timeout_hours: int = 48


class ExtractPipelineConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    docling_confidence_threshold: float
    rapidocr_enabled: bool
    rapidocr_model_path: str
    rapidocr_timeout_seconds: int
    rapidocr_default_confidence: float


def make_extract_pipeline_config(settings: Settings) -> ExtractPipelineConfig:
    return ExtractPipelineConfig(
        docling_confidence_threshold=settings.docling_confidence_threshold,
        rapidocr_enabled=settings.rapidocr_enabled,
        rapidocr_model_path=settings.rapidocr_model_path,
        rapidocr_timeout_seconds=settings.rapidocr_timeout_seconds,
        rapidocr_default_confidence=settings.rapidocr_default_confidence,
    )
