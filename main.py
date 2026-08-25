from fastapi import FastAPI, HTTPException, Query, Request
from pydantic import BaseModel, Field
from fastapi.responses import JSONResponse


app = FastAPI(title="Football API")


@app.get("/")
def home():
    return {"message": "Football API is running", "version": "0.1.0"}

class TeamCreate(BaseModel):
    name: str = Field(min_length=2, max_length=60)
    league_id: int
    founded: int | None = Field(None, ge=1850, le=2100)
    stadium: str | None = None

class TeamOut(BaseModel):
    id: int
    name: str = Field(min_length=2, max_length=60)
    league_id: int
    founded: int | None = Field(None, ge=1850, le=2100)
    stadium: str | None = None

class TeamUpdate(BaseModel):
    name: str | None = None
    league_id: int | None = None
    founded: int | None = None
    stadium: str | None = None

TEAMS = {}
team_id_counter = 1

@app.post("/teams", status_code=201, response_model=TeamOut)
def create_team(payload: TeamCreate):
    global team_id_counter
    for team in TEAMS.values():
       if team["name"] == payload.name:
            raise HTTPException(status_code=409, detail="Team already exists")
    new_team = {"id": team_id_counter, **payload.model_dump()}
    TEAMS[team_id_counter] = new_team
    team_id_counter += 1
    return new_team

@app.get("/teams", status_code=200)
def get_all_teams(league_id: int | None = None, limit: int = Query(20, ge=1, le=100), offset: int = Query(0, ge=0)):
    filtered_items = [team for team in TEAMS.values() if league_id is None or team["league_id"] == league_id]
    total = len(filtered_items)
    items = filtered_items[offset:offset+limit]
    return {"items": items, "total": total, "limit": limit, "offset": offset}

@app.get("/teams/top", status_code=200)
def get_top_teams():
    return list(TEAMS.values())
        
@app.get("/teams/{id}", status_code=200)
def get_team(id: int):
    if id not in TEAMS:
        raise HTTPException(status_code=404, detail="Team not found")
    return TEAMS[id]

@app.patch("/teams/{id}", status_code=200)
def update_team(id: int, payload: TeamUpdate):
    if id not in TEAMS:
        raise HTTPException(status_code=404, detail="Team not found")
    team = TEAMS[id]
    if payload.name is not None:
        team["name"] = payload.name
    if payload.league_id is not None:
        team["league_id"] = payload.league_id
    if payload.founded is not None:
        team["founded"] = payload.founded
    if payload.stadium is not None:
        team["stadium"] = payload.stadium
    return team

@app.delete("/teams/{id}", status_code=204)
def delete_team(id: int):
    if id not in TEAMS:
        raise HTTPException(status_code=404, detail="Team not found")
    del(TEAMS[id])

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={"message": "Internal server error", "detail": str(exc)}
    )
