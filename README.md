# Football API

A FastAPI backend for football leagues, teams, players and live match events, with Redis caching and Kafka-driven background workers.

## Features

- **CRUD** for leagues, teams, players and matches, with filtering and pagination
- **League tables** computed in SQL (played, W/D/L, goals, points), cached in Redis
- **Live match events** (goals, cards, substitutions, VAR) stored in MongoDB, with a per-match timeline
- **Top scorers** aggregated from match events
- **JWT authentication** with admin-only write routes, logout via a Redis token blocklist, and login rate limiting
- **Kafka workers** that react to match events: follower notifications and a live Redis leaderboard, with retries and a dead-letter queue

## Tech stack

| Area | Technology |
|---|---|
| API | Python 3.12, FastAPI, Pydantic |
| Relational data | PostgreSQL, SQLAlchemy, Alembic |
| Match events | MongoDB (Motor) |
| Cache, rate limits, leaderboard | Redis |
| Messaging | Kafka (aiokafka) |
| Tooling | Docker Compose, Ruff |

## Getting started

Requires Python 3.12+ and Docker.

```bash
git clone https://github.com/harelshaish-dotcom/football-api.git
cd football-api

python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env               # Windows: copy .env.example .env
                                   # then set SECRET_KEY to a long random string

docker compose up -d               # PostgreSQL, MongoDB, Redis, Kafka
alembic upgrade head               # create the PostgreSQL tables
python -m scripts.seed             # optional: sample leagues, teams, players + admin user
```

### Run the API

```bash
uvicorn app.main:app --reload
```

Interactive docs: http://127.0.0.1:8000/docs. Use **Authorize** to log in. The seeded admin is `admin@example.com` / `password123`.

### Run the workers

Each worker is a separate process that consumes the `match-events` Kafka topic:

```bash
python -m workers.notifications
python -m workers.stats
```

### Useful scripts

```bash
python -m scripts.make_admin you@example.com    # promote an existing user to admin
```

## Configuration

Settings are read from environment variables or `.env` (see [app/core/config.py](app/core/config.py)):

| Variable | Default |
|---|---|
| `SECRET_KEY` | *(required)* |
| `DATABASE_URL` | `postgresql+psycopg2://postgres:dev@localhost:5432/football` |
| `MONGO_URL` | `mongodb://localhost:27017` |
| `REDIS_URL` | `redis://localhost:6379` |
| `KAFKA_BOOTSTRAP_SERVERS` | `localhost:9092` |

Alembic reads its database URL from `alembic.ini`.

## Project structure

```
football-api/
├── app/
│   ├── main.py              # FastAPI app, startup checks, router registration
│   ├── routes/              # HTTP endpoints, one module per resource
│   ├── controllers/         # database queries used by the routes
│   ├── core/                # config, security (JWT/passwords), auth dependencies, Redis cache, Kafka producer
│   ├── db/                  # PostgreSQL and MongoDB connections
│   ├── models/              # SQLAlchemy tables
│   └── schemas/             # Pydantic request/response models
├── workers/                 # Kafka consumers (notifications, stats) and their shared retry/DLQ code
├── scripts/                 # seed data, make_admin
├── alembic/                 # database migrations
├── docs/                    # API spec and design notes
├── docker-compose.yml
├── requirements.txt         # runtime dependencies
├── requirements-dev.txt     # + ruff
└── pyproject.toml           # ruff settings
```

## Development

```bash
pip install -r requirements-dev.txt
ruff format .
ruff check .
```
