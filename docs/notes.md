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