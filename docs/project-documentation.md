# Live Football Score Tracker — Project Documentation

## 1. Project Overview

A personal project to track live football scores from multiple API sources, with a simple web dashboard for development use. Built with Python, FastAPI, and vanilla JavaScript.

**Run:** `uv run python -m livescores`
**Dashboard:** `http://localhost:8000`
**Tests:** `uv run pytest` (184 tests)

---

## 2. Motivation and Goals

The original idea was to build a system that:
1. Fetches a match schedule for the day
2. When matches start, monitors live score updates
3. Displays everything on a personal dashboard

The key goal was to load live data without constantly refreshing pages — observe changes as they happen rather than polling HTML.

### What we want to track
- **La Liga** and **Premier League** — all matches
- **International Friendlies** — all matches
- **Top teams** (configurable) — tracked across ALL competitions including Champions League, Europa League, FA Cup, Copa del Rey, etc.
- **Data per match:** Live scores, match clock, events (goals, cards, substitutions), and match statistics (possession, shots, corners, fouls)

---

## 3. Key Technical Decisions

### 3.1 Why Python over Rust

Rust is the preferred language for this project's author, but Python was chosen for the scraping layer because:

- **Playwright/browser automation** has first-class Python bindings; the Rust ecosystem for this is immature
- **Anti-bot bypass** libraries are overwhelmingly Python-first
- **Speed doesn't matter** — the bottleneck is network I/O (waiting for API responses), not computation. The process is idle 99% of the time
- **Memory** — the browser itself (Chromium) is the memory hog, not the Python process
- **Iteration speed** — scraping is inherently messy work that benefits from rapid prototyping

Rust would make sense for a downstream component that consumes the data at scale, but not for the scraping layer itself.

### 3.2 Why API polling over browser-based scraping

The original idea was to load a page in a headless browser and watch for DOM mutations. After investigation, we discovered that all target sites (FotMob, ESPN, SofaScore) use REST APIs that their frontends consume. This changed the approach:

| Aspect | API Polling | Browser (Playwright) |
|--------|-------------|---------------------|
| Bot detection risk | **Lower** — looks like app traffic | Higher — headless browser fingerprints |
| Resource usage | **Minimal** — just HTTP requests | Heavy — full Chromium per session |
| Complexity | **Simple** — parse JSON | Complex — DOM selectors, page lifecycle |
| Fragility | API structure changes break it | HTML layout changes break it |
| Data quality | **Structured JSON directly** | Have to extract from HTML |
| Latency | Depends on poll interval (5-10s) | Can be near-instant watching DOM |
| Fallback flexibility | **Easy to swap sources** | Each site needs its own scraper |

The only advantage of Playwright is sub-second latency via DOM mutation observation. For football scores, a 5-10 second delay is completely fine.

**Bot detection specifics:** API polling sends small, predictable HTTP requests that look similar to mobile app traffic. Browser-based scraping leaves a much bigger fingerprint — headless browser detection is an entire industry (canvas fingerprinting, WebGL checks, navigator properties). For a personal project tracking ~20 matches, API polling generates negligible traffic.

### 3.3 Why ESPN as primary source (not FotMob)

FotMob was originally planned as the primary source due to its rich football-specific data. However, API exploration revealed a critical problem:

**FotMob's `X-Fm-Req` authentication header:**
- All FotMob API endpoints return 404 without a custom `X-Fm-Req` header
- The header is a Base64-encoded JSON containing the endpoint URL, a timestamp, and an MD5 signature
- The signature uses a secret string reverse-engineered from FotMob's JavaScript bundle
- This secret has changed in the past, breaking all third-party wrappers
- None of the current Python wrappers (`fotmob-api`, `pyfotmob`, `fotmoby`) reliably implement this header

**Source priority was reordered to:**
1. **ESPN** (primary) — Zero auth, fully public API, CORS enabled, 2-8 second cache freshness
2. **SofaScore** (fallback) — Zero auth, CORS enabled, single endpoint for all live matches
3. **FotMob** (deferred) — Rich data but fragile auth mechanism

### 3.4 The multi-source fallback strategy

Rather than scraping multiple sites simultaneously (which creates a data normalization nightmare), the approach is:
1. Use ESPN as primary for all data
2. Only switch to SofaScore if ESPN fails for a specific match
3. Keep sources behind a common interface for easy swapping

