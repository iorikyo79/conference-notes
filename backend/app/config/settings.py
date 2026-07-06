"""Application Settings"""
from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    """Application Settings"""

    # Application
    APP_NAME: str = "Conference Notes"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = True

    # Server
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    # Paths
    BASE_DIR: str = "."
    STORAGE_DIR: str = "storage"
    DATA_DIR: str = "storage/data"
    UPLOAD_DIR: str = "storage/uploads"
    REPORTS_DIR: str = "storage/reports"
    CONFERENCES_DIR: str = "storage/conferences"

    # File Upload
    MAX_FILE_SIZE: int = 50 * 1024 * 1024  # 50MB

    # Zhipu AI (GLM)
    ZHIPU_API_KEY: Optional[str] = None
    ZHIPU_MODEL: str = "glm-4-flash"

    # Ollama (Local LLM)
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "qwen2.5:14b"

    # Note auto-save
    AUTOSAVE_DEBOUNCE_MS: int = 2000

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
