"""Tests for cross-source match correlation. Written before implementation."""

from datetime import datetime, timezone


from livescores.models import Match, MatchStatus, Team
from livescores.sources.correlator import correlate_matches


def _make_match(
    match_id: str,
    home_name: str,
    away_name: str,
    kickoff: datetime,
    source: str = "espn",
    competition: str = "Premier League",
) -> Match:
    return Match(
        id=f"{source}-{match_id}",
        home_team=Team(name=home_name, source_ids={source: f"h-{match_id}"}),
        away_team=Team(name=away_name, source_ids={source: f"a-{match_id}"}),
        status=MatchStatus.SCHEDULED,
        kickoff=kickoff,
        competition=competition,
        source=source,
        source_match_ids={source: match_id},
    )


class TestCorrelateMatches:
    def test_same_match_correlated(self):
        kickoff = datetime(2026, 3, 27, 15, 0, tzinfo=timezone.utc)
        primary = [_make_match("1", "Arsenal", "Chelsea", kickoff, "espn")]
        secondary = [_make_match("99", "Arsenal", "Chelsea", kickoff, "sofascore")]

        correlate_matches(primary, secondary)

        assert "sofascore" in primary[0].source_match_ids
        assert primary[0].source_match_ids["sofascore"] == "99"

    def test_slight_kickoff_difference(self):
        # 1 minute difference should still correlate
        espn_kickoff = datetime(2026, 3, 27, 15, 0, tzinfo=timezone.utc)
        sofa_kickoff = datetime(2026, 3, 27, 15, 1, tzinfo=timezone.utc)
        primary = [_make_match("1", "Arsenal", "Chelsea", espn_kickoff, "espn")]
        secondary = [_make_match("99", "Arsenal", "Chelsea", sofa_kickoff, "sofascore")]

        correlate_matches(primary, secondary)

        assert "sofascore" in primary[0].source_match_ids

    def test_different_team_name_formats(self):
        kickoff = datetime(2026, 3, 27, 20, 0, tzinfo=timezone.utc)
        primary = [_make_match("1", "Atletico Madrid", "Real Madrid", kickoff, "espn")]
        secondary = [_make_match("99", "Atlético de Madrid", "Real Madrid CF", kickoff, "sofascore")]

        correlate_matches(primary, secondary)

        assert "sofascore" in primary[0].source_match_ids

    def test_unrelated_matches_not_correlated(self):
        kickoff = datetime(2026, 3, 27, 15, 0, tzinfo=timezone.utc)
        primary = [_make_match("1", "Arsenal", "Chelsea", kickoff, "espn")]
        secondary = [_make_match("99", "Liverpool", "Man City", kickoff, "sofascore")]

        correlate_matches(primary, secondary)

        assert "sofascore" not in primary[0].source_match_ids

    def test_one_source_has_extra_match(self):
        kickoff = datetime(2026, 3, 27, 15, 0, tzinfo=timezone.utc)
        primary = [
            _make_match("1", "Arsenal", "Chelsea", kickoff, "espn"),
            _make_match("2", "Liverpool", "Man City", kickoff, "espn"),
        ]
        # Secondary only has Arsenal match
        secondary = [_make_match("99", "Arsenal", "Chelsea", kickoff, "sofascore")]

        correlate_matches(primary, secondary)

        assert "sofascore" in primary[0].source_match_ids
        assert "sofascore" not in primary[1].source_match_ids

    def test_multiple_matches_all_correlated(self):
        k1 = datetime(2026, 3, 27, 15, 0, tzinfo=timezone.utc)
        k2 = datetime(2026, 3, 27, 17, 30, tzinfo=timezone.utc)
        primary = [
            _make_match("1", "Arsenal", "Chelsea", k1, "espn"),
            _make_match("2", "Barcelona", "Real Madrid", k2, "espn"),
        ]
        secondary = [
            _make_match("88", "FC Barcelona", "Real Madrid CF", k2, "sofascore"),
            _make_match("99", "Arsenal", "Chelsea", k1, "sofascore"),
        ]

        correlate_matches(primary, secondary)

        assert primary[0].source_match_ids.get("sofascore") == "99"
        assert primary[1].source_match_ids.get("sofascore") == "88"

    def test_large_kickoff_difference_no_correlation(self):
        # 30 minute difference — too big
        primary = [_make_match("1", "Arsenal", "Chelsea",
                               datetime(2026, 3, 27, 15, 0, tzinfo=timezone.utc), "espn")]
        secondary = [_make_match("99", "Arsenal", "Chelsea",
                                 datetime(2026, 3, 27, 15, 30, tzinfo=timezone.utc), "sofascore")]

        correlate_matches(primary, secondary)

        assert "sofascore" not in primary[0].source_match_ids

    def test_empty_secondary_no_error(self):
        kickoff = datetime(2026, 3, 27, 15, 0, tzinfo=timezone.utc)
        primary = [_make_match("1", "Arsenal", "Chelsea", kickoff, "espn")]

        correlate_matches(primary, [])

        assert "sofascore" not in primary[0].source_match_ids

    def test_empty_primary_no_error(self):
        kickoff = datetime(2026, 3, 27, 15, 0, tzinfo=timezone.utc)
        secondary = [_make_match("99", "Arsenal", "Chelsea", kickoff, "sofascore")]

        correlate_matches([], secondary)
        # Just shouldn't crash