This avoids the complexity of real-time cross-source normalization during normal operation. The correlator maps matches between sources using kickoff time + team name similarity, so the fallback can find the same match on the alternate source.

**Practical example:** ESPN's `fifa.friendly` endpoint has 16 international friendlies but missed Netherlands vs Norway. SofaScore's scheduled events endpoint included it. Having both sources means better coverage.

### 3.5 Dashboard: no framework, dev tool only

The dashboard uses plain HTML + CSS + vanilla JavaScript with WebSocket updates. No React, no Vue, no build step, no node_modules.

Reasoning:
- It's a dev tool, not a product — clean and informative, not polished
- A score dashboard only updates text in cards — no component reactivity needed
- WebSocket pushes from the backend mean scores update in real-time without frontend polling
- Zero build tooling keeps the project simple

---

## 4. Data Source Details

### 4.1 ESPN (Primary)

**API exploration findings:**
- **Base URL:** `https://site.api.espn.com/apis/site/v2/sports/soccer/{league}/scoreboard`
- **Auth:** None required. Fully public, CORS enabled (`Access-Control-Allow-Origin: *`)
- **Cache:** `max-age=2` to `max-age=8` — extremely fresh, ideal for live scores
- **Rate limiting:** None observed (no `X-RateLimit` headers)
- **Query format:** `?dates=YYYYMMDD` for specific dates, per-league queries

**League codes tested and working:**
| Competition | ESPN Code |
|---|---|
| Premier League | `eng.1` |
| La Liga | `esp.1` |
| Champions League | `uefa.champions` |
| Europa League | `uefa.europa` |
| Conference League | `uefa.europa.conf` |
| FA Cup | `eng.fa` |
| Carabao Cup | `eng.league_cup` |
| Copa del Rey | `esp.copa_del_rey` |
| International Friendlies | `fifa.friendly` |

**Response structure:**
- `events[]` — array of matches
- Each event has `competitions[0].competitors[]` with home/away teams, scores, statistics
- `status.type.state`: `"pre"`, `"live"`, `"post"` for match state
- `status.displayClock`: human-readable match time (e.g. `"45'+10'"`)
- `competitions[0].details[]`: play-by-play events with type IDs (70=goal, 94=yellow, 96=red, 98=penalty, 137=header goal, 93=red card)
- `competitors[].statistics[]`: possession, shots, shotsOnTarget, wonCorners, foulsCommitted

**Strengths:** Zero auth, very fresh cache (2-8s), complete match details in single response, rich event data.
**Limitations:** Must query per-league (no all-leagues endpoint), match detail requires league context.

### 4.2 SofaScore (Fallback)

**API exploration findings:**
- **Base URL:** `https://api.sofascore.com/api/v1`
- **Auth:** None required. CORS enabled.
- **Cache:** `max-age=5` on live events, `max-age=10` on scheduled
- **Anti-bot:** Cloudflare present. WebFetch got 403 — requires browser User-Agent header with `curl`/`httpx`
- **Rate limiting:** None observed, but Cloudflare could throttle

**Key endpoints:**
| Endpoint | Purpose |
|---|---|
| `/sport/football/events/live` | ALL live matches across all leagues (233 events in test) |
| `/sport/football/scheduled-events/YYYY-MM-DD` | All matches for a date (181 events in test) |
| `/event/{id}` | Full event details (venue, managers, etc.) |
| `/event/{id}/incidents` | Goals, cards, substitutions with coordinates |
| `/event/{id}/statistics` | Possession, shots, passes by period |
| `/search/all?q={query}` | Search teams/players/tournaments |

**Status codes:**
| Code | Meaning |
|---|---|
| 0 | Not started / Scheduled |
| 6 | 1st half |
| 7 | 2nd half |
| 20 | Started (treated as 1H) |
| 31 | Halftime |
| 70 | Cancelled |
| 80 | Postponed |
| 100 | Ended / Finished |
| 120 | After Penalties (finished) |

**Strengths:** Single endpoint for ALL live matches, richest incident data (goal coordinates, body part), no auth.
**Limitations:** Cloudflare can block basic requests, requires browser-like User-Agent.

