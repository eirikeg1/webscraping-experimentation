"""Tests for data models. Written before implementation (test-first)."""

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


class TestMatchStatus:
    def test_all_statuses_exist(self):
        expected = {"SCHEDULED", "1H", "HT", "2H", "ET", "PEN", "FT", "PPD", "CAN"}
        actual = {s.value for s in MatchStatus}
        assert expected == actual

    def test_live_statuses(self):
        live = {MatchStatus.FIRST_HALF, MatchStatus.SECOND_HALF, MatchStatus.EXTRA_TIME, MatchStatus.PENALTIES}
        for status in live:
            assert status.is_live

    def test_non_live_statuses(self):
        non_live = {MatchStatus.SCHEDULED, MatchStatus.HALFTIME, MatchStatus.FINISHED, MatchStatus.POSTPONED, MatchStatus.CANCELLED}
        for status in non_live:
            assert not status.is_live


class TestEventType:
    def test_all_event_types_exist(self):
        expected = {"goal", "own_goal", "penalty_goal", "yellow_card", "red_card", "second_yellow", "substitution"}
        actual = {t.value for t in EventType}
        assert expected == actual


class TestTeam:
    def test_create_team(self):
        team = Team(name="Arsenal", short_name="ARS")
        assert team.name == "Arsenal"
        assert team.short_name == "ARS"
        assert team.source_ids == {}

    def test_create_team_with_source_ids(self):
        team = Team(name="Arsenal", short_name="ARS", source_ids={"espn": "359", "sofascore": "42"})
        assert team.source_ids["espn"] == "359"
        assert team.source_ids["sofascore"] == "42"

    def test_team_requires_name(self):
        with pytest.raises(Exception):
            Team(short_name="ARS")

    def test_team_optional_short_name(self):
        team = Team(name="Arsenal")
        assert team.short_name is None

    def test_team_serialization(self):
        team = Team(name="Arsenal", short_name="ARS", source_ids={"espn": "359"})
        data = team.model_dump()
        assert data["name"] == "Arsenal"
        assert data["short_name"] == "ARS"
        assert data["source_ids"] == {"espn": "359"}

    def test_team_from_dict(self):
        data = {"name": "Chelsea", "short_name": "CHE", "source_ids": {}}
        team = Team.model_validate(data)
        assert team.name == "Chelsea"


class TestMatchEvent:
    def test_create_goal(self):
        event = MatchEvent(
            type=EventType.GOAL,
            minute=45,
            player_name="Saka",
            is_home=True,
        )
        assert event.type == EventType.GOAL
        assert event.minute == 45
        assert event.player_name == "Saka"
        assert event.is_home is True
        assert event.added_time is None

    def test_create_goal_with_added_time(self):
        event = MatchEvent(
            type=EventType.GOAL,
            minute=90,
            added_time=3,
            player_name="Salah",
            is_home=False,
        )
        assert event.added_time == 3

    def test_create_yellow_card(self):
        event = MatchEvent(
            type=EventType.YELLOW_CARD,
            minute=30,
            player_name="Casemiro",
            is_home=True,
        )
        assert event.type == EventType.YELLOW_CARD

    def test_create_red_card(self):
        event = MatchEvent(
            type=EventType.RED_CARD,
            minute=60,
            player_name="Casemiro",
            is_home=True,
        )
        assert event.type == EventType.RED_CARD

    def test_create_second_yellow(self):
        event = MatchEvent(
            type=EventType.SECOND_YELLOW,
            minute=75,
            player_name="Casemiro",
            is_home=True,
        )
        assert event.type == EventType.SECOND_YELLOW

    def test_create_substitution(self):
        event = MatchEvent(
            type=EventType.SUBSTITUTION,
            minute=60,
            player_name="Saka",
            player_in="Martinelli",
            player_out="Saka",
            is_home=True,
        )
        assert event.player_in == "Martinelli"
        assert event.player_out == "Saka"

    def test_create_own_goal(self):
        event = MatchEvent(
            type=EventType.OWN_GOAL,
            minute=22,
            player_name="Stones",
            is_home=False,
        )
        assert event.type == EventType.OWN_GOAL

    def test_create_penalty_goal(self):
        event = MatchEvent(
            type=EventType.PENALTY_GOAL,
            minute=55,
            player_name="Salah",
            is_home=True,
        )
        assert event.type == EventType.PENALTY_GOAL

    def test_event_requires_type(self):
        with pytest.raises(Exception):
            MatchEvent(minute=45, player_name="Saka", is_home=True)

    def test_event_requires_minute(self):
        with pytest.raises(Exception):
            MatchEvent(type=EventType.GOAL, player_name="Saka", is_home=True)

    def test_event_optional_player(self):
        event = MatchEvent(type=EventType.GOAL, minute=45, is_home=True)
        assert event.player_name is None

    def test_event_serialization_roundtrip(self):
        event = MatchEvent(
            type=EventType.GOAL,
            minute=45,
            added_time=2,
            player_name="Saka",
            assist_name="Odegaard",
            is_home=True,
        )
        data = event.model_dump()
        restored = MatchEvent.model_validate(data)
        assert restored == event


