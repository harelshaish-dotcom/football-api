from dotenv import load_dotenv
load_dotenv()
from fastapi import FastAPI
from database.postgres import Base, engine
from database.mongo import ensure_indexes
from models import league, players, team, user
from routes import auth, leagues, players as players_routes, teams, users
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    await ensure_indexes()
    yield

app = FastAPI(title="Football API", version="0.2.0", lifespan=lifespan)

app.include_router(teams.router)
app.include_router(users.router)
app.include_router(players_routes.router)
app.include_router(leagues.router)
app.include_router(auth.router)