from dotenv import load_dotenv
load_dotenv()
from fastapi import FastAPI
from database.postgres import Base, engine
from database.mongo import ensure_indexes
from models import league, players, team, user
from routes import auth, leagues, matches as matches_routes, players as players_routes, stats, teams, users
from core.cache import r
from contextlib import asynccontextmanager


@asynccontextmanager
async def lifespan(app: FastAPI):
    await ensure_indexes()
    try:
        await r.ping()
        print("Redis connected")
    except Exception as e:
        print(f"Redis unreachable: {e}")
    yield


app = FastAPI(title="Football API", version="0.2.0", lifespan=lifespan)

app.include_router(stats.router)
app.include_router(teams.router)
app.include_router(users.router)
app.include_router(players_routes.router)
app.include_router(leagues.router)
app.include_router(matches_routes.router)
app.include_router(auth.router)
