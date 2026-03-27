"""Tests for the polling engine. Written before implementation."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest

from livescores.models import Match, MatchStatus, Team
from livescores.polling.engine import PollingEngine
from livescores.state import MatchState


def _make_match(
    match_id: str = "espn-123",
    status: MatchStatus = MatchStatus.FIRST_HALF,
    home_score: int = 0,
    away_score: int = 0,
) -> Match:
    return Match(
        id=match_id,
        home_team=Team(name="Arsenal"),
        away_team=Team(name="Chelsea"),
        home_score=home_score,
        away_score=away_score,
        status=status,
        kickoff=datetime(2026, 3, 27, 15, 0, tzinfo=timezone.utc),
        competition="Premier League",
        source="espn",
        source_match_ids={"espn": "123"},
    )


class TestPollingEngineBasics:
    @pytest.mark.asyncio
    async def test_polls_source_for_live_matches(self):
        state = MatchState()
        live_match = _make_match(status=MatchStatus.FIRST_HALF)
        await state.update(live_match)

        source = AsyncMock()
        updated_match = _make_match(status=MatchStatus.FIRST_HALF, home_score=1)
        source.get_schedule = AsyncMock(return_value=[updated_match])

        broadcast = AsyncMock()
        engine = PollingEngine(state=state, sources=[source], broadcast_fn=broadcast)
        await engine.poll_once()

        assert state.get("espn-123").home_score == 1

    @pytest.mark.asyncio
    async def test_broadcasts_on_change(self):
        state = MatchState()
        live_match = _make_match(status=MatchStatus.FIRST_HALF, home_score=0)
        await state.update(live_match)

        source = AsyncMock()
        updated = _make_match(status=MatchStatus.FIRST_HALF, home_score=1)
        source.get_schedule = AsyncMock(return_value=[updated])

        broadcast = AsyncMock()
        engine = PollingEngine(state=state, sources=[source], broadcast_fn=broadcast)
        await engine.poll_once()

        broadcast.assert_called_once()

    @pytest.mark.asyncio
    async def test_no_broadcast_when_no_change_finished(self):
        """Finished matches with no changes should not broadcast."""
        state = MatchState()
        finished_match = _make_match(status=MatchStatus.FINISHED, home_score=1)
        await state.update(finished_match)

        source = AsyncMock()
        same_match = _make_match(status=MatchStatus.FINISHED, home_score=1)
        source.get_schedule = AsyncMock(return_value=[same_match])

        broadcast = AsyncMock()
        engine = PollingEngine(state=state, sources=[source], broadcast_fn=broadcast)
        await engine.poll_once()

        broadcast.assert_not_called()

    @pytest.mark.asyncio
    async def test_live_match_always_broadcasts(self):
        """Live matches always broadcast even if score hasn't changed (clock updates)."""
        state = MatchState()
        live_match = _make_match(status=MatchStatus.FIRST_HALF, home_score=1)
        await state.update(live_match)

        source = AsyncMock()
        same_match = _make_match(status=MatchStatus.FIRST_HALF, home_score=1)
        source.get_schedule = AsyncMock(return_value=[same_match])

        broadcast = AsyncMock()
        engine = PollingEngine(state=state, sources=[source], broadcast_fn=broadcast)
        await engine.poll_once()

        broadcast.assert_called_once()

    @pytest.mark.asyncio
    async def test_handles_source_error_gracefully(self):
        state = MatchState()
        live_match = _make_match()
        await state.update(live_match)

        source = AsyncMock()
        source.get_schedule = AsyncMock(side_effect=Exception("API error"))

        broadcast = AsyncMock()
        engine = PollingEngine(state=state, sources=[source], broadcast_fn=broadcast)
        # Should not raise
        await engine.poll_once()
        # State should be unchanged
        assert state.get("espn-123").home_score == 0


class TestPollingEngineFailover:
    @pytest.mark.asyncio
    async def test_falls_through_to_fallback(self):
        state = MatchState()

        primary = AsyncMock()
        primary.name = "espn"
        primary.get_schedule = AsyncMock(side_effect=Exception("ESPN down"))

        fallback = AsyncMock()
        fallback.name = "sofascore"
        updated = _make_match(home_score=2)
        fallback.get_schedule = AsyncMock(return_value=[updated])

        broadcast = AsyncMock()
        engine = PollingEngine(state=state, sources=[primary, fallback], broadcast_fn=broadcast)
        await engine.poll_once()

        assert state.get("espn-123").home_score == 2

    @pytest.mark.asyncio
    async def test_all_sources_fail_no_crash(self):
        state = MatchState()
        live_match = _make_match()
        await state.update(live_match)

        source1 = AsyncMock()
        source1.name = "espn"
        source1.get_schedule = AsyncMock(side_effect=Exception("ESPN down"))

        source2 = AsyncMock()
        source2.name = "sofascore"
        source2.get_schedule = AsyncMock(side_effect=Exception("SofaScore down"))

        broadcast = AsyncMock()
        engine = PollingEngine(state=state, sources=[source1, source2], broadcast_fn=broadcast)
        await engine.poll_once()

        # State unchanged, no crash
        assert state.get("espn-123").home_score == 0
        broadcast.assert_not_called()

    @pytest.mark.asyncio
    async def test_circuit_breaker_demotes_source(self):
        state = MatchState()

        primary = AsyncMock()
        primary.name = "espn"
        primary.get_schedule = AsyncMock(side_effect=Exception("ESPN down"))

        fallback = AsyncMock()
        fallback.name = "sofascore"
        fallback.get_schedule = AsyncMock(return_value=[_make_match(home_score=1)])

        broadcast = AsyncMock()
        engine = PollingEngine(state=state, sources=[primary, fallback], broadcast_fn=broadcast)

        # Trip the circuit breaker by failing 5 times
        for _ in range(5):
            await engine.poll_once()

        # After 5 failures, primary should be demoted
        assert engine.is_source_demoted("espn")

    @pytest.mark.asyncio
    async def test_circuit_breaker_recovers(self):
        state = MatchState()

        primary = AsyncMock()
        primary.name = "espn"
        primary.get_schedule = AsyncMock(side_effect=Exception("ESPN down"))

        fallback = AsyncMock()
        fallback.name = "sofascore"
        fallback.get_schedule = AsyncMock(return_value=[_make_match(home_score=1)])

        engine = PollingEngine(state=state, sources=[primary, fallback])

        # Trip breaker
        for _ in range(5):
            await engine.poll_once()

        assert engine.is_source_demoted("espn")

        # Reset cooldown manually for test
        engine.reset_circuit_breaker("espn")

        assert not engine.is_source_demoted("espn")
