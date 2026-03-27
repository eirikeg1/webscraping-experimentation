"""Tests for schedule-aware polling timing. Written before implementation."""

from datetime import datetime, timezone


from livescores.models import Match, MatchStatus, Team
from livescores.polling.scheduler import MatchScheduler


def _make_match(
    kickoff: datetime,
    status: MatchStatus = MatchStatus.SCHEDULED,
    competition: str = "Premier League",
    home_name: str = "Arsenal",
) -> Match:
    return Match(
        id=f"test-{home_name}",
        home_team=Team(name=home_name),
        away_team=Team(name="Chelsea"),
        status=status,
        kickoff=kickoff,
        competition=competition,
        source="espn",
    )


class TestActiveWindow:
    def test_no_matches_not_active(self):
        scheduler = MatchScheduler()
        now = datetime(2026, 3, 27, 15, 0, tzinfo=timezone.utc)
        assert not scheduler.is_active_window([], now)

    def test_before_active_window(self):
        scheduler = MatchScheduler()
        kickoff = datetime(2026, 3, 27, 15, 0, tzinfo=timezone.utc)
        now = datetime(2026, 3, 27, 14, 44, tzinfo=timezone.utc)  # 16 min before
        matches = [_make_match(kickoff)]
        assert not scheduler.is_active_window(matches, now)

    def test_just_entered_active_window(self):
        scheduler = MatchScheduler()
        kickoff = datetime(2026, 3, 27, 15, 0, tzinfo=timezone.utc)
        now = datetime(2026, 3, 27, 14, 46, tzinfo=timezone.utc)  # 14 min before
        matches = [_make_match(kickoff)]
        assert scheduler.is_active_window(matches, now)

    def test_during_match(self):
        scheduler = MatchScheduler()
        kickoff = datetime(2026, 3, 27, 15, 0, tzinfo=timezone.utc)
        now = datetime(2026, 3, 27, 16, 0, tzinfo=timezone.utc)  # 1 hour into match
        matches = [_make_match(kickoff)]
        assert scheduler.is_active_window(matches, now)

    def test_just_before_window_closes(self):
        scheduler = MatchScheduler()
        kickoff = datetime(2026, 3, 27, 15, 0, tzinfo=timezone.utc)
        # 2.5h match + 30min buffer = 3h after kickoff = 18:00
        now = datetime(2026, 3, 27, 17, 59, tzinfo=timezone.utc)
        matches = [_make_match(kickoff)]
        assert scheduler.is_active_window(matches, now)

    def test_after_window_closes(self):
        scheduler = MatchScheduler()
        kickoff = datetime(2026, 3, 27, 15, 0, tzinfo=timezone.utc)
        now = datetime(2026, 3, 27, 18, 1, tzinfo=timezone.utc)  # 3h + 1min after
        matches = [_make_match(kickoff)]
        assert not scheduler.is_active_window(matches, now)

    def test_multiple_matches_spans_full_window(self):
        scheduler = MatchScheduler()
        kickoff1 = datetime(2026, 3, 27, 13, 0, tzinfo=timezone.utc)
        kickoff2 = datetime(2026, 3, 27, 20, 0, tzinfo=timezone.utc)
        now = datetime(2026, 3, 27, 17, 0, tzinfo=timezone.utc)  # Between matches
        matches = [_make_match(kickoff1, home_name="Team1"), _make_match(kickoff2, home_name="Team2")]
        assert scheduler.is_active_window(matches, now)


class TestPollInterval:
    def test_live_match_short_interval(self):
        scheduler = MatchScheduler()
        live_match = _make_match(
            datetime(2026, 3, 27, 15, 0, tzinfo=timezone.utc),
            status=MatchStatus.FIRST_HALF,
        )
        interval = scheduler.get_poll_interval([live_match])
        assert 5.0 <= interval <= 10.0

    def test_upcoming_match_medium_interval(self):
        scheduler = MatchScheduler()
        upcoming = _make_match(
            datetime(2026, 3, 27, 15, 10, tzinfo=timezone.utc),
            status=MatchStatus.SCHEDULED,
        )
        now = datetime(2026, 3, 27, 15, 0, tzinfo=timezone.utc)
        interval = scheduler.get_poll_interval([upcoming], now=now)
        assert 25.0 <= interval <= 35.0

    def test_no_live_no_upcoming_long_interval(self):
        scheduler = MatchScheduler()
        far_away = _make_match(
            datetime(2026, 3, 27, 20, 0, tzinfo=timezone.utc),
            status=MatchStatus.SCHEDULED,
        )
        now = datetime(2026, 3, 27, 15, 0, tzinfo=timezone.utc)
        interval = scheduler.get_poll_interval([far_away], now=now)
        assert interval >= 60.0


class TestTopTeamFilter:
    def test_top_team_match_included(self):
        scheduler = MatchScheduler()
        match = _make_match(
            datetime(2026, 3, 27, 15, 0, tzinfo=timezone.utc),
            competition="Champions League",
            home_name="Arsenal",
        )
        filtered = scheduler.filter_top_team_matches([match], top_teams=["Arsenal"])
        assert len(filtered) == 1

    def test_non_top_team_cup_match_excluded(self):
        scheduler = MatchScheduler()
        match = _make_match(
            datetime(2026, 3, 27, 15, 0, tzinfo=timezone.utc),
            competition="Champions League",
            home_name="Feyenoord",
        )
        match.away_team = Team(name="PSV")
        filtered = scheduler.filter_top_team_matches([match], top_teams=["Arsenal"])
        assert len(filtered) == 0

    def test_top_team_in_away(self):
        scheduler = MatchScheduler()
        match = _make_match(
            datetime(2026, 3, 27, 15, 0, tzinfo=timezone.utc),
            competition="FA Cup",
            home_name="Luton",
        )
        match.away_team = Team(name="Arsenal")
        filtered = scheduler.filter_top_team_matches([match], top_teams=["Arsenal"])
        assert len(filtered) == 1
