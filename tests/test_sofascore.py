"""Tests for SofaScore source parsing. Written before implementation using recorded fixtures."""

import json
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock

import httpx
import pytest

from livescores.models import EventType, MatchStatus
from livescores.sources.sofascore import SofaScoreSource

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def _load_fixture(name: str) -> dict:
    with open(FIXTURES_DIR / f"{name}.json") as f:
        return json.load(f)


def _mock_client(responses: dict[str, dict]) -> AsyncMock:
    """Create a mock client that returns different fixtures based on URL substring."""
    client = AsyncMock()

    async def mock_get(url, **kwargs):
        for pattern, data in responses.items():
            if pattern in str(url):
                req = httpx.Request("GET", str(url))
                return httpx.Response(200, json=data, request=req)
        req = httpx.Request("GET", str(url))
        return httpx.Response(404, json={}, request=req)

    client.get = mock_get
    return client


class TestSofaScoreParseScheduledEvents:
    @pytest.mark.asyncio
    async def test_parse_scheduled_events(self):
        source = SofaScoreSource()
        data = _load_fixture("sofascore_scheduled_events")
        matches = source.parse_events_response(data)
        assert len(matches) > 0

    @pytest.mark.asyncio
    async def test_finished_match_parsed(self):
        source = SofaScoreSource()
        data = _load_fixture("sofascore_scheduled_events")
        matches = source.parse_events_response(data)
        finished = [m for m in matches if m.status == MatchStatus.FINISHED]
        assert len(finished) > 0

    @pytest.mark.asyncio
    async def test_finished_match_has_scores(self):
        source = SofaScoreSource()
        data = _load_fixture("sofascore_scheduled_events")
        matches = source.parse_events_response(data)
        # Türkiye 1-0 Romania
        turkey_match = [m for m in matches if "rkiye" in m.home_team.name or "Turkey" in m.home_team.name]
        assert len(turkey_match) >= 1
        m = turkey_match[0]
        assert m.home_score == 1
        assert m.away_score == 0

    @pytest.mark.asyncio
    async def test_scheduled_match_parsed(self):
        source = SofaScoreSource()
        data = _load_fixture("sofascore_scheduled_events")
        matches = source.parse_events_response(data)
        scheduled = [m for m in matches if m.status == MatchStatus.SCHEDULED]
        assert len(scheduled) > 0

    @pytest.mark.asyncio
    async def test_scheduled_match_no_score(self):
        source = SofaScoreSource()
        data = _load_fixture("sofascore_scheduled_events")
        matches = source.parse_events_response(data)
        scheduled = [m for m in matches if m.status == MatchStatus.SCHEDULED]
        for m in scheduled:
            assert m.home_score is None
            assert m.away_score is None

    @pytest.mark.asyncio
    async def test_cancelled_match_parsed(self):
        source = SofaScoreSource()
        data = _load_fixture("sofascore_scheduled_events")
        matches = source.parse_events_response(data)
        cancelled = [m for m in matches if m.status == MatchStatus.CANCELLED]
        assert len(cancelled) > 0


class TestSofaScoreParseLiveEvents:
    @pytest.mark.asyncio
    async def test_parse_live_events(self):
        source = SofaScoreSource()
        data = _load_fixture("sofascore_live_events")
        matches = source.parse_events_response(data)
        assert len(matches) > 0

    @pytest.mark.asyncio
    async def test_live_match_has_scores(self):
        source = SofaScoreSource()
        data = _load_fixture("sofascore_live_events")
        matches = source.parse_events_response(data)
        live = [m for m in matches if m.status.is_live]
        assert len(live) > 0
        # At least some live matches should have scores
        with_scores = [m for m in live if m.home_score is not None]
        assert len(with_scores) > 0


