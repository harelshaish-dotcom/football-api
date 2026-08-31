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

# Caching Implementation

## GET /leagues/{id}/table (5-minute TTL)

**Cold Start (Cache Miss):**
- Full query computation required
- Response includes `_cache: "MISS"` and `_timing_ms` (query duration)
- Result cached for 5 minutes (300 seconds)

**Cached (Cache Hit):**
- Instant retrieval from Redis
- Response includes `_cache: "HIT"` and `_timing_ms` (from initial cold request)
- Typical improvement: 100x+ faster

**Testing:**
```bash
# First request (cache miss)
curl http://localhost:8000/leagues/1/table

# Subsequent requests within 5 minutes (cache hit)
curl http://localhost:8000/leagues/1/table

# Cache expires after 5 minutes
```

## GET /teams/{id} (60-second TTL)

**Cold Start (Cache Miss):**
- Database query required
- Response includes `_cache: "MISS"` and `_timing_ms`
- Result cached for 60 seconds

**Cached (Cache Hit):**
- Instant retrieval from Redis
- Response includes `_cache: "HIT"` and `_timing_ms` (from initial cold request)

**Cache Invalidation:**
- PATCH /teams/{id}: Invalidates cache immediately
- DELETE /teams/{id}: Invalidates cache immediately
- New requests after invalidation trigger fresh database queries

**Testing:**
```bash
# 1. First GET (cache miss)
curl http://localhost:8000/teams/1

# 2. Subsequent GET (cache hit)
curl http://localhost:8000/teams/1

# 3. Update team (invalidates cache)
curl -X PATCH http://localhost:8000/teams/1 \
  -H "Content-Type: application/json" \
  -d '{"name":"Updated Team"}' \
  -H "Authorization: Bearer $ADMIN_TOKEN"

# 4. Next GET (cache miss - fresh from DB)
curl http://localhost:8000/teams/1
```

## Performance Baseline

To measure performance differences, compare `_timing_ms` values:
- **Cold request**: Database query time (~10-50ms typically)
- **Cached request**: ~0-1ms (sub-millisecond)
- **Improvement factor**: 10-50x or more

## Cache Implementation Details

- Redis backend: `redis://localhost:6379`
- Cache format: JSON serialized
- TTL enforcement: Redis native expiry
- Pattern invalidation available for bulk deletes

## GET /teams with Pagination Caching (5-minute TTL)

**Cached endpoint:** `GET /teams?league_id={league_id}&limit={limit}&offset={offset}`

**Cache key includes:**
- `league_id`: Filter by league (optional)
- `limit`: Number of results (1-100, default 20)
- `offset`: Pagination offset (default 0)

**Cold Start (Cache Miss):**
- Queries database with specified filters
- Applies limit and offset for pagination
- Response includes `_cache: "MISS"` and `_timing_ms`
- Result cached for 5 minutes (300 seconds)

**Cached (Cache Hit):**
- Instant retrieval from Redis
- Response includes `_cache: "HIT"` and `_timing_ms`

**Key Feature:** Each pagination combination has its own cache key. Page 1 and page 2 return different data and are cached separately.

**Testing:**
```bash
# Page 1 - first request (cache miss)
curl "http://localhost:8000/teams/?league_id=1&limit=5&offset=0"

# Page 1 - second request (cache hit)
curl "http://localhost:8000/teams/?league_id=1&limit=5&offset=0"

# Page 2 - first request (different cache key, cache miss)
curl "http://localhost:8000/teams/?league_id=1&limit=5&offset=5"

# Page 2 - second request (cache hit)
curl "http://localhost:8000/teams/?league_id=1&limit=5&offset=5"
```

**Response Structure:**
```json
{
  "teams": [
    {"id": 1, "name": "Team A", "player_count": 5},
    {"id": 2, "name": "Team B", "player_count": 3}
  ],
  "total": 10,
  "limit": 5,
  "offset": 0,
  "_cache": "HIT",
  "_timing_ms": 2.5
}
```

## Rate Limiting on POST /auth/login

**Rate limit:** 5 login attempts per minute per IP address

**Implementation:**
- Tracks attempts per client IP in Redis
- Increments counter for each login request
- Resets counter after 60 seconds of inactivity

**When limit exceeded:**
- Returns `429 Too Many Requests` status
- Includes `Retry-After` header with seconds to wait
- Error message: "Too many login attempts. Please try again later."

**Testing:**
```bash
# Make 6 rapid login attempts
for i in {1..6}; do
  echo "Attempt $i:"
  curl -X POST http://localhost:8000/auth/login \
    -H "Content-Type: application/json" \
    -d '{"email":"test@example.com","password":"wrong"}' \
    -i  # Show headers including Retry-After
  echo ""
  sleep 0.1
done
```

