"""Tests for web layer (REST endpoints and WebSocket). Written before implementation."""

from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from livescores.models import Match, MatchStatus, Team
from livescores.state import MatchState
from livescores.web.app import create_app


def _make_match(
    match_id: str = "espn-123",
    home_name: str = "Arsenal",
    away_name: str = "Chelsea",
    status: MatchStatus = MatchStatus.FIRST_HALF,
    home_score: int = 1,
    away_score: int = 0,
) -> Match:
    return Match(
        id=match_id,
        home_team=Team(name=home_name, short_name=home_name[:3].upper()),
        away_team=Team(name=away_name, short_name=away_name[:3].upper()),
        home_score=home_score,
        away_score=away_score,
        status=status,
        kickoff=datetime(2026, 3, 27, 15, 0, tzinfo=timezone.utc),
        competition="Premier League",
        source="espn",
    )


@pytest.fixture
def state():
    return MatchState()


@pytest.fixture
def app(state):
    return create_app(state=state, start_polling=False)


@pytest.fixture
def client(app):
    return TestClient(app)


class TestRESTEndpoints:
    def test_get_root_returns_html(self, client):
        resp = client.get("/")
        assert resp.status_code == 200
        assert "text/html" in resp.headers["content-type"]

    def test_get_matches_empty(self, client):
        resp = client.get("/api/matches")
        assert resp.status_code == 200
        assert resp.json() == []

    @pytest.mark.asyncio
    async def test_get_matches_with_data(self, state, app):
        await state.update(_make_match("espn-1", "Arsenal", "Chelsea"))
        await state.update(_make_match("espn-2", "Liverpool", "City"))

        with TestClient(app) as client:
            resp = client.get("/api/matches")
            assert resp.status_code == 200
            data = resp.json()
            assert len(data) == 2

    @pytest.mark.asyncio
    async def test_get_match_by_id(self, state, app):
        await state.update(_make_match("espn-123"))

        with TestClient(app) as client:
            resp = client.get("/api/matches/espn-123")
            assert resp.status_code == 200
            data = resp.json()
            assert data["id"] == "espn-123"

    @pytest.mark.asyncio
    async def test_get_match_not_found(self, state, app):
        with TestClient(app) as client:
            resp = client.get("/api/matches/nonexistent")
            assert resp.status_code == 404


class TestWebSocket:
    @pytest.mark.asyncio
    async def test_connect_receives_full_state(self, state, app):
        await state.update(_make_match("espn-1"))

        with TestClient(app) as client:
            with client.websocket_connect("/ws") as ws:
                msg = ws.receive_json()
                assert msg["type"] == "full_state"
                assert len(msg["data"]) == 1
                assert msg["data"][0]["id"] == "espn-1"

    def test_connect_empty_state(self, client):
        with client.websocket_connect("/ws") as ws:
            msg = ws.receive_json()
            assert msg["type"] == "full_state"
            assert msg["data"] == []
