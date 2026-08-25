```mermaid
erDiagram

    LEAGUES {
        int league_id PK
        string name
        string country
        date date_founded
    }

    TEAMS {
        int team_id PK
        string name
        string country
        string stadium
        date date_founded
        int league_id FK
    }

    PLAYERS {
        int player_id PK
        string name
        enum position
        int shirt_number
        int height
        string country
        int value
        date date_of_birth
        int team_id FK
    }

    MATCHES {
        int match_id PK
        int league_id FK
        string season
        int matchday
        datetime match_date
        int home_team_id FK
        int away_team_id FK
        int home_score
        int away_score
        enum status
    }

    PLAYER_TRANSFERS {
        int transfer_id PK
        int player_id FK
        int team_id FK
        date start_date
        date end_date
        int transfer_fee
    }

    PLAYER_MATCH_STATS {
        int match_stat_id PK
        int player_id FK
        int match_id FK
        int team_id FK
        int minutes_played
        int goals
        int assists
        int yellow_cards
        int red_cards
        decimal rating
        boolean is_starter
    }

    LEAGUE_STANDING {
        int standing_id PK
        int league_id FK
        int team_id FK
        string season
        int played
        int won
        int drawn
        int lost
        int goals_for
        int goals_against
        int goals_difference
        int points
    }

    PLAYER_SEASON_STATS {
        int stat_id PK
        int player_id FK
        int league_id FK
        string season
        int apps
        int minutes_played
        int goals
        int assists
        int yellow_cards
        int red_cards
        decimal avg_rating
    }

    LEAGUES ||--o{ MATCHES : "hosts"
    LEAGUES ||--o{ LEAGUE_STANDING : "ranks"
    LEAGUES ||--o{ PLAYER_SEASON_STATS : "tracks"

    TEAMS ||--o{ PLAYER_TRANSFERS : "contracts"
    TEAMS ||--o{ LEAGUE_STANDING : "competes_in"
    TEAMS ||--o{ MATCHES : "plays_home"
    TEAMS ||--o{ MATCHES : "plays_away"

    PLAYERS ||--o{ PLAYER_TRANSFERS : "belongs_to"
    PLAYERS ||--o{ PLAYER_MATCH_STATS : "appears_in"
    PLAYERS ||--o{ PLAYER_SEASON_STATS : "records"

    MATCHES ||--o{ PLAYER_MATCH_STATS : "includes"
```


| Method | Path | Description | Auth | Success | Error |
|--------|------|-------------|------|---------|-------|
| POST | `/auth/register` | Create new user account | No | 201 | 400, 409 |
| POST | `/auth/login` | Login to the system | No | 200 | 400, 401 |
| POST | `/teams` | Creates new team | Yes | 201 | 400, 403, 409 |
| POST | `/teams/{id}/players` | Add player to the team | Yes | 201 | 400, 403, 404, 409 |
| POST | `/players/{id}/player_season_stats` | Add player stats | Yes | 201 | 400, 403, 404 |
| GET | `/teams/{id}/players` | Get every player on a team | No | 200 | 404 |
| GET | `/players/{id}/player_season_stats` | Get player stats | No | 200 | 404 |
| GET | `/players?country=France` | Get every France player | No | 200 | 400 |
| GET | `/users` | Get every user in the DB | Yes | 200 | 401, 403 |
| GET | `/users/{id}/followed_teams` | Get a user's followed teams | Yes | 200 | 401, 403, 404 |
| PUT | `/players/{id}/player_season_stats` | Update player stats | Yes | 200 | 400, 403, 404 |
| PUT | `/teams/{team_id}/league` | Changes a team's league | Yes | 200 | 400, 403, 404, 409 |
| PUT | `/teams/{id}` | Update team details | Yes | 200 | 400, 403, 404 |
| PUT | `/players/{id}` | Update player details | Yes | 200 | 400, 403, 404 |
| PUT | `/users/{id}` | Update own user profile | Yes | 200 | 400, 401, 403, 404 |
| DELETE | `/teams/{id}` | Deletes a team | Yes | 204 | 403, 404 |
| DELETE | `/players/{id}` | Deletes a player | Yes | 204 | 403, 404 |
| DELETE | `/teams/{team_id}/players/{player_id}` | Remove player from a team | Yes | 204 | 403, 404 |
| DELETE | `/players/{id}/player_season_stats/{season_id}` | Delete a stats entry | Yes | 204 | 403, 404 |
| DELETE | `/users/{id}/followed_teams/{team_id}` | Unfollow a team | Yes | 204 | 403, 404 |