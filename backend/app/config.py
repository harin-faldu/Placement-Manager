from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    database_url: str = os.getenv("DATABASE_URL", "sqlite:///./placement.db")
    secret_key: str = os.getenv("SECRET_KEY", "dev-only-change-me")
    fernet_key: str = os.getenv("FERNET_KEY", "MJwr1Ha0E6YjANmlqa58KANk9eQxMlf5OabFobfgfgk=")
    seed: bool = os.getenv("SEED", "1") == "1"
    cookie_secure: bool = os.getenv("COOKIE_SECURE", "false").lower() == "true"
    trust_proxy: bool = os.getenv("TRUST_PROXY", "false").lower() == "true"
    cors_origins: str = os.getenv("CORS_ORIGINS", "http://localhost:5173")
    session_hours: int = int(os.getenv("SESSION_HOURS", "8"))
    idle_minutes: int = int(os.getenv("IDLE_MINUTES", "30"))
    cookie_name: str = "placement_session"


settings = Settings()