**Expected behavior:**
- Attempts 1-5: `401 Unauthorized` (invalid credentials)
- Attempt 6: `429 Too Many Requests` with `Retry-After: ~60` header
- After 60 seconds: Counter resets, new attempts allowed

**Response on rate limit:**
```json
{
  "detail": "Too many login attempts. Please try again later."
}
```

Header: `Retry-After: 59` (approximate seconds remaining in rate limit window)

**Benefit:** Protects against brute force attacks on login endpoint

## Live Top-Scorers Leaderboard (Redis Sorted Set)

**Implementation:** Redis sorted set with player goals as scores

**How it works:**
- When a goal event is created (`POST /matches/{id}/events` with type="goal"), the player's score is incremented using ZINCRBY
- Leaderboard key format: `leaderboard:season:{season_id}`
- Member format: `player:{player_id}`

**Endpoints:**

### GET /stats/live-scorers (Fast - Redis)
```
GET /stats/live-scorers?season=1&limit=10
```

**Response:**
```json
{
  "scorers": [
    {"player_id": 5, "goals": 15, "rank": 1},
    {"player_id": 3, "goals": 12, "rank": 2},
    {"player_id": 8, "goals": 10, "rank": 3}
  ],
  "season": 1,
  "limit": 10,
  "_timing_ms": 0.8,
  "_source": "Redis (ZREVRANGE - sorted set)"
}
```

**Performance:** Typically **< 1ms** (sub-millisecond)

### GET /stats/top-scorers (Slow - MongoDB)
```
GET /stats/top-scorers?limit=10
```

**Response:**
```json
{
  "scorers": [
    {"player_id": 5, "player_name": "Harry Kane", "goals": 15},
    {"player_id": 3, "player_name": "Robert Lewandowski", "goals": 12}
  ],
  "_timing_ms": 45.2,
  "_source": "MongoDB (Aggregation Pipeline)"
}
```

**Performance:** Typically **40-100ms** (aggregation pipeline)

**Latency Comparison:**
- Redis ZREVRANGE: ~0.5-2ms
- MongoDB aggregation: ~40-100ms
- **Improvement:** 20-100x faster with Redis

**Testing:**
```bash
# Create a goal event
curl -X POST http://localhost:8000/matches/1/events \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "minute": 45,
    "type": "goal",
    "player": {"id": 5, "name": "Harry Kane"},
    "detail": {"assist": "John Smith"},
    "tags": ["open_play"]
  }'

# Check live leaderboard (should show player 5 with 1 goal)
curl http://localhost:8000/stats/live-scorers?limit=10

# Check MongoDB version (for comparison)
curl http://localhost:8000/stats/top-scorers?limit=10
```

## Real Logout with Token Blocklist

**Implementation:** JWT token blocklist in Redis

**Token Claims Update:**
- Added `jti` (JWT ID) - unique identifier for each token
- Generated as UUID4 string
- Used to track logged-out tokens

**How it works:**
1. User logs in → JWT includes `jti` claim
2. User calls logout → `jti` added to Redis blocklist with TTL = token's remaining lifetime
3. User tries to use token after logout → `get_current_user` checks blocklist, request rejected
4. Token expires → Redis automatically removes from blocklist (TTL expires)

**Endpoints:**

### POST /auth/logout
```
POST /auth/logout
Authorization: Bearer <access_token>
```

**Response (Success):**
```json
{
  "detail": "Successfully logged out"
}
```

**Response (No token):**
```json
{
  "detail": "Missing or invalid token"
}
```

**How blocklist works:**
- Redis key: `blocklist:jti:{jti_value}`
- TTL: Set to token's remaining lifetime
- Check: All authenticated requests check if token's jti is in blocklist
- Cleanup: Automatic when Redis TTL expires

**Testing:**
```bash
# 1. Login
TOKEN=$(curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"user@example.com","password":"password"}' \
  | jq -r '.access_token')

# 2. Verify token works (should return user data)
curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/users/me

# 3. Logout (add token to blocklist)
curl -X POST http://localhost:8000/auth/logout \
  -H "Authorization: Bearer $TOKEN"

# 4. Try to use token after logout (should fail with 401)
curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/users/me
# Response: {"detail": "Could not validate credentials"}
```

**Key Features:**
- Immediate logout (no need to wait for token expiry)
- TTL-based cleanup (no manual blocklist management)
- Works across all API endpoints
- Secure: Token invalid immediately after logout