class TestSofaScoreStatusMapping:
    @pytest.mark.asyncio
    async def test_status_code_0_is_scheduled(self):
        source = SofaScoreSource()
        data = _load_fixture("sofascore_scheduled_events")
        matches = source.parse_events_response(data)
        # Find a match with status code 0
        scheduled = [m for m in matches if m.status == MatchStatus.SCHEDULED]
        assert len(scheduled) > 0

    @pytest.mark.asyncio
    async def test_status_code_6_is_first_half(self):
        source = SofaScoreSource()
        data = _load_fixture("sofascore_live_events")
        matches = source.parse_events_response(data)
        first_half = [m for m in matches if m.status == MatchStatus.FIRST_HALF]
        assert len(first_half) > 0

    @pytest.mark.asyncio
    async def test_status_code_7_is_second_half(self):
        source = SofaScoreSource()
        data = _load_fixture("sofascore_live_events")
        matches = source.parse_events_response(data)
        second_half = [m for m in matches if m.status == MatchStatus.SECOND_HALF]
        assert len(second_half) > 0

    @pytest.mark.asyncio
    async def test_status_code_31_is_halftime(self):
        source = SofaScoreSource()
        data = _load_fixture("sofascore_live_events")
        matches = source.parse_events_response(data)
        halftime = [m for m in matches if m.status == MatchStatus.HALFTIME]
        assert len(halftime) > 0

    @pytest.mark.asyncio
    async def test_status_code_100_is_finished(self):
        source = SofaScoreSource()
        data = _load_fixture("sofascore_scheduled_events")
        matches = source.parse_events_response(data)
        finished = [m for m in matches if m.status == MatchStatus.FINISHED]
        assert len(finished) > 0

    @pytest.mark.asyncio
    async def test_status_code_70_is_cancelled(self):
        source = SofaScoreSource()
        data = _load_fixture("sofascore_scheduled_events")
        matches = source.parse_events_response(data)
        cancelled = [m for m in matches if m.status == MatchStatus.CANCELLED]
        assert len(cancelled) > 0


class TestSofaScoreTeamParsing:
    @pytest.mark.asyncio
    async def test_team_names_populated(self):
        source = SofaScoreSource()
        data = _load_fixture("sofascore_live_events")
        matches = source.parse_events_response(data)
        for m in matches[:5]:
            assert m.home_team.name != ""
            assert m.away_team.name != ""

    @pytest.mark.asyncio
    async def test_team_short_names(self):
        source = SofaScoreSource()
        data = _load_fixture("sofascore_live_events")
        matches = source.parse_events_response(data)
        # SofaScore provides nameCode (e.g. "COR")
        for m in matches[:5]:
            assert m.home_team.short_name is not None

    @pytest.mark.asyncio
    async def test_team_source_ids(self):
        source = SofaScoreSource()
        data = _load_fixture("sofascore_live_events")
        matches = source.parse_events_response(data)
        for m in matches[:5]:
            assert "sofascore" in m.home_team.source_ids
            assert "sofascore" in m.away_team.source_ids

    @pytest.mark.asyncio
    async def test_match_source_is_sofascore(self):
        source = SofaScoreSource()
        data = _load_fixture("sofascore_live_events")
        matches = source.parse_events_response(data)
        for m in matches[:5]:
            assert m.source == "sofascore"
            assert "sofascore" in m.source_match_ids


class TestSofaScoreKickoff:
    @pytest.mark.asyncio
    async def test_kickoff_is_datetime(self):
        source = SofaScoreSource()
        data = _load_fixture("sofascore_live_events")
        matches = source.parse_events_response(data)
        for m in matches[:5]:
            assert isinstance(m.kickoff, datetime)
            assert m.kickoff.tzinfo is not None


