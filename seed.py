from database.postgres import engine, SessionLocal
from models.league import League
from models.team import Team
from models.players import Player
from database.postgres import Base
from datetime import datetime
from models.user import User
from core.security import hash_password

db = SessionLocal()

league1 = League(name="Premier League", country="England", date_founded=datetime(1992, 8, 15))
league2 = League(name="La Liga", country="Spain", date_founded=datetime(1929, 2, 10))
league3 = League(name="Bundesliga", country="Germany", date_founded=datetime(1963, 8, 24))

db.add_all([league1, league2, league3])
db.commit()
db.refresh(league1)
db.refresh(league2)
db.refresh(league3)


team1 = Team(name="Manchester City", league_id=league1.id, country="England", stadium="Etihad Stadium", date_founded=datetime(1880, 1, 1))
team2 = Team(name="Chelsea", league_id=league1.id, country="England", stadium="Stamford Bridge", date_founded=datetime(1905, 3, 10))
team3 = Team(name="Tottenham Hotspur", league_id=league1.id, country="England", stadium="Tottenham Hotspur Stadium", date_founded=datetime(1882, 9, 5))
team4 = Team(name="Real Madrid", league_id=league2.id, country="Spain", stadium="Santiago Bernabeu", date_founded=datetime(1902, 3, 6))
team5 = Team(name="Barcelona", league_id=league2.id, country="Spain", stadium="Camp Nou", date_founded=datetime(1899, 11, 29))
team6 = Team(name="Atletico Madrid", league_id=league2.id, country="Spain", stadium="Metropolitano", date_founded=datetime(1903, 4, 26))
team7 = Team(name="Bayern Munich", league_id=league3.id, country="Germany", stadium="Allianz Arena", date_founded=datetime(1900, 2, 27))
team8 = Team(name="Borussia Dortmund", league_id=league3.id, country="Germany", stadium="Signal Iduna Park", date_founded=datetime(1909, 12, 19))
team9 = Team(name="Leverkusen", league_id=league3.id, country="Germany", stadium="BayArena", date_founded=datetime(1904, 7, 1))


db.add_all([team1, team2, team3, team4, team5, team6, team7, team8, team9])
db.commit()
for team in [team1, team2, team3, team4, team5, team6, team7, team8, team9]:
	db.refresh(team)

player1 = Player(name="Cristiano Ronaldo", age=38, position="ST", shirt_number=7, height=187, country="Portugal", value=50000000, team_id=team1.id)
player2 = Player(name="Lionel Messi", age=35, position="ST", shirt_number=10, height=170, country="Argentina", value=40000000, team_id=team2.id)
player3 = Player(name="Ederson", age=30, position="GK", shirt_number=31, height=188, country="Brazil", value=35000000, team_id=team1.id)
player4 = Player(name="Thibaut Courtois", age=31, position="GK", shirt_number=1, height=199, country="Belgium", value=40000000, team_id=team4.id)
player5 = Player(name="Manuel Neuer", age=37, position="GK", shirt_number=1, height=193, country="Germany", value=7000000, team_id=team7.id)
player6 = Player(name="Ruben Dias", age=26, position="CB", shirt_number=3, height=187, country="Portugal", value=80000000, team_id=team1.id)
player7 = Player(name="Antonio Rudiger", age=30, position="CB", shirt_number=22, height=190, country="Germany", value=25000000, team_id=team4.id)
player8 = Player(name="Ronald Araujo", age=24, position="CB", shirt_number=4, height=192, country="Uruguay", value=70000000, team_id=team5.id)
player9 = Player(name="William Saliba", age=22, position="CB", shirt_number=2, height=192, country="France", value=75000000, team_id=team2.id)
player10 = Player(name="Kyle Walker", age=33, position="RB", shirt_number=2, height=183, country="England", value=13000000, team_id=team1.id)
player11 = Player(name="Dani Carvajal", age=31, position="RB", shirt_number=2, height=173, country="Spain", value=10000000, team_id=team4.id)
player12 = Player(name="Alphonso Davies", age=22, position="LB", shirt_number=19, height=183, country="Canada", value=70000000, team_id=team7.id)
player13 = Player(name="Theo Hernandez", age=25, position="LB", shirt_number=19, height=184, country="France", value=55000000, team_id=team6.id)
player14 = Player(name="Rodri", age=27, position="CDM", shirt_number=16, height=191, country="Spain", value=110000000, team_id=team1.id)
player15 = Player(name="Joshua Kimmich", age=28, position="CDM", shirt_number=6, height=177, country="Germany", value=75000000, team_id=team7.id)
player16 = Player(name="Kevin De Bruyne", age=32, position="CM", shirt_number=17, height=181, country="Belgium", value=60000000, team_id=team1.id)
player17 = Player(name="Luka Modric", age=37, position="CM", shirt_number=10, height=172, country="Croatia", value=10000000, team_id=team4.id)
player18 = Player(name="Jude Bellingham", age=20, position="CM", shirt_number=5, height=186, country="England", value=120000000, team_id=team4.id)
player19 = Player(name="Pedri", age=20, position="CM", shirt_number=8, height=174, country="Spain", value=90000000, team_id=team5.id)
player20 = Player(name="Phil Foden", age=23, position="CAM", shirt_number=47, height=171, country="England", value=110000000, team_id=team1.id)
player21 = Player(name="Jamal Musiala", age=20, position="CAM", shirt_number=42, height=184, country="Germany", value=110000000, team_id=team7.id)
player22 = Player(name="Harry Kane", age=30, position="ST", shirt_number=9, height=188, country="England", value=90000000, team_id=team7.id)
player23 = Player(name="Erling Haaland", age=23, position="ST", shirt_number=9, height=195, country="Norway", value=180000000, team_id=team1.id)
player24 = Player(name="Vinicius Junior", age=23, position="LW", shirt_number=7, height=176, country="Brazil", value=150000000, team_id=team4.id)
player25 = Player(name="Robert Lewandowski", age=35, position="ST", shirt_number=9, height=185, country="Poland", value=30000000, team_id=team5.id)
player26 = Player(name="Bukayo Saka", age=22, position="RW", shirt_number=7, height=178, country="England", value=120000000, team_id=team2.id)
player27 = Player(name="Antoine Griezmann", age=32, position="CF", shirt_number=7, height=176, country="France", value=25000000, team_id=team6.id)

db.add_all([
	player1, player2, player3, player4, player5, player6, player7, player8,
	player9, player10, player11, player12, player13, player14, player15,
	player16, player17, player18, player19, player20, player21, player22,
	player23, player24, player25, player26, player27,
])
db.commit()

admin_user = User(
    email="admin@example.com",
    hashed_password=hash_password("password123"),
    is_admin=True,
    is_active=True
)
db.add(admin_user)
db.commit()

db.close()