import os

os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["SECRET_KEY"] = "test-secret-key"
os.environ["FERNET_KEY"] = "MJwr1Ha0E6YjANmlqa58KANk9eQxMlf5OabFobfgfgk="
os.environ["SEED"] = "1"
os.environ["COOKIE_SECURE"] = "false"
os.environ["TRUST_PROXY"] = "false"
os.environ["CORS_ORIGINS"] = "http://localhost:5173"

import pytest
from fastapi.testclient import TestClient

from app.database import Base, engine
from app.main import app


@pytest.fixture()
def client():
    Base.metadata.drop_all(bind=engine)
    with TestClient(app) as test_client:
        yield test_client
