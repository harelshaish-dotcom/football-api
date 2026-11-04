# Football API

A FastAPI REST API for managing football teams and players.

## Features
- Create, read, update, delete teams
- Filter teams by league
- Pagination support (limit, offset)
- Postman collection for testing

## Setup (macOS / Linux)

Requires Python 3.12 and Docker.

```bash
git clone https://github.com/harelshaish-dotcom/football-api.git
cd football-api

python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env        # then edit SECRET_KEY

docker compose up -d        # Postgres, MongoDB, Redis, Kafka
alembic upgrade head        # create Postgres tables
python seed.py              # optional: sample data

uvicorn main:app --reload
```

On Windows, activate the venv with `.venv\Scripts\activate` and copy the env file with `copy .env.example .env`.

## Note

```bash
This is a work in progress.
```
