from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str = "sqlite:///./recoverai.db"
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    razorpay_key_id: str = ""
    razorpay_key_secret: str = ""
    openai_api_key: str = ""

    # Policy bounds (bar requirements)
    max_automatic_retries: int = 2
    max_recovery_attempts: int = 3
    human_approval_amount_paise: int = 2_500_000  # ₹25,000

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def razorpay_enabled(self) -> bool:
        return bool(self.razorpay_key_id and self.razorpay_key_secret)


@lru_cache
def get_settings() -> Settings:
    return Settings()
