"""Tests for ESPN source parsing. Written before implementation using recorded fixtures."""

import json
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock

import httpx
import pytest

from livescores.models import EventType, MatchStatus
from livescores.sources.espn import ESPNSource

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def _load_fixture(name: str) -> dict:
    with open(FIXTURES_DIR / f"{name}.json") as f:
        return json.load(f)


def _mock_client_for_fixture(fixture_name: str) -> AsyncMock:
    """Create a mock httpx client that returns a fixture for any GET request."""
    data = _load_fixture(fixture_name)
    mock_request = httpx.Request("GET", "https://example.com/test")
    mock_response = httpx.Response(200, json=data, request=mock_request)
    client = AsyncMock()
    client.get = AsyncMock(return_value=mock_response)
    return client


class TestESPNParseSchedule:
    @pytest.mark.asyncio
    async def test_parse_finished_matches(self):
        source = ESPNSource()
        client = _mock_client_for_fixture("espn_scoreboard_finished")
        matches = await source.get_schedule_for_league(client, "eng.1", "20260321")

        assert len(matches) == 5
        # First match: Brighton 2-1 Liverpool
        brighton_match = [m for m in matches if "Brighton" in m.home_team.name][0]
        assert brighton_match.home_score == 2
        assert brighton_match.away_score == 1
        assert brighton_match.status == MatchStatus.FINISHED
        assert "Liverpool" in brighton_match.away_team.name

    @pytest.mark.asyncio
    async def test_parse_scheduled_matches(self):
        source = ESPNSource()
        client = _mock_client_for_fixture("espn_scoreboard_scheduled")
        matches = await source.get_schedule_for_league(client, "esp.1", "20260404")

        assert len(matches) == 4
        for m in matches:
            assert m.status == MatchStatus.SCHEDULED
            assert m.home_score is None or m.home_score == 0

    @pytest.mark.asyncio
    async def test_parse_postponed_match(self):
        source = ESPNSource()
        client = _mock_client_for_fixture("espn_scoreboard_finished")
        matches = await source.get_schedule_for_league(client, "eng.1", "20260321")

        postponed = [m for m in matches if m.status == MatchStatus.POSTPONED]
        assert len(postponed) == 1
        assert "Crystal Palace" in postponed[0].home_team.name or "Manchester City" in postponed[0].home_team.name

    @pytest.mark.asyncio
    async def test_team_names_populated(self):
        source = ESPNSource()
        client = _mock_client_for_fixture("espn_scoreboard_finished")
        matches = await source.get_schedule_for_league(client, "eng.1", "20260321")

        brighton_match = matches[0]
        assert brighton_match.home_team.name != ""
        assert brighton_match.away_team.name != ""
        assert brighton_match.home_team.short_name is not None
        assert brighton_match.away_team.short_name is not None

    @pytest.mark.asyncio
    async def test_team_source_ids(self):
        source = ESPNSource()
        client = _mock_client_for_fixture("espn_scoreboard_finished")
        matches = await source.get_schedule_for_league(client, "eng.1", "20260321")

        for m in matches:
            assert "espn" in m.home_team.source_ids
            assert "espn" in m.away_team.source_ids

    @pytest.mark.asyncio
    async def test_match_has_espn_source(self):
        source = ESPNSource()
        client = _mock_client_for_fixture("espn_scoreboard_finished")
        matches = await source.get_schedule_for_league(client, "eng.1", "20260321")

        for m in matches:
            assert m.source == "espn"
            assert "espn" in m.source_match_ids

    @pytest.mark.asyncio
    async def test_kickoff_is_utc_datetime(self):
        source = ESPNSource()
        client = _mock_client_for_fixture("espn_scoreboard_scheduled")
        matches = await source.get_schedule_for_league(client, "esp.1", "20260404")

        for m in matches:
            assert isinstance(m.kickoff, datetime)
            assert m.kickoff.tzinfo is not None

    @pytest.mark.asyncio
    async def test_competition_name(self):
        source = ESPNSource()
        client = _mock_client_for_fixture("espn_scoreboard_finished")
        matches = await source.get_schedule_for_league(client, "eng.1", "20260321")

        for m in matches:
            assert m.competition != ""