### 4.3 FotMob (Deferred)

**API exploration findings:**
- **Base URL:** `https://www.fotmob.com/api`
- **Endpoints:** `/matches?date=YYYYMMDD`, `/leagues?id={id}`, `/matchDetails?matchId={id}`, `/allLeagues`
- **Auth:** ALL endpoints return 404 without `X-Fm-Req` header
- **X-Fm-Req header:** Base64-encoded JSON with URL, timestamp, MD5 signature using a reverse-engineered secret
- **Risk:** The secret has changed before, breaking all third-party wrappers
- **Status:** Deferred indefinitely. ESPN + SofaScore provide complete coverage.

### 4.4 Source Comparison Matrix

| Feature | ESPN | SofaScore | FotMob |
|---|---|---|---|
| Auth required | No | No | Yes (`X-Fm-Req`) |
| All-leagues-in-one-call | No (per-league) | Yes | Yes |
| Live score freshness | 2-8s cache | 5s cache | Unknown |
| Play-by-play events | Yes | Yes (richest) | Yes |
| Anti-bot risk | Low | Low-Medium | Medium |
| Stability risk | Very stable | Moderate | Auth could change |

---

## 5. Architecture

### 5.1 High-Level Data Flow

```
ESPN API ──────┐
               ├──→ PollingEngine ──→ MatchState ──→ WebSocket ──→ Browser Dashboard
SofaScore API ─┘     (5-10s)         (in-memory)    (broadcast)    (live updates)
```

### 5.2 Module Structure

```
src/livescores/
├── main.py                    # Entry point: config, sources, engine, server
├── models.py                  # Pydantic models: Match, Team, MatchEvent, MatchStats, MatchStatus
├── config.py                  # TOML config loading with validation
├── state.py                   # In-memory state store with change detection (MatchDiff)
├── sources/
│   ├── base.py                # Abstract FootballSource interface
│   ├── espn.py                # ESPN API implementation
│   ├── sofascore.py           # SofaScore API implementation
│   ├── correlator.py          # Cross-source match matching
│   └── ids.py                 # League/tournament ID mappings per source
├── polling/
│   ├── scheduler.py           # Active window detection, adaptive poll intervals
│   └── engine.py              # Async polling loop with failover and circuit breaker
├── web/
│   ├── app.py                 # FastAPI app factory
│   ├── routes.py              # REST endpoints + WebSocket handler
│   └── static/                # Dashboard (HTML/CSS/JS)
└── utils/
    ├── http.py                # Shared async httpx client
    └── team_names.py          # Team name normalization + alias matching
```

### 5.3 Polling and Scheduling

The polling system has two layers:

**Schedule awareness (scheduler.py):**
- Active window: 15 minutes before first kickoff → 3 hours after last kickoff
- Outside the window, checks every 5 minutes for new matches
- Inside the window, defers to poll interval logic

**Adaptive poll intervals (scheduler.py):**
- Live matches present: **5-10 seconds** (randomized jitter to reduce bot detection)
- Upcoming matches within 15 min: **25-35 seconds**
- No live or imminent matches: **5 minutes**

**Failover and circuit breaker (engine.py):**
- Sources tried in priority order (ESPN first, then SofaScore)
- If a source fails, the next source is tried
- After 5 consecutive failures, source is "demoted" (skipped) for 60 seconds
- After cooldown, source is retried
- Success resets the failure counter

### 5.4 WebSocket Update Flow

```
1. PollingEngine.poll_once() fetches from ESPN/SofaScore
2. For each match: MatchState.update(match) computes diff
3. If anything changed (score, status, events) OR match is live: returns MatchDiff
4. MatchDiff is broadcast to all WebSocket clients
5. Frontend receives {"type": "match_update", "data": {...}} and updates the DOM
6. On initial connect, frontend receives {"type": "full_state", "data": [...all matches...]}
```

