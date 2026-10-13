from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def load_env_file() -> None:
    here = Path(__file__).resolve()
    candidates = [here.parents[3] / ".env", here.parents[2] / ".env", Path.cwd() / ".env"]
    for path in candidates:
        if not path.is_file():
            continue
        for raw in path.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))
        return


def _required(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"{name} is not set. Copy .env.example to .env and fill it in.")
    return value


load_env_file()


@dataclass(frozen=True)
class Settings:
    database_url: str = _required("DATABASE_URL")
    secret_key: str = _required("SECRET_KEY")
    fernet_key: str = _required("FERNET_KEY")
    seed: bool = os.getenv("SEED", "0") == "1"
    cookie_secure: bool = os.getenv("COOKIE_SECURE", "false").lower() == "true"
    trust_proxy: bool = os.getenv("TRUST_PROXY", "false").lower() == "true"
    cors_origins: str = os.getenv("CORS_ORIGINS", "")
    session_hours: int = int(os.getenv("SESSION_HOURS", "8"))
    idle_minutes: int = int(os.getenv("IDLE_MINUTES", "30"))
    cookie_name: str = "placement_session"


settings = Settings()