class TestESPNParseEvents:
    @pytest.mark.asyncio
    async def test_goals_parsed(self):
        source = ESPNSource()
        client = _mock_client_for_fixture("espn_scoreboard_finished")
        matches = await source.get_schedule_for_league(client, "eng.1", "20260321")

        # Brighton 2-1 Liverpool has 3 goals
        brighton_match = [m for m in matches if "Brighton" in m.home_team.name][0]
        goals = [e for e in brighton_match.events if e.type in (EventType.GOAL, EventType.PENALTY_GOAL)]
        assert len(goals) == 3

    @pytest.mark.asyncio
    async def test_goal_has_player_name(self):
        source = ESPNSource()
        client = _mock_client_for_fixture("espn_scoreboard_finished")
        matches = await source.get_schedule_for_league(client, "eng.1", "20260321")

        brighton_match = [m for m in matches if "Brighton" in m.home_team.name][0]
        goals = [e for e in brighton_match.events if e.type in (EventType.GOAL, EventType.PENALTY_GOAL)]
        for g in goals:
            assert g.player_name is not None
            assert g.player_name != ""

    @pytest.mark.asyncio
    async def test_goal_has_minute(self):
        source = ESPNSource()
        client = _mock_client_for_fixture("espn_scoreboard_finished")
        matches = await source.get_schedule_for_league(client, "eng.1", "20260321")

        brighton_match = [m for m in matches if "Brighton" in m.home_team.name][0]
        goals = [e for e in brighton_match.events if e.type in (EventType.GOAL, EventType.PENALTY_GOAL)]
        assert goals[0].minute == 14  # Welbeck 14'

    @pytest.mark.asyncio
    async def test_yellow_cards_parsed(self):
        source = ESPNSource()
        client = _mock_client_for_fixture("espn_scoreboard_finished")
        matches = await source.get_schedule_for_league(client, "eng.1", "20260321")

        brighton_match = [m for m in matches if "Brighton" in m.home_team.name][0]
        yellows = [e for e in brighton_match.events if e.type == EventType.YELLOW_CARD]
        assert len(yellows) >= 5  # Several yellow cards in this match

    @pytest.mark.asyncio
    async def test_red_card_parsed(self):
        source = ESPNSource()
        client = _mock_client_for_fixture("espn_scoreboard_finished")
        matches = await source.get_schedule_for_league(client, "eng.1", "20260321")

        # Fulham vs Burnley has a red card (type id 93, J. Laurent)
        fulham_match = [m for m in matches if "Fulham" in m.home_team.name][0]
        reds = [e for e in fulham_match.events if e.type == EventType.RED_CARD]
        assert len(reds) == 1

    @pytest.mark.asyncio
    async def test_penalty_goal_parsed(self):
        source = ESPNSource()
        client = _mock_client_for_fixture("espn_scoreboard_finished")
        matches = await source.get_schedule_for_league(client, "eng.1", "20260321")

        # Check if any match has a penalty goal (type 98 exists in fixture)
        all_events = []
        for m in matches:
            all_events.extend(m.events)
        penalties = [e for e in all_events if e.type == EventType.PENALTY_GOAL]
        assert len(penalties) >= 1

    @pytest.mark.asyncio
    async def test_event_is_home_correct(self):
        source = ESPNSource()
        client = _mock_client_for_fixture("espn_scoreboard_finished")
        matches = await source.get_schedule_for_league(client, "eng.1", "20260321")

        # Brighton (home, id 331) scored at 14' and 56'
        brighton_match = [m for m in matches if "Brighton" in m.home_team.name][0]
        goals = [e for e in brighton_match.events if e.type in (EventType.GOAL, EventType.PENALTY_GOAL)]
        home_goals = [g for g in goals if g.is_home]
        away_goals = [g for g in goals if not g.is_home]
        assert len(home_goals) == 2  # Brighton scored twice
        assert len(away_goals) == 1  # Liverpool scored once

    @pytest.mark.asyncio
    async def test_no_events_for_scheduled_match(self):
        source = ESPNSource()
        client = _mock_client_for_fixture("espn_scoreboard_scheduled")
        matches = await source.get_schedule_for_league(client, "esp.1", "20260404")

        for m in matches:
            assert len(m.events) == 0

    @pytest.mark.asyncio
    async def test_no_events_for_postponed_match(self):
        source = ESPNSource()
        client = _mock_client_for_fixture("espn_scoreboard_finished")
        matches = await source.get_schedule_for_league(client, "eng.1", "20260321")

        postponed = [m for m in matches if m.status == MatchStatus.POSTPONED][0]
        assert len(postponed.events) == 0


