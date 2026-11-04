"""Fill an empty database with sample leagues, teams, players and an admin user.

Run once after `alembic upgrade head`:  python -m scripts.seed
Admin login: admin@example.com / password123
"""

from datetime import datetime

from app.core.security import hash_password
from app.db.postgres import SessionLocal
from app.models.league import League
from app.models.player import Player
from app.models.team import Team
from app.models.user import User

# (name, country, founded)
LEAGUES = [
    ("Premier League", "England", datetime(1992, 8, 15)),
    ("La Liga", "Spain", datetime(1929, 2, 10)),
    ("Bundesliga", "Germany", datetime(1963, 8, 24)),
]

# (name, league, country, stadium, founded)
TEAMS = [
    ("Manchester City", "Premier League", "England", "Etihad Stadium", datetime(1880, 1, 1)),
    ("Chelsea", "Premier League", "England", "Stamford Bridge", datetime(1905, 3, 10)),
    (
        "Tottenham Hotspur",
        "Premier League",
        "England",
        "Tottenham Hotspur Stadium",
        datetime(1882, 9, 5),
    ),
    ("Real Madrid", "La Liga", "Spain", "Santiago Bernabeu", datetime(1902, 3, 6)),
    ("Barcelona", "La Liga", "Spain", "Camp Nou", datetime(1899, 11, 29)),
    ("Atletico Madrid", "La Liga", "Spain", "Metropolitano", datetime(1903, 4, 26)),
    ("Bayern Munich", "Bundesliga", "Germany", "Allianz Arena", datetime(1900, 2, 27)),
    ("Borussia Dortmund", "Bundesliga", "Germany", "Signal Iduna Park", datetime(1909, 12, 19)),
    ("Leverkusen", "Bundesliga", "Germany", "BayArena", datetime(1904, 7, 1)),
]

# (name, age, position, shirt_number, height_cm, country, value_eur, team)
PLAYERS = [
    ("Cristiano Ronaldo", 38, "ST", 7, 187, "Portugal", 50_000_000, "Manchester City"),
    ("Lionel Messi", 35, "ST", 10, 170, "Argentina", 40_000_000, "Chelsea"),
    ("Ederson", 30, "GK", 31, 188, "Brazil", 35_000_000, "Manchester City"),
    ("Thibaut Courtois", 31, "GK", 1, 199, "Belgium", 40_000_000, "Real Madrid"),
    ("Manuel Neuer", 37, "GK", 1, 193, "Germany", 7_000_000, "Bayern Munich"),
    ("Ruben Dias", 26, "CB", 3, 187, "Portugal", 80_000_000, "Manchester City"),
    ("Antonio Rudiger", 30, "CB", 22, 190, "Germany", 25_000_000, "Real Madrid"),
    ("Ronald Araujo", 24, "CB", 4, 192, "Uruguay", 70_000_000, "Barcelona"),
    ("William Saliba", 22, "CB", 2, 192, "France", 75_000_000, "Chelsea"),
    ("Kyle Walker", 33, "RB", 2, 183, "England", 13_000_000, "Manchester City"),
    ("Dani Carvajal", 31, "RB", 2, 173, "Spain", 10_000_000, "Real Madrid"),
    ("Alphonso Davies", 22, "LB", 19, 183, "Canada", 70_000_000, "Bayern Munich"),
    ("Theo Hernandez", 25, "LB", 19, 184, "France", 55_000_000, "Atletico Madrid"),
    ("Rodri", 27, "CDM", 16, 191, "Spain", 110_000_000, "Manchester City"),
    ("Joshua Kimmich", 28, "CDM", 6, 177, "Germany", 75_000_000, "Bayern Munich"),
    ("Kevin De Bruyne", 32, "CM", 17, 181, "Belgium", 60_000_000, "Manchester City"),
    ("Luka Modric", 37, "CM", 10, 172, "Croatia", 10_000_000, "Real Madrid"),
    ("Jude Bellingham", 20, "CM", 5, 186, "England", 120_000_000, "Real Madrid"),
    ("Pedri", 20, "CM", 8, 174, "Spain", 90_000_000, "Barcelona"),
    ("Phil Foden", 23, "CAM", 47, 171, "England", 110_000_000, "Manchester City"),
    ("Jamal Musiala", 20, "CAM", 42, 184, "Germany", 110_000_000, "Bayern Munich"),
    ("Harry Kane", 30, "ST", 9, 188, "England", 90_000_000, "Bayern Munich"),
    ("Erling Haaland", 23, "ST", 9, 195, "Norway", 180_000_000, "Manchester City"),
    ("Vinicius Junior", 23, "LW", 7, 176, "Brazil", 150_000_000, "Real Madrid"),
    ("Robert Lewandowski", 35, "ST", 9, 185, "Poland", 30_000_000, "Barcelona"),
    ("Bukayo Saka", 22, "RW", 7, 178, "England", 120_000_000, "Chelsea"),
    ("Antoine Griezmann", 32, "CF", 7, 176, "France", 25_000_000, "Atletico Madrid"),
]


def main() -> None:
    """Insert the sample data. Fails on unique constraints if run twice."""
    db = SessionLocal()
    try:
        leagues = {
            name: League(name=name, country=country, date_founded=founded)
            for name, country, founded in LEAGUES
        }
        db.add_all(leagues.values())
        db.commit()

        teams = {
            name: Team(
                name=name,
                league_id=leagues[league].id,
                country=country,
                stadium=stadium,
                date_founded=founded,
            )
            for name, league, country, stadium, founded in TEAMS
        }
        db.add_all(teams.values())
        db.commit()

        db.add_all(
            Player(
                name=name,
                age=age,
                position=position,
                shirt_number=shirt_number,
                height=height,
                country=country,
                value=value,
                team_id=teams[team].id,
            )
            for name, age, position, shirt_number, height, country, value, team in PLAYERS
        )
        db.commit()

        db.add(
            User(
                email="admin@example.com",
                hashed_password=hash_password("password123"),
                is_admin=True,
                is_active=True,
            )
        )
        db.commit()
    finally:
        db.close()


if __name__ == "__main__":
    main()
