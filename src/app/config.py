# src/app/config.py
from pydantic_settings import BaseSettings
from pydantic import Field

class Settings(BaseSettings):
    DATABASE_URL: str = Field(
        default="postgresql://postgres@localhost:5432/setu_reconciliation",
        validation_alias="DATABASE_URL"
    )
    PORT: int = Field(default=8000, validation_alias="PORT")
    HOST: str = Field(default="0.0.0.0", validation_alias="HOST")
    DISCREPANCY_THRESHOLD_HOURS: float = Field(default=6.0, validation_alias="DISCREPANCY_THRESHOLD_HOURS")

    class Config:
        env_file = ".env"
        extra = "ignore"

settings = Settings()
