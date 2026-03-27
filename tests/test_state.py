"""Tests for in-memory state store. Written before implementation."""

import asyncio
from datetime import datetime, timezone

import pytest

from livescores.models import (
    EventType,
    Match,
    MatchEvent,
    MatchStats,
    MatchStatus,
    Team,
)
from livescores.state import MatchState


def _make_match(
    match_id: str = "espn-123",
    home_name: str = "Arsenal",
    away_name: str = "Chelsea",
    home_score: int | None = 0,
    away_score: int | None = 0,
    status: MatchStatus = MatchStatus.FIRST_HALF,
    competition: str = "Premier League",
    events: list | None = None,
    stats: MatchStats | None = None,
) -> Match:
    return Match(
        id=match_id,
        home_team=Team(name=home_name, short_name=home_name[:3].upper()),
        away_team=Team(name=away_name, short_name=away_name[:3].upper()),
        home_score=home_score,
        away_score=away_score,
        status=status,
        kickoff=datetime(2026, 3, 27, 15, 0, tzinfo=timezone.utc),
        competition=competition,
        events=events or [],
        stats=stats,
        source="espn",
    )


class TestMatchStateBasics:
    @pytest.mark.asyncio
    async def test_add_and_get(self):
        state = MatchState()
        match = _make_match()
        await state.update(match)
        result = state.get(match.id)
        assert result is not None
        assert result.id == match.id

    @pytest.mark.asyncio
    async def test_get_nonexistent(self):
        state = MatchState()
        assert state.get("nonexistent") is None

    @pytest.mark.asyncio
    async def test_get_all(self):
        state = MatchState()
        m1 = _make_match("espn-1", home_name="Arsenal")
        m2 = _make_match("espn-2", home_name="Liverpool")
        await state.update(m1)
        await state.update(m2)
        all_matches = state.get_all()
        assert len(all_matches) == 2

    @pytest.mark.asyncio
    async def test_get_all_sorted_by_kickoff(self):
        state = MatchState()
        m1 = _make_match("espn-1")
        m2 = _make_match("espn-2")
        m2.kickoff = datetime(2026, 3, 27, 14, 0, tzinfo=timezone.utc)  # Earlier
        await state.update(m1)
        await state.update(m2)
        all_matches = state.get_all()
        assert all_matches[0].id == "espn-2"  # Earlier kickoff first


class TestMatchStateDiffs:
    @pytest.mark.asyncio
    async def test_score_change_returns_diff(self):
        state = MatchState()
        m1 = _make_match(home_score=0, away_score=0)
        await state.update(m1)

        m2 = _make_match(home_score=1, away_score=0)
        diff = await state.update(m2)
        assert diff is not None
        assert diff.score_changed

    @pytest.mark.asyncio
    async def test_no_change_returns_none_for_finished(self):
        state = MatchState()
        m1 = _make_match(home_score=1, away_score=0, status=MatchStatus.FINISHED)
        await state.update(m1)

        m2 = _make_match(home_score=1, away_score=0, status=MatchStatus.FINISHED)
        diff = await state.update(m2)
        assert diff is None

    @pytest.mark.asyncio
    async def test_live_match_always_returns_diff(self):
        state = MatchState()
        m1 = _make_match(home_score=1, away_score=0, status=MatchStatus.FIRST_HALF)
        await state.update(m1)

        m2 = _make_match(home_score=1, away_score=0, status=MatchStatus.FIRST_HALF)
        diff = await state.update(m2)
        # Live matches always broadcast (clock is ticking)
        assert diff is not None

    @pytest.mark.asyncio
    async def test_status_change_returns_diff(self):
        state = MatchState()
        m1 = _make_match(status=MatchStatus.FIRST_HALF)
        await state.update(m1)

        m2 = _make_match(status=MatchStatus.HALFTIME)
        diff = await state.update(m2)
        assert diff is not None
        assert diff.status_changed

    @pytest.mark.asyncio
    async def test_new_event_returns_diff(self):
        state = MatchState()
        m1 = _make_match(events=[])
        await state.update(m1)

        m2 = _make_match(events=[
            MatchEvent(type=EventType.GOAL, minute=15, player_name="Saka", is_home=True)
        ])
        diff = await state.update(m2)
        assert diff is not None
        assert diff.events_changed

    @pytest.mark.asyncio
    async def test_first_add_returns_diff(self):
        state = MatchState()
        m1 = _make_match()
        diff = await state.update(m1)
        assert diff is not None

    @pytest.mark.asyncio
    async def test_status_progression(self):
        state = MatchState()
        statuses = [
            MatchStatus.SCHEDULED,
            MatchStatus.FIRST_HALF,
            MatchStatus.HALFTIME,
            MatchStatus.SECOND_HALF,
            MatchStatus.FINISHED,
        ]
        for status in statuses:
            m = _make_match(status=status)
            diff = await state.update(m)
            assert diff is not None


class TestMatchStateFilters:
    @pytest.mark.asyncio
    async def test_get_live(self):
        state = MatchState()
        live = _make_match("espn-1", status=MatchStatus.FIRST_HALF)
        finished = _make_match("espn-2", status=MatchStatus.FINISHED)
        scheduled = _make_match("espn-3", status=MatchStatus.SCHEDULED)
        for m in [live, finished, scheduled]:
            await state.update(m)

        live_matches = state.get_live()
        assert len(live_matches) == 1
        assert live_matches[0].id == "espn-1"

    @pytest.mark.asyncio
    async def test_get_by_competition(self):
        state = MatchState()
        m1 = _make_match("espn-1", competition="Premier League")
        m2 = _make_match("espn-2", competition="La Liga")
        m3 = _make_match("espn-3", competition="Premier League")
        for m in [m1, m2, m3]:
            await state.update(m)

        by_comp = state.get_by_competition()
        assert "Premier League" in by_comp
        assert "La Liga" in by_comp
        assert len(by_comp["Premier League"]) == 2
        assert len(by_comp["La Liga"]) == 1


class TestMatchStateConcurrency:
    @pytest.mark.asyncio
    async def test_concurrent_updates_dont_corrupt(self):
        state = MatchState()

        async def update_match(i: int):
            m = _make_match(f"espn-{i}", home_score=i)
            await state.update(m)

        await asyncio.gather(*[update_match(i) for i in range(100)])
        all_matches = state.get_all()
        assert len(all_matches) == 100
