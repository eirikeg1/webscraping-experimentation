# API Exploration Report: Football Score Sources

## 1. FotMob (Primary)

**Base URL:** `https://www.fotmob.com/api`

### Key Endpoints

- `/matches?date=YYYYMMDD` — daily match schedule
- `/leagues?id={id}` — league details & fixtures (e.g. 47 = Premier League)
- `/matchDetails?matchId={id}` — full match info
- `/allLeagues` — list of all available leagues

### Authentication

All endpoints returned **404 without the `X-Fm-Req` header**. This is a custom auth token that must be generated per-request:

- Base64-encoded JSON containing the endpoint URL, a timestamp, and an MD5 signature
- The signature uses a known secret string (reverse-engineered from their JS)
- Several Python wrappers handle this automatically: `fotmob-api`, `pyfotmob`, `fotmoby`

### Anti-bot

CORS restricted (backend requests only). No observed rate-limit headers, but the auth header is the main gatekeeper.

### Verdict

Richest football-specific data, but requires implementing the auth header or using an existing wrapper. Slightly more fragile since the secret could change.

---

## 2. ESPN FC (Fallback #1)

**Base URL:** `https://site.api.espn.com/apis/site/v2/sports/soccer/{league}/scoreboard`

### Key Endpoints

- `/scoreboard` — current matches for a league
- `/scoreboard?dates=YYYYMMDD` — matches for a specific date
- `/teams` — all teams in a league

### League Codes

`eng.1`, `esp.1`, `ger.1`, `ita.1`, `fra.1`, `uefa.champions`

### Authentication

**None.** Fully public, CORS enabled (`Access-Control-Allow-Origin: *`).

### Cache

`max-age=2` to `max-age=8` — extremely fresh data, ideal for live scores.

### Live Match Data Structure

- `status.type.state`: `"pre"`, `"live"`, `"post"`
- `status.displayClock`: human-readable match time (e.g. `"45'+10'"`)
- `competitors[].score`: current score as string
- `details[]`: play-by-play events (goals, cards) with minute and player info

### Rate Limiting

None observed. No `X-RateLimit` headers.

### Verdict

Best fallback source by far. No auth, no anti-bot, rich data, 2-8 second cache freshness. Only downside: you need to query per-league (no single "all matches" endpoint).

---

## 3. SofaScore (Fallback #2)

**Base URL:** `https://api.sofascore.com/api/v1`

### Key Endpoints

- `/sport/football/events/live` — all live matches across all leagues
- `/sport/football/scheduled-events/YYYY-MM-DD` — all matches for a date
- `/event/{id}` — full event details (venue, managers, etc.)
- `/event/{id}/incidents` — goals, cards, substitutions with coordinates
- `/event/{id}/statistics` — possession, shots, passes broken down by period
- `/search/all?q={query}` — search teams/players/tournaments

### Authentication

**None.** CORS enabled, no API keys needed.

### Cache

`max-age=5` on live events, `max-age=10` on scheduled — good for polling.

### Live Match Data Structure

- `status.code`: 6 = 1st half, 7 = 2nd half, 8 = finished
- `homeScore.current` / `awayScore.current`: integer scores
- `homeScore.period1`, `.period2`: scores by half
- `changes.changeTimestamp`: when data last updated
- `time.currentPeriodStartTimestamp`: for calculating match clock

### Rate Limiting

None observed, but Cloudflare is present.

### Verdict

Excellent. The `/events/live` endpoint is uniquely valuable — one call gets ALL live matches across all leagues. Richest incident data (goal coordinates, body part). No auth barrier.

---

## Comparison Matrix

| Feature | FotMob | ESPN | SofaScore |
|---|---|---|---|
| Auth required | Yes (`X-Fm-Req`) | No | No |
| All-leagues-in-one-call | Yes | No (per-league) | Yes |
| Live score freshness | Unknown | 2-8s cache | 5s cache |
| Play-by-play events | Yes | Yes | Yes (richest) |
| Anti-bot risk | Medium | Low | Low-Medium |
| Python wrappers | Several | None needed | None needed |
| Stability risk | Auth could change | Very stable (public API) | Moderate |

---

## Recommendation

**Primary:** FotMob (best football-specific data, existing Python wrappers handle auth)

**Fallback #1:** ESPN (zero auth, rock solid, 2s cache)

**Fallback #2:** SofaScore (zero auth, single endpoint for all live matches, richest event detail)

The failover logic should be simple: if FotMob's auth breaks or starts returning errors, fall through to ESPN, then SofaScore. ESPN and SofaScore are almost interchangeable in reliability, but ESPN's simpler response structure makes it easier to parse.