class TestSofaScoreParseIncidents:
    @pytest.mark.asyncio
    async def test_parse_period_incident(self):
        source = SofaScoreSource()
        data = _load_fixture("sofascore_incidents")
        events = source.parse_incidents(data)
        # The fixture has only a period marker, no goals/cards
        # Period markers should be skipped
        assert len(events) == 0

    @pytest.mark.asyncio
    async def test_parse_goal_incident(self):
        source = SofaScoreSource()
        # Synthetic goal incident
        data = {"incidents": [{
            "incidentType": "goal",
            "incidentClass": "regular",
            "time": 25,
            "addedTime": None,
            "isHome": True,
            "player": {"name": "Test Player", "id": 123},
            "homeScore": 1,
            "awayScore": 0,
        }]}
        events = source.parse_incidents(data)
        assert len(events) == 1
        assert events[0].type == EventType.GOAL
        assert events[0].minute == 25
        assert events[0].player_name == "Test Player"
        assert events[0].is_home is True

    @pytest.mark.asyncio
    async def test_parse_yellow_card_incident(self):
        source = SofaScoreSource()
        data = {"incidents": [{
            "incidentType": "card",
            "incidentClass": "yellow",
            "time": 33,
            "isHome": False,
            "player": {"name": "Test Player", "id": 456},
        }]}
        events = source.parse_incidents(data)
        assert len(events) == 1
        assert events[0].type == EventType.YELLOW_CARD

    @pytest.mark.asyncio
    async def test_parse_red_card_incident(self):
        source = SofaScoreSource()
        data = {"incidents": [{
            "incidentType": "card",
            "incidentClass": "red",
            "time": 70,
            "isHome": True,
            "player": {"name": "Test Player", "id": 789},
        }]}
        events = source.parse_incidents(data)
        assert len(events) == 1
        assert events[0].type == EventType.RED_CARD

    @pytest.mark.asyncio
    async def test_parse_substitution_incident(self):
        source = SofaScoreSource()
        data = {"incidents": [{
            "incidentType": "substitution",
            "time": 60,
            "isHome": True,
            "playerIn": {"name": "Sub In", "id": 1},
            "playerOut": {"name": "Sub Out", "id": 2},
        }]}
        events = source.parse_incidents(data)
        assert len(events) == 1
        assert events[0].type == EventType.SUBSTITUTION
        assert events[0].player_in == "Sub In"
        assert events[0].player_out == "Sub Out"

    @pytest.mark.asyncio
    async def test_parse_own_goal_incident(self):
        source = SofaScoreSource()
        data = {"incidents": [{
            "incidentType": "goal",
            "incidentClass": "ownGoal",
            "time": 40,
            "isHome": True,
            "player": {"name": "Unlucky", "id": 111},
            "homeScore": 0,
            "awayScore": 1,
        }]}
        events = source.parse_incidents(data)
        assert len(events) == 1
        assert events[0].type == EventType.OWN_GOAL

    @pytest.mark.asyncio
    async def test_parse_penalty_goal_incident(self):
        source = SofaScoreSource()
        data = {"incidents": [{
            "incidentType": "goal",
            "incidentClass": "penalty",
            "time": 55,
            "isHome": False,
            "player": {"name": "Pen Taker", "id": 222},
            "homeScore": 0,
            "awayScore": 1,
        }]}
        events = source.parse_incidents(data)
        assert len(events) == 1
        assert events[0].type == EventType.PENALTY_GOAL


class TestSofaScoreParseStatistics:
    @pytest.mark.asyncio
    async def test_parse_stats(self):
        source = SofaScoreSource()
        data = _load_fixture("sofascore_statistics")
        stats = source.parse_statistics(data)
        assert stats is not None

    @pytest.mark.asyncio
    async def test_possession_parsed(self):
        source = SofaScoreSource()
        data = _load_fixture("sofascore_statistics")
        stats = source.parse_statistics(data)
        assert stats.possession_home == 44.0
        assert stats.possession_away == 56.0

    @pytest.mark.asyncio
    async def test_shots_parsed(self):
        source = SofaScoreSource()
        data = _load_fixture("sofascore_statistics")
        stats = source.parse_statistics(data)
        # totalShotsOnGoal from fixture: home=0, away=1
        assert stats.shots_home is not None
        assert stats.shots_away is not None

    @pytest.mark.asyncio
    async def test_empty_stats(self):
        source = SofaScoreSource()
        stats = source.parse_statistics({"statistics": []})
        assert stats is None
