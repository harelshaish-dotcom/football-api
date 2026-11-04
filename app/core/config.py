"""Application settings, read from environment variables (and `.env`, if present).

Every value except SECRET_KEY has a default that matches the local
docker-compose setup, so the app runs out of the box in development.
"""

import os

from dotenv import load_dotenv

load_dotenv()

# Required by the API (JWT signing); checked in app.core.security so that
# workers and scripts, which never sign tokens, can run without it.
SECRET_KEY: str | None = os.getenv("SECRET_KEY")

DATABASE_URL: str = os.getenv(
    "DATABASE_URL", "postgresql+psycopg2://postgres:dev@localhost:5432/football"
)
MONGO_URL: str = os.getenv("MONGO_URL", "mongodb://localhost:27017")
REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379")
KAFKA_BOOTSTRAP_SERVERS: str = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
