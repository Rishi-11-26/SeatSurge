from typing import List, Union
from pydantic import AnyHttpUrl, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # General
    PROJECT_NAME: str = "SeatSurge"
    VERSION: str = "0.1.0"
    API_V1_STR: str = "/api/v1"
    APP_ENV: str = "production"
    INSTANCE_ID: str = "backend-1"
    PORT: int = 8000
    LOG_LEVEL: str = "INFO"

    # Security
    SECRET_KEY: str = "seatsurge-development-secret-key-32chars-min"
    CORS_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
        "*"
    ]
    TRUSTED_PROXY_SUBNETS: List[str] = [
        "127.0.0.1/32",
        "172.16.0.0/12",
        "10.0.0.0/8",
        "192.168.0.0/16",
    ]

    # PostgreSQL Database
    DATABASE_URL: Union[str, None] = None
    POSTGRES_USER: str = "seatsurge"
    POSTGRES_PASSWORD: str = "seatsurge_secret"
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_DB: str = "seatsurge"

    @property
    def async_database_url(self) -> str:
        if self.DATABASE_URL:
            url = self.DATABASE_URL
            if url.startswith("postgres://"):
                url = url.replace("postgres://", "postgresql+asyncpg://", 1)
            elif url.startswith("postgresql://") and not url.startswith("postgresql+asyncpg://"):
                url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
            return url
        return f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"

    # Redis Cache & Coordination
    REDIS_URL: Union[str, None] = None
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    REDIS_PASSWORD: Union[str, None] = None
    REDIS_SSL: bool = False

    @property
    def redis_url(self) -> str:
        if self.REDIS_URL:
            return self.REDIS_URL
        proto = "rediss" if self.REDIS_SSL else "redis"
        if self.REDIS_PASSWORD:
            return f"{proto}://:{self.REDIS_PASSWORD}@{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"
        return f"{proto}://{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"

    # Ticketing Business Rules
    TOTAL_SEATS: int = 5040
    HOLD_DURATION_SECONDS: int = 120
    REAPER_INTERVAL_SECONDS: int = 5
    MAX_GROUP_SEATS: int = 6

    # Queue & Waiting Room (Phase 5)
    QUEUE_ADMISSION_CAPACITY: int = 100
    ADMISSION_TOKEN_TTL_SECONDS: int = 900  # 15 minutes
    ENFORCE_ADMISSION_TOKEN: bool = False  # Set True to strictly require token on holds


settings = Settings()
