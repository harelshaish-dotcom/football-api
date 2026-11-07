"""Shared pytest setup. Runs before any test module imports the app."""

import os

# app.core.security raises at import time when SECRET_KEY is missing, and CI has no .env file.
os.environ.setdefault("SECRET_KEY", "test-secret-not-for-production")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402


@pytest.fixture
def client() -> TestClient:
    """A TestClient that does NOT run the lifespan handler.

    Plain TestClient(app), used outside a `with` block, skips startup, so the tests
    never try to reach MongoDB, Redis or Kafka.
    """
    return TestClient(app)
