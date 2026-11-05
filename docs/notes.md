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
- When a goal event is created (`POST /matches/{id}/events` with type="goal"), the API publishes it to Kafka and the **stats worker** rebuilds the whole board from MongoDB (`rebuild_leaderboard()`: aggregate goals per player, write to a temp key, `RENAME` over the live key). Editing or deleting a goal (`PATCH`/`DELETE` on the event, or deleting the match) rebuilds it directly in the API, since those changes aren't published to Kafka.
- Why rebuild instead of `ZINCRBY +1`: an increment can't be undone when a goal is edited or deleted, and a redelivered/republished Kafka message would count twice. A rebuild from Mongo (the source of truth) gives the same result no matter how often it runs. `python -m scripts.rebuild_leaderboard` does the same by hand.
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

# POST /matches/{id}/events: Latency Before/After Moving Work Off the Request Path

## Background

`create_match_event` used to be the only place a goal's side effects happened. Two consumers
(`workers/notifications.py`, `workers/stats.py`) now do that work asynchronously off a Kafka
topic (`match-events`), so the endpoint itself only inserts the event doc into MongoDB and
publishes to Kafka.

**Work moved off the request path:**
- `notify_goal`: Postgres join `Player -> Team -> followers`, then one print per follower
- stats: rebuild the Redis leaderboard from Mongo, then `DEL` on `league_table:{league_id}`
  (at the time of the measurements below this was a `ZINCRBY +1`; see the leaderboard section)

## Methodology

Two measurements, both against the same running server/infra:

1. **Live endpoint** — 20x `POST /matches/1/events` against the real running API
   (`http://127.0.0.1:8000`, not `localhost` — see DNS note below), full HTTP + JWT auth +
   Mongo insert + Kafka publish.
2. **Isolated work cost** — 20x calls, in-process, timing exactly two things:
   - `AFTER`: `events.insert_one(doc)` + `publish("match-events", ...)` — what the request
     handler does today.
   - `extra work`: `notify_goal(event)` + `update_leaderboard(player_id)` (since replaced by
     `rebuild_leaderboard()`) +
     `delete_cached(f"league_table:{league_id}")` — the work the workers do now, timed as if
     it still ran inline.
   - `BEFORE` = `AFTER` + `extra work`, i.e. the latency the endpoint would have if this logic
     had never been moved to background consumers.

The isolated measurement exists because the live endpoint's absolute number is dominated by
constant HTTP/JWT overhead that's identical whether or not the Kafka offload exists — it can't
by itself show what the offload bought us. Diffing `AFTER` vs `BEFORE` at the code level isolates
that variable.

## Results

| Measurement | mean | median | p95 |
|---|---|---|---|
| Live endpoint today (HTTP + auth + Mongo + publish) | 19.56ms | 18.57ms | 30.33ms |
| `AFTER` — Mongo insert + Kafka publish only | 6.15ms | 3.33ms | 10.91ms |
| extra work — notify + leaderboard + cache invalidate | 16.46ms | 6.26ms | 8.28ms |
| `BEFORE` — same work done inline (no offload) | 22.61ms | 9.57ms | 17.37ms |

**Takeaway:** moving the notification/stats work off the request path roughly halves-to-thirds
the endpoint's own processing cost (`AFTER` vs `BEFORE`, code-level: ~6ms vs ~23ms mean). The
gap would widen a lot further under load or with more followers per team, since `notify_goal`'s
cost scales with follower count and runs once per goal event no matter how many workers exist,
whereas `publish()` is a fixed, small cost regardless of how much work happens downstream.

**DNS note:** hitting the API via `http://localhost:8000` on this machine adds a flat ~2000ms to
every request, including `/auth/login` and unauthenticated `GET /matches` — confirmed with
`127.0.0.1` (47ms) vs `localhost` (2042ms) for the identical `GET /matches` request. This is a
local Windows hostname-resolution artifact (IPv6 lookup timing out before IPv4 fallback), not
applicable to app code; benchmarks above use `127.0.0.1` to avoid it.

## Testing

```bash
# Live endpoint (repeat N times, record wall-clock per request)
TOKEN=$(curl -s -X POST http://127.0.0.1:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"harelshaish@gmail.com","password":"examplepass"}' | jq -r .access_token)

curl -s -X POST http://127.0.0.1:8000/matches/1/events \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"minute":10,"type":"goal","player":{"id":1,"name":"Cristiano Ronaldo"}}' \
  -w '\n%{time_total}s\n'
```

# Kafka Consumer Groups: Fan-out, Partitions, and Dead-Letter Queue

## Fan-out (different consumer groups)

`workers/notifications.py` (group `notifications`) and `workers/stats.py` (group `stats`) both
subscribe to `match-events`. Because they use different `group_id`s, Kafka delivers every
message to both groups independently — publishing one goal event produced a `processed:*` dedup
marker in Redis for *both* groups from the same `event_id`, confirming each got its own copy.

## Partition rebalancing (same consumer group)

`match-events` was widened from 1 to 3 partitions (`kafka-topics.sh --alter --partitions 3`).
Running two instances of `workers/notifications.py` with the same `group_id`:

- Instance A alone: assigned `[0, 1, 2]`
- Instance B joins: rebalance fires, A keeps `[0, 2]`, B gets `[1]`
- Instance B is killed: rebalance fires again, A is reassigned `[0, 1, 2]`

Each instance only ever consumed messages from partitions it was assigned. This is logged via an
`aiokafka.abc.ConsumerRebalanceListener` (`on_partitions_assigned`/`on_partitions_revoked`) added
to `workers/notifications.py`, tagged with the process's pid so multiple local instances are
distinguishable in the logs.

