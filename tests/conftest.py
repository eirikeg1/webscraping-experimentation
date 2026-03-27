import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def fixtures_dir() -> Path:
    return FIXTURES_DIR


def load_fixture(name: str) -> dict:
    """Load a JSON fixture file by name (without .json extension)."""
    path = FIXTURES_DIR / f"{name}.json"
    with open(path) as f:
        return json.load(f)


@pytest.fixture
def espn_scoreboard_finished() -> dict:
    return load_fixture("espn_scoreboard_finished")


@pytest.fixture
def espn_scoreboard_scheduled() -> dict:
    return load_fixture("espn_scoreboard_scheduled")


@pytest.fixture
def espn_scoreboard_live() -> dict:
    return load_fixture("espn_scoreboard_live")


@pytest.fixture
def sofascore_scheduled_events() -> dict:
    return load_fixture("sofascore_scheduled_events")


@pytest.fixture
def sofascore_live_events() -> dict:
    return load_fixture("sofascore_live_events")


@pytest.fixture
def sofascore_event_detail() -> dict:
    return load_fixture("sofascore_event_detail")


@pytest.fixture
def sofascore_incidents() -> dict:
    return load_fixture("sofascore_incidents")


@pytest.fixture
def sofascore_statistics() -> dict:
    return load_fixture("sofascore_statistics")


def make_team(
    name: str = "Arsenal",
    short_name: str | None = "ARS",
    source_ids: dict[str, str] | None = None,
) -> dict:
    """Helper to build a Team-compatible dict for tests."""
    return {
        "name": name,
        "short_name": short_name,
        "source_ids": source_ids or {},
    }


def make_match_event(
    event_type: str = "goal",
    minute: int = 45,
    added_time: int | None = None,
    player_name: str | None = "Test Player",
    is_home: bool = True,
    **kwargs,
) -> dict:
    """Helper to build a MatchEvent-compatible dict for tests."""
    return {
        "type": event_type,
        "minute": minute,
        "added_time": added_time,
        "player_name": player_name,
        "is_home": is_home,
        **kwargs,
    }


def make_match(
    match_id: str = "test-match-1",
    home_team: dict | None = None,
    away_team: dict | None = None,
    home_score: int | None = 0,
    away_score: int | None = 0,
    status: str = "SCHEDULED",
    match_clock: str | None = None,
    kickoff: str | None = None,
    competition: str = "Premier League",
    events: list[dict] | None = None,
    stats: dict | None = None,
    source: str = "espn",
    source_match_ids: dict[str, str] | None = None,
) -> dict:
    """Helper to build a Match-compatible dict for tests."""
    return {
        "id": match_id,
        "home_team": home_team or make_team("Arsenal", "ARS"),
        "away_team": away_team or make_team("Chelsea", "CHE"),
        "home_score": home_score,
        "away_score": away_score,
        "status": status,
        "match_clock": match_clock,
        "kickoff": kickoff or "2026-03-27T15:00:00Z",
        "competition": competition,
        "events": events or [],
        "stats": stats,
        "source": source,
        "source_match_ids": source_match_ids or {},
        "last_updated": datetime.now(timezone.utc).isoformat(),
    }