class TestESPNParseStats:
    @pytest.mark.asyncio
    async def test_finished_match_has_stats(self):
        source = ESPNSource()
        client = _mock_client_for_fixture("espn_scoreboard_finished")
        matches = await source.get_schedule_for_league(client, "eng.1", "20260321")

        brighton_match = [m for m in matches if "Brighton" in m.home_team.name][0]
        assert brighton_match.stats is not None

    @pytest.mark.asyncio
    async def test_possession_parsed(self):
        source = ESPNSource()
        client = _mock_client_for_fixture("espn_scoreboard_finished")
        matches = await source.get_schedule_for_league(client, "eng.1", "20260321")

        brighton_match = [m for m in matches if "Brighton" in m.home_team.name][0]
        assert brighton_match.stats.possession_home is not None
        assert brighton_match.stats.possession_away is not None
        # Possession should roughly add up to 100
        total = brighton_match.stats.possession_home + brighton_match.stats.possession_away
        assert 98 <= total <= 102

    @pytest.mark.asyncio
    async def test_shots_parsed(self):
        source = ESPNSource()
        client = _mock_client_for_fixture("espn_scoreboard_finished")
        matches = await source.get_schedule_for_league(client, "eng.1", "20260321")

        brighton_match = [m for m in matches if "Brighton" in m.home_team.name][0]
        assert brighton_match.stats.shots_home is not None
        assert brighton_match.stats.shots_away is not None

    @pytest.mark.asyncio
    async def test_shots_on_target_parsed(self):
        source = ESPNSource()
        client = _mock_client_for_fixture("espn_scoreboard_finished")
        matches = await source.get_schedule_for_league(client, "eng.1", "20260321")

        brighton_match = [m for m in matches if "Brighton" in m.home_team.name][0]
        assert brighton_match.stats.shots_on_target_home is not None
        assert brighton_match.stats.shots_on_target_away is not None

    @pytest.mark.asyncio
    async def test_corners_parsed(self):
        source = ESPNSource()
        client = _mock_client_for_fixture("espn_scoreboard_finished")
        matches = await source.get_schedule_for_league(client, "eng.1", "20260321")

        brighton_match = [m for m in matches if "Brighton" in m.home_team.name][0]
        assert brighton_match.stats.corners_home is not None

    @pytest.mark.asyncio
    async def test_fouls_parsed(self):
        source = ESPNSource()
        client = _mock_client_for_fixture("espn_scoreboard_finished")
        matches = await source.get_schedule_for_league(client, "eng.1", "20260321")

        brighton_match = [m for m in matches if "Brighton" in m.home_team.name][0]
        assert brighton_match.stats.fouls_home is not None

    @pytest.mark.asyncio
    async def test_scheduled_match_no_stats(self):
        source = ESPNSource()
        client = _mock_client_for_fixture("espn_scoreboard_scheduled")
        matches = await source.get_schedule_for_league(client, "esp.1", "20260404")

        for m in matches:
            assert m.stats is None

    @pytest.mark.asyncio
    async def test_postponed_match_no_stats(self):
        source = ESPNSource()
        client = _mock_client_for_fixture("espn_scoreboard_finished")
        matches = await source.get_schedule_for_league(client, "eng.1", "20260321")

        postponed = [m for m in matches if m.status == MatchStatus.POSTPONED][0]
        assert postponed.stats is None


class TestESPNMatchClock:
    @pytest.mark.asyncio
    async def test_finished_match_clock(self):
        source = ESPNSource()
        client = _mock_client_for_fixture("espn_scoreboard_finished")
        matches = await source.get_schedule_for_league(client, "eng.1", "20260321")

        brighton_match = [m for m in matches if "Brighton" in m.home_team.name][0]
        # Finished match should have FT or the final clock value
        assert brighton_match.match_clock is not None

    @pytest.mark.asyncio
    async def test_scheduled_match_no_clock(self):
        source = ESPNSource()
        client = _mock_client_for_fixture("espn_scoreboard_scheduled")
        matches = await source.get_schedule_for_league(client, "esp.1", "20260404")

        for m in matches:
            assert m.match_clock is None
