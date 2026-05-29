from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    DATABASE_URL: str = "sqlite:///./logs.db"
    REDIS_URL: str = "redis://localhost:6379/0"
    GEMINI_API_KEY: Optional[str] = None
    GEMINI_MODEL: str = "gemini-1.5-flash"
    KUBECONFIG: Optional[str] = None
    LOG_RETENTION_DAYS: int = 30
    SECRET_KEY: str = "your-secret-key-change-in-production"
    
    class Config:
        env_file = ".env"


settings = Settings()