## Dead-letter queue

Both workers now retry a failing message up to 3 times (with a small backoff), then publish it
to `match-events-dlq` — with the original payload, the error, the group, and attempt count — and
commit the offset anyway, so a permanently-failing ("poison") message can't stall the partition.
Verified with a malformed event (missing `event_id`, which both handlers require for the SET NX
dedup check): 3 failed attempts were logged, the message landed on `match-events-dlq`, and the
next (valid) message on the same partition was processed immediately afterward — the offset
advanced past the poison message instead of stalling on it.

### Dedup and retries: mark processed only after success

The first version claimed the event (`SET processed:{group}:{event_id} NX`) *before* doing the
work. That broke retries: when attempt 1 raised, attempt 2 found the key, logged "duplicate",
and returned normally, so the message counted as handled, never reached the DLQ, and its offset
was committed. The goal was silently lost.

Now each handler checks `is_processed()` first, does the work, and only then calls
`mark_processed()`. A failure (or a crash) leaves no mark, so the retry / redelivery does the
work. Trade-off: a crash in the gap between "work done" and "mark written" runs the work twice
(at-least-once). That is harmless for stats (the rebuild is idempotent) and means a rare
duplicate alert for notifications. The alternative, claim first and `DEL` on failure, avoids
that, but a hard crash (no `except` runs) leaves the claim behind and the redelivery is skipped:
the message would be lost instead of repeated.

### When the DLQ itself fails

The DLQ is written with `send()`, which raises if Kafka doesn't ack. The exception stops the
worker *before* `consumer.commit()`, so the message is redelivered on restart. Catching it and
moving on would be wrong: committing the next message's offset implicitly commits past this one.

## Topics, startup and the outbox

- **Topics**: `ensure_topics()` (`app/core/events.py`, AIOKafkaAdminClient) creates
  `match-events` and `match-events-dlq` with 3 partitions at API and worker startup if they
  don't exist. Otherwise the first publish auto-creates them with the broker default of 1
  partition. Existing topics are left as they are.
- **API startup**: if Kafka is unreachable the API logs a warning and starts without a producer
  instead of refusing to start. `send()` then raises "producer is not started".
- **Outbox**: `POST /matches/{id}/events` saves the event with `published: false`, publishes,
  and flips it to `true` once Kafka acks. If Kafka is down the request still returns 201 (the
  event is saved). `python -m scripts.republish_events` sends everything still `false`; the
  workers dedupe by `event_id`, so a resend is safe.
- **Blocking calls**: the workers' Postgres lookups (`notify_goal`, `get_league_id`) are
  synchronous SQLAlchemy, so they run via `asyncio.to_thread` to keep the event loop free.

## Worker loop: batches, versions, shutdown

- **Batch commits**: `run_consumer` reads up to 100 messages with `getmany()` and commits once
  per batch, per partition, the offset after the last message that was handled or
  dead-lettered. If one message can't even be dead-lettered, the messages before it are
  committed and it and everything after it are redelivered; already-handled ones are then
  skipped by `is_processed()`.
- **Schema version**: match-event messages carry `"schema_version": 1`. A worker that gets a
  version it doesn't know sends the message straight to the DLQ (no retries) instead of
  guessing. Messages without the field (from before versioning) count as version 1.
- **Graceful shutdown**: Ctrl+C / SIGTERM lets the current message finish, commits it, and
  stops ("stopped cleanly"). Unhandled messages in the batch are redelivered next time.
  A second Ctrl+C quits immediately.
- **Kafka storage**: `docker-compose.yml` sets `KAFKA_LOG_DIRS=/var/lib/kafka/data` on a named
  volume (`kafkadata`), so topics, messages and committed offsets survive re-creating the
  container. Before this the broker wrote to `/tmp/kafka-logs` inside the container.

# What Should Not Be Async

**`hash_password` / `verify_password`** (`core/security.py`, wrapping `bcrypt.hashpw` /
`bcrypt.checkpw`) should not be `async def`.

**Why:** `async`/`await` only helps with I/O-bound work — a coroutine that's *waiting* on a
socket, a disk, or another process can yield control back to the event loop so it can go serve
other requests in the meantime. bcrypt hashing isn't waiting on anything; it's pure CPU-bound
computation, and its slowness is the entire point (an adaptive work factor that deliberately
costs tens-to-hundreds of milliseconds per call, so brute-forcing a leaked hash is expensive).
If `hash_password` were declared `async def` and just called `bcrypt.hashpw` directly inside it,
`await`ing it wouldn't offload the work anywhere — it would run synchronously on the single event
loop thread for its full duration, and every other coroutine on that worker (every other
in-flight request) would stall until it finished. Under load, one `/auth/register` call would
pause the entire process, not just that request.

In this codebase: `register` in `routes/auth.py` is a plain `def`. FastAPI runs sync
path-operation functions in a threadpool automatically, so the blocking bcrypt call ties up one
thread-pool worker, not the event loop — concurrent requests on other routes keep flowing.
`login` and `/auth/token` had to become `async def` (they `await` the Redis rate limiter), so
they explicitly offload the check with `await asyncio.to_thread(auth_ctl.authenticate, ...)`.
Making a route `async def` *without* that offload would be a regression (this actually happened
once): every login would freeze the whole API for the length of one bcrypt check.

The general rule this illustrates: reach for `async` for I/O-bound waiting (DB queries, Kafka
publish/consume, Redis, HTTP calls — everything else in this API). For CPU-bound work, the
correct tool is a thread or process pool, not `async def`.

