from fastapi import FastAPI
from database.connection import Base, engine
from models import team as _team          # import so the table is registered
from routes import teams

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Football API", version="0.2.0")
app.include_router(teams.router)