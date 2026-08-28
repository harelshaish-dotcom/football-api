from fastapi import FastAPI
from database.connection import Base, engine
from models import league, players, team, user
from routes import auth, leagues, players as players_routes, teams, users

app = FastAPI(title="Football API", version="0.2.0")

app.include_router(teams.router)
app.include_router(users.router)
app.include_router(players_routes.router)
app.include_router(leagues.router)
app.include_router(auth.router)