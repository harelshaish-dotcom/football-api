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
| Observability | OpenTelemetry, Elasticsearch, Kibana, Elastic APM Server |
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

docker compose up -d               # PostgreSQL, MongoDB, Redis, Kafka, Elastic stackC
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

## Observability (Elastic)

`docker compose up -d` also starts an Elastic stack (9.5.6, local-dev mode, no passwords):

| Service | URL | Role |
|---|---|---|
| Elasticsearch | http://localhost:9200 | stores everything |
| Kibana | http://localhost:5601 | UI |
| APM Server | http://localhost:8200 | receives OpenTelemetry (OTLP) and writes it to Elasticsearch |

Elasticsearch takes a 1 GB heap; give Docker Desktop at least 4 GB of memory.

To send data, start the API and workers through `scripts/instrumented.py`. It runs them under
`opentelemetry-instrument` with the settings Elastic needs (see the defaults at the top of the file):

```bash
python -m scripts.instrumented football-api -m uvicorn app.main:app --reload
python -m scripts.instrumented football-stats-worker -m workers.stats
python -m scripts.instrumented football-notifications-worker -m workers.notifications
```

What is collected:

- **Traces**: every HTTP request (FastAPI), with child spans for each PostgreSQL query
  (SQLAlchemy), MongoDB command, Redis command and Kafka send/receive. The trace context
  travels in the Kafka message headers, so a `POST /matches/{id}/events` and the worker that
  handles the goal show up as one connected trace.
- **Logs**: everything the API, uvicorn and the workers log (INFO and above), each line
  tagged with the trace id of the request or message that wrote it. `app/core/logs.py` routes
  all loggers through the root logger, where the exporter is attached.
- **Metrics**: request rate/latency, process CPU and memory, plus two custom counters
  (`app/core/telemetry.py`): `football.match_events.created` (by `event.type`, `published`)
  and `football.worker.messages` (by `group_id`, `outcome`: ok / dead_lettered / unsupported_schema).

Where to look in Kibana:

- **Observability > Applications > Service inventory**: the three services, latency,
  throughput, errors; open a transaction for its trace waterfall and the logs written during it.
- **Observability > Applications > Service map**: API -> PostgreSQL / MongoDB / Redis / Kafka -> workers.
- **Discover**: data view `logs-*` for logs; `metrics-*` for metrics (e.g. `football.worker.messages`).

Without the wrapper (plain `uvicorn`, tests, CI, the production image) the OpenTelemetry API is a
no-op and nothing is exported.

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
│   ├── core/                # config, security (JWT/passwords), auth dependencies, Redis cache, Kafka producer, logging + metrics
│   ├── db/                  # PostgreSQL and MongoDB connections
│   ├── models/              # SQLAlchemy tables
│   └── schemas/             # Pydantic request/response models
├── workers/                 # Kafka consumers (notifications, stats) and their shared retry/DLQ code
├── scripts/                 # seed data, make_admin, instrumented (OpenTelemetry launcher)
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
