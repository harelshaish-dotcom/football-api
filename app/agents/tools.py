"""Tools the match analyst agent can call. Each tool runs its own DB query —
the LLM never sees or writes SQL, it only sees these functions' results."""

from langchain_core.tools import tool
from sqlalchemy import or_

from app.controllers import teams as teams_ctl
from app.db.postgres import SessionLocal
from app.models import Match, Team


def _find_team(db, team_name: str) -> Team | None:
    return db.query(Team).filter(Team.name.ilike(team_name)).first()


def _finished_matches_query(db, team_id: int):
    return (
        db.query(Match)
        .filter(or_(Match.home_team_id == team_id, Match.away_team_id == team_id))
        .filter(Match.status == "finished")
    )


@tool
def get_season_record(team_name: str) -> dict:
    """Get a team's full-season record: games played, wins, draws, losses,
    goals for, goals against, and goal difference, across all finished
    matches. Use this for questions about how a team's whole season is
    going."""
    db = SessionLocal()
    try:
        team = _find_team(db, team_name)
        if not team:
            return {"error": f"No team found named '{team_name}'"}

        rows = teams_ctl.get_standings(db, team_id=team.id)
        if not rows:
            return {"error": f"No stats found for '{team_name}'"}

        row = rows[0]
        return {k: v for k, v in row.items() if k != "id"}
    finally:
        db.close()


@tool
def get_recent_form(team_name: str, n: int = 5) -> dict:
    """Get a team's most recent finished games, most recent first. Each game
    includes the opponent, score, result (W/D/L), and that game's goal
    difference. Use this for questions about recent form. If the user
    specifies how many recent games they mean (e.g. "last 8 games"), pass
    that number as n; otherwise n defaults to 5."""
    db = SessionLocal()
    try:
        team = _find_team(db, team_name)
        if not team:
            return {"error": f"No team found named '{team_name}'"}

        matches = (
            _finished_matches_query(db, team.id)
            .order_by(Match.kickoff_time.desc())
            .limit(n)
            .all()
        )

        games = []
        for m in matches:
            is_home = m.home_team_id == team.id
            opponent = m.away_team.name if is_home else m.home_team.name
            gf = m.home_score if is_home else m.away_score
            ga = m.away_score if is_home else m.home_score
            result = "W" if gf > ga else "D" if gf == ga else "L"
            games.append(
                {
                    "opponent": opponent,
                    "score": f"{gf}-{ga}",
                    "result": result,
                    "goal_difference": gf - ga,
                    "kickoff_time": m.kickoff_time.isoformat(),
                }
            )

        return {"team": team.name, "games": games}
    finally:
        db.close()
