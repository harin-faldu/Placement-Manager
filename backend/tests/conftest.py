import os
from pathlib import Path

from cryptography.fernet import Fernet

os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["SECRET_KEY"] = "test-secret-key"
os.environ["FERNET_KEY"] = Fernet.generate_key().decode()
os.environ["SEED"] = "1"
os.environ["COOKIE_SECURE"] = "false"
os.environ["TRUST_PROXY"] = "false"
os.environ["CORS_ORIGINS"] = "http://localhost:5173"

env_file = Path(__file__).resolve().parents[2] / ".env"
if env_file.is_file():
    for raw in env_file.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))

import pytest
from fastapi.testclient import TestClient

from app.core.database import Base, engine
from app.main import app


@pytest.fixture()
def client():
    Base.metadata.drop_all(bind=engine)
    with TestClient(app) as test_client:
        yield test_client
