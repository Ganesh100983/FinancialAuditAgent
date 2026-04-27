from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Auth
    secret_key: str = "test12345"
    algorithm: str = "HS256"
    access_token_expire_hours: int = 24

    # Demo users — in production, replace with a real user store / DB
    demo_users: dict = {
        "auditor": {"password": "FinAudit@2025",  "role": "auditor"},
        "viewer":  {"password": "FinView@2025",   "role": "viewer"},
    }

    # OpenAI
    openai_api_key: str = ""

    # CORS — comma-separated list of allowed origins
    allowed_origins: str = "http://localhost:5173,http://localhost:3000"

    # Rate limits
    rate_limit_default: str = "60/minute"
    rate_limit_ai: str = "10/minute"

    # Session
    session_ttl_hours: int = 8

    # Company defaults
    default_company_name: str = "ABC Pvt Ltd"
    default_gstin: str = "27AABCE1234A1Z5"
    default_tan: str = "MUMA12345A"
    default_pan: str = "AABCE1234A"
    default_financial_year: str = "2024-25"

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.allowed_origins.split(",")]


@lru_cache
def get_settings() -> Settings:
    return Settings()
