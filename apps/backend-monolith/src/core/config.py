from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    SUPABASE_URL: str
    SUPABASE_ANON_KEY: str
    SUPABASE_SERVICE_ROLE_KEY: str
    SUPABASE_STORAGE_BUCKET_EVIDENCIAS: str = "justificaciones-evidencias"
    SYNTHETIC_EMAIL_DOMAIN: str = "catequesis.local"
    TELEGRAM_BOT_USERNAME: str = "CatequesisParroquiaBot"
    ALLOWED_CORS_ORIGINS: str = "http://localhost:5173"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def cors_origins_list(self) -> List[str]:
        return [origin.strip() for origin in self.ALLOWED_CORS_ORIGINS.split(",") if origin.strip()]

    def build_synthetic_email(self, username: str) -> str:
        clean_user = username.strip().lower()
        return f"{clean_user}@{self.SYNTHETIC_EMAIL_DOMAIN}"


settings = Settings()