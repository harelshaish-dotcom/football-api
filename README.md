# Football API

A FastAPI REST API for managing football teams and players.

## Features
- Create, read, update, delete teams
- Filter teams by league
- Pagination support (limit, offset)
- Postman collection for testing

## Setup

```bash
pip install fastapi pydantic uvicorn email-validator
uvicorn main:app --reload --port 8000
```

## API Docs

Visit `http://localhost:8000/docs` for interactive API documentation.