**Live match clock:** The API only provides a clock that updates every 30-60 seconds. The frontend estimates a ticking clock locally based on kickoff time and match status (1H: 0-45', 2H: 45-90', ET: 90-120'), updated every second via `setInterval`.

### 5.5 Match Correlation Between Sources

When fetching schedules, the correlator maps the same fixture across ESPN and SofaScore:
1. Kickoff time within 5 minutes
2. Home team name matches (using alias table + fuzzy matching)
3. Away team name matches

This enables the fallback: if ESPN fails for a specific match, the engine can look up the SofaScore ID for that match via `source_match_ids` and fetch from SofaScore instead.

### 5.6 Team Name Normalization

Matching teams across sources requires handling name variations:
- "Man Utd" vs "Manchester United" vs "Manchester United FC"
- "Atlético de Madrid" vs "Atletico Madrid" vs "Atl. Madrid"

Three-tier matching:
1. **Exact match** after normalization (lowercase, strip accents, remove FC/CF/SC suffixes)
2. **Alias table** — ~40 groups covering all PL and La Liga teams plus common variants
3. **Fuzzy match** — `difflib.SequenceMatcher` with 0.8 threshold as fallback

Important: if a name IS in the alias table but doesn't match the other name's group, it's definitively a different team. This prevents "Manchester United" ≈ "Manchester City" (high fuzzy similarity but different alias groups).

---

## 6. Configuration

**`config.toml`:**
```toml
[general]
poll_interval_min = 5.0          # Min seconds between polls
poll_interval_max = 10.0         # Max seconds (randomized jitter)
schedule_refresh_minutes = 30

[sources]
priority = ["espn", "sofascore"] # Fallback order

[leagues]
tracked = ["premier_league", "laliga", "international_friendly"]

[top_teams]
names = []                       # Configure your top teams here
# Example: names = ["Arsenal", "Barcelona", "Real Madrid"]

[top_teams.extra_competitions]
include = [
    "champions_league", "europa_league", "conference_league",
    "fa_cup", "carabao_cup", "copa_del_rey",
]

[server]
host = "0.0.0.0"
port = 8000
```

All config values have sensible defaults — an empty `config.toml` works fine.

---

## 7. Testing

**184 tests** across 10 test files, using a test-first approach (tests written before implementation).

| Module | Tests | What's Tested |
|---|---|---|
| Models | 37 | Validation, serialization, enum coverage, edge cases |
| Team Names | 30 | Normalization, 15+ alias pairs, fuzzy matching, non-matches |
| ESPN | 27 | All match states, all event types, stats, clock, home/away |
| SofaScore | 30 | Status codes, incidents, statistics, team parsing |
| State | 14 | Diffs, live-always-broadcast, concurrency, filters |
| Scheduler | 13 | Active window boundaries, poll intervals, top team filter |
| Engine | 9 | Polling, broadcast, failover, circuit breaker |
| Correlator | 9 | Matching, kickoff tolerance, name variants, edge cases |
| Config | 8 | Loading, defaults, validation errors |
| Web | 7 | REST endpoints, WebSocket connect/state |

**Test fixtures:** 8 recorded JSON files from real ESPN and SofaScore API responses, covering scheduled, live, and finished match states.

**Run tests:** `uv run pytest`
**Lint:** `uv run ruff check src/ tests/`

---

## 8. Dependencies

| Package | Purpose |
|---|---|
| `fastapi` | Web framework with WebSocket support |
| `uvicorn[standard]` | ASGI server |
| `httpx` | Async HTTP client for API calls |
| `pydantic` | Data validation and serialization |
| `pytest` | Testing framework (dev) |
| `pytest-asyncio` | Async test support (dev) |
| `ruff` | Linting (dev) |

---

## 9. Future Work

### Deferred / Not Yet Implemented
- **FotMob source** — Would require implementing the `X-Fm-Req` auth header. Only worth doing if unique FotMob data (xG, player ratings) is needed.
- **Database persistence** — Currently in-memory only. Could add SQLite for match history and analysis.
- **Top teams cross-competition tracking** — Config structure exists but the scheduler doesn't yet filter extra competition schedules by top teams during polling.
- **Debug endpoint** — `/api/debug/inject` for injecting test data during development.

### Known Limitations
- ESPN requires per-league queries (no single "all matches" endpoint)
- ESPN's `displayClock` only updates every 30-60 seconds in their API (frontend compensates with local clock estimation)
- SofaScore's Cloudflare protection may occasionally block requests
- Match correlation assumes kickoff times are within 5 minutes across sources
- No persistence — all data lost on restart
