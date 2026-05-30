from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    DATABASE_URL: str = "sqlite:///./logs.db"
    REDIS_URL: str = "redis://localhost:6379/0"
    # Azure OpenAI
    AZURE_OPENAI_ENDPOINT: Optional[str] = None
    AZURE_OPENAI_API_KEY: Optional[str] = None
    AZURE_OPENAI_DEPLOYMENT: str = "gpt-5.4"
    AZURE_OPENAI_API_VERSION: str = "2024-12-01-preview"
    AZURE_OPENAI_TEMPERATURE: float = 0.1
    AZURE_OPENAI_MAX_TOKENS: int = 100000
    KUBECONFIG: Optional[str] = None
    LOG_RETENTION_DAYS: int = 30
    SECRET_KEY: str = "your-secret-key-change-in-production"

    class Config:
        env_file = ".env"


settings = Settings()