class TestMatchStats:
    def test_create_full_stats(self):
        stats = MatchStats(
            possession_home=58.0,
            possession_away=42.0,
            shots_home=12,
            shots_away=8,
            shots_on_target_home=5,
            shots_on_target_away=3,
            corners_home=6,
            corners_away=4,
            fouls_home=10,
            fouls_away=14,
        )
        assert stats.possession_home == 58.0
        assert stats.shots_on_target_away == 3

    def test_all_fields_optional(self):
        stats = MatchStats()
        assert stats.possession_home is None
        assert stats.shots_home is None
        assert stats.corners_home is None

    def test_partial_stats(self):
        stats = MatchStats(possession_home=60.0, possession_away=40.0)
        assert stats.possession_home == 60.0
        assert stats.shots_home is None

    def test_stats_serialization_roundtrip(self):
        stats = MatchStats(
            possession_home=55.0,
            possession_away=45.0,
            shots_home=10,
            shots_away=6,
        )
        data = stats.model_dump()
        restored = MatchStats.model_validate(data)
        assert restored == stats


class TestMatch:
    def _make_kickoff(self):
        return datetime(2026, 3, 27, 15, 0, 0, tzinfo=timezone.utc)

    def test_create_scheduled_match(self):
        match = Match(
            id="espn-12345",
            home_team=Team(name="Arsenal", short_name="ARS"),
            away_team=Team(name="Chelsea", short_name="CHE"),
            home_score=None,
            away_score=None,
            status=MatchStatus.SCHEDULED,
            kickoff=self._make_kickoff(),
            competition="Premier League",
            source="espn",
        )
        assert match.status == MatchStatus.SCHEDULED
        assert match.home_score is None
        assert match.events == []
        assert match.stats is None
        assert match.match_clock is None

    def test_create_live_match(self):
        match = Match(
            id="espn-12345",
            home_team=Team(name="Arsenal", short_name="ARS"),
            away_team=Team(name="Chelsea", short_name="CHE"),
            home_score=2,
            away_score=1,
            status=MatchStatus.FIRST_HALF,
            match_clock="34'",
            kickoff=self._make_kickoff(),
            competition="Premier League",
            events=[
                MatchEvent(type=EventType.GOAL, minute=12, player_name="Saka", is_home=True),
                MatchEvent(type=EventType.GOAL, minute=23, player_name="Palmer", is_home=False),
                MatchEvent(type=EventType.GOAL, minute=30, player_name="Havertz", is_home=True),
            ],
            stats=MatchStats(possession_home=58.0, possession_away=42.0),
            source="espn",
        )
        assert match.home_score == 2
        assert match.away_score == 1
        assert len(match.events) == 3
        assert match.stats.possession_home == 58.0

    def test_create_finished_match(self):
        match = Match(
            id="espn-12345",
            home_team=Team(name="Arsenal", short_name="ARS"),
            away_team=Team(name="Chelsea", short_name="CHE"),
            home_score=3,
            away_score=1,
            status=MatchStatus.FINISHED,
            kickoff=self._make_kickoff(),
            competition="Premier League",
            source="espn",
        )
        assert match.status == MatchStatus.FINISHED

    def test_create_postponed_match(self):
        match = Match(
            id="espn-12345",
            home_team=Team(name="Crystal Palace"),
            away_team=Team(name="Manchester City"),
            home_score=None,
            away_score=None,
            status=MatchStatus.POSTPONED,
            kickoff=self._make_kickoff(),
            competition="Premier League",
            source="espn",
        )
        assert match.status == MatchStatus.POSTPONED

    def test_match_requires_id(self):
        with pytest.raises(Exception):
            Match(
                home_team=Team(name="Arsenal"),
                away_team=Team(name="Chelsea"),
                status=MatchStatus.SCHEDULED,
                kickoff=self._make_kickoff(),
                competition="Premier League",
                source="espn",
            )

    def test_match_requires_teams(self):
        with pytest.raises(Exception):
            Match(
                id="test",
                status=MatchStatus.SCHEDULED,
                kickoff=self._make_kickoff(),
                competition="Premier League",
                source="espn",
            )

    def test_match_default_empty_events(self):
        match = Match(
            id="test",
            home_team=Team(name="Arsenal"),
            away_team=Team(name="Chelsea"),
            status=MatchStatus.SCHEDULED,
            kickoff=self._make_kickoff(),
            competition="Premier League",
            source="espn",
        )
        assert match.events == []
        assert match.stats is None
        assert match.source_match_ids == {}

    def test_match_source_match_ids(self):
        match = Match(
            id="espn-12345",
            home_team=Team(name="Arsenal"),
            away_team=Team(name="Chelsea"),
            status=MatchStatus.SCHEDULED,
            kickoff=self._make_kickoff(),
            competition="Premier League",
            source="espn",
            source_match_ids={"espn": "12345", "sofascore": "67890"},
        )
        assert match.source_match_ids["sofascore"] == "67890"

    def test_match_last_updated_auto(self):
        match = Match(
            id="test",
            home_team=Team(name="Arsenal"),
            away_team=Team(name="Chelsea"),
            status=MatchStatus.SCHEDULED,
            kickoff=self._make_kickoff(),
            competition="Premier League",
            source="espn",
        )
        assert match.last_updated is not None
        assert isinstance(match.last_updated, datetime)

    def test_match_serialization_roundtrip(self):
        match = Match(
            id="espn-12345",
            home_team=Team(name="Arsenal", short_name="ARS"),
            away_team=Team(name="Chelsea", short_name="CHE"),
            home_score=2,
            away_score=1,
            status=MatchStatus.FIRST_HALF,
            match_clock="34'",
            kickoff=self._make_kickoff(),
            competition="Premier League",
            events=[
                MatchEvent(type=EventType.GOAL, minute=12, player_name="Saka", is_home=True),
            ],
            stats=MatchStats(possession_home=58.0, possession_away=42.0),
            source="espn",
            source_match_ids={"espn": "12345"},
        )
        data = match.model_dump(mode="json")
        restored = Match.model_validate(data)
        assert restored.id == match.id
        assert restored.home_score == match.home_score
        assert restored.events[0].player_name == "Saka"
        assert restored.stats.possession_home == 58.0

    def test_match_to_json(self):
        match = Match(
            id="test",
            home_team=Team(name="Arsenal"),
            away_team=Team(name="Chelsea"),
            status=MatchStatus.SCHEDULED,
            kickoff=self._make_kickoff(),
            competition="Premier League",
            source="espn",
        )
        json_str = match.model_dump_json()
        assert "Arsenal" in json_str
        assert "SCHEDULED" in json_str
