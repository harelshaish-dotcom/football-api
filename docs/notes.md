# Authentication Notes

## JWT Payload

The access token contains:

- `sub`: the user's database ID, serialized as a string
- `admin`: whether the user has administrator privileges
- `iat`: the UTC time when the token was issued
- `exp`: the UTC time when the token expires

The password and password hash must never be included in a JWT. Tokens are readable by their bearer, so putting a password there would expose a credential to anyone who obtains the token. The server only needs the user ID and authorization claims; it checks the current user and active status against the database.

## Expiration Check

For a short-lived token test, temporarily set `ACCESS_TOKEN_MINUTES = 1` in `core/security.py`, restart the API, log in, wait at least 70 seconds, and call `/users/me` with the token:

```bash
curl -H "Authorization: Bearer $TOKEN" http://localhost:8000/users/me
```

The response should be `401 Unauthorized` because `decode_token()` rejects expired JWTs. Restore `ACCESS_TOKEN_MINUTES = 30` afterward and restart the API.

## Creating the First Admin

Register a user, then promote that account by email:

```bash
./venv/bin/python make_admin.py user@example.com
```

# N+1 Query Optimization

## GET /teams endpoint

**Before selectinload:**
- 11 queries (1 count + 1 teams + 9 player queries)
- Slow ❌

**After selectinload:**
- 2 queries (1 teams + 1 players IN query)
- Fast ✓

**Implementation:**
```python
from sqlalchemy.orm import selectinload

teams = db.query(Team).options(selectinload(Team.players)).all()
```

# New Endpoints

## GET /stats/top-scorers

Returns top 10 players by goals scored, with optional league_id filter.

**Endpoint:** `GET /stats/top-scorers?league_id={optional}&limit={1-100}`

**Implementation:** Uses MongoDB aggregation pipeline to:
1. Filter events where `type: "goal"`
2. Group by `player.id` and count occurrences
3. Sort by goal count descending
4. Limit to top N scorers

**Example Response:**
```json
[
  {
    "player_id": 23,
    "player_name": "Erling Haaland",
    "goals": 47
  },
  {
    "player_id": 24,
    "player_name": "Vinicius Junior",
    "goals": 42
  }
]
```

## GET /matches/{id}/timeline

Combines data from both databases in one response:
- **From PostgreSQL:** Match details (team names, IDs, kickoff time, status, scores)
- **From MongoDB:** All events for the match in chronological order

**Endpoint:** `GET /matches/{id}/timeline`

**Example Response:**
```json
{
  "match": {
    "id": 1,
    "home_team": {
      "id": 1,
      "name": "Manchester City"
    },
    "away_team": {
      "id": 4,
      "name": "Real Madrid"
    },
    "kickoff_time": "2024-01-15T15:00:00",
    "status": "finished",
    "home_score": 3,
    "away_score": 2
  },
  "events": [
    {
      "id": "507f1f77bcf86cd799439011",
      "minute": 12,
      "type": "goal",
      "player": {"id": 23, "name": "Erling Haaland"},
      "detail": {...}
    }
  ]
}
```

# Database Design Rationale

## Why Events Go to MongoDB and Teams Don't

**Events in MongoDB:**
- **High Volume:** Events accumulate rapidly (multiple per match × thousands of matches)
- **Frequent Writes:** New events are created constantly during live matches
- **Flexible Schema:** Event details vary by type (substitution vs card vs goal)
- **Loose Consistency:** Eventual consistency acceptable (match not updated in real-time)
- **Scalability:** MongoDB handles writes/reads at high scale without locking

**Teams in PostgreSQL:**
- **Low Volume:** Static team data
- **ACID Requirements:** Team updates need transactional consistency
- **Relational Structure:** Teams have strict relationships (leagues, players, stadiums)
- **Reference Integrity:** Foreign key constraints ensure data consistency
- **Query Patterns:** Teams are frequently joined with other entities

## Painful Query with Current Design

**Query:** *"Get all events for every team in a specific league, ordered by match date and minute"*

This is painful because:
1. **Requires Cross-Database Logic:** Must fetch leagues → teams → matches from PostgreSQL, then look up events in MongoDB
2. **No Single Join:** SQL joins can't cross to MongoDB, requiring application-level iteration
3. **N+1 Problem:** For each match, a separate MongoDB query is needed
4. **Inefficient Filtering:** Can't push the league_id filter into MongoDB's aggregation pipeline

**Pseudo-code of what's required:**
```python
league = db.query(League).get(league_id)
matches = db.query(Match).filter(
    (Match.home_team.league_id == league_id) | 
    (Match.away_team.league_id == league_id)
).all()

for match in matches:
    # N MongoDB queries!
    events = mongo_events.find({"match_id": match.id}).sort("minute", 1)
```

A better design would require: either storing league_id denormalized in MongoDB events, or using a database that supports cross-table queries (PostgreSQL with JSONB + event logs, or a GraphQL layer).

# Event Query Performance Testing

Run `python seed_events_timing.py` to:
1. Insert 500 test events for a match
2. Query the endpoint before creating an index
3. Create an index on (match_id, minute)
4. Query the endpoint after creating the index
5. Log timing results below

Results will be automatically appended to this section.


**Benefit:** Loads all players in ONE query with IN clause instead of N separate queries.

match events:

{
  "match_id": 209,
  "minute": 67,
  "type": "goal",
  "player": {"id": 9, "name": "Kylian Mbappe"},
  "detail": {"assist_by": "Vinicius Jr", "body_part": "right foot", "situation": "open play", "xg": 0.35}
}

{
  "match_id": 201,
  "minute": 28,
  "type": "card",
  "player": {"id": 5, "name": "Sergio Ramos"},
  "detail": {"card_type": "yellow", "reason": "tackle"}
}

{
  "match_id": 190,
  "minute": 57,
  "type": "substitution",
  "player": {"id": 10, "name": "Vini Jr"},
  "detail": {"player_out": {"id": 9, "name": "Kylian Mbappe"}}
}

{
  "match_id": 267,
  "minute": 96,
  "type": "var",
  "player": {"id": 9, "name": "Kylian Mbappe"},
  "detail": {"decision": "goal_cancellation", "reason": "offside", "reviewed_minute": 98}
}

admin: 
harelshaish@gmail.com
examplepass