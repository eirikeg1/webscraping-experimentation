"""Tests for team name normalization and matching. Written before implementation."""

from livescores.utils.team_names import normalize_name, are_same_team


class TestNormalizeName:
    def test_exact_name(self):
        assert normalize_name("Arsenal") == "arsenal"

    def test_strip_fc_suffix(self):
        assert normalize_name("Arsenal FC") == "arsenal"

    def test_strip_cf_suffix(self):
        assert normalize_name("Valencia CF") == "valencia"

    def test_strip_sc_suffix(self):
        assert normalize_name("Sporting SC") == "sporting"

    def test_case_insensitive(self):
        assert normalize_name("ARSENAL") == "arsenal"

    def test_strip_whitespace(self):
        assert normalize_name("  Arsenal  ") == "arsenal"

    def test_strip_accents(self):
        # Atlético → atletico
        assert normalize_name("Atlético") == "atletico"

    def test_strip_multiple_suffixes(self):
        assert normalize_name("Real Sociedad FC") == "real sociedad"


class TestAreSameTeam:
    # Exact matches
    def test_exact_match(self):
        assert are_same_team("Arsenal", "Arsenal")

    def test_case_insensitive_match(self):
        assert are_same_team("Arsenal", "arsenal")

    def test_with_suffix_difference(self):
        assert are_same_team("Arsenal", "Arsenal FC")

    # Known alias matches
    def test_alias_man_utd(self):
        assert are_same_team("Manchester United", "Man Utd")

    def test_alias_man_utd_reverse(self):
        assert are_same_team("Man Utd", "Manchester United")

    def test_alias_man_city(self):
        assert are_same_team("Manchester City", "Man City")

    def test_alias_atletico_madrid(self):
        assert are_same_team("Atletico Madrid", "Atlético de Madrid")

    def test_alias_atletico_short(self):
        assert are_same_team("Atletico Madrid", "Atl. Madrid")

    def test_alias_wolves(self):
        assert are_same_team("Wolverhampton Wanderers", "Wolves")

    def test_alias_real_betis(self):
        assert are_same_team("Real Betis", "Real Betis Balompié")

    def test_alias_spurs(self):
        assert are_same_team("Tottenham Hotspur", "Spurs")

    def test_alias_brighton(self):
        assert are_same_team("Brighton and Hove Albion", "Brighton")

    def test_alias_west_ham(self):
        assert are_same_team("West Ham United", "West Ham")

    def test_alias_newcastle(self):
        assert are_same_team("Newcastle United", "Newcastle")

    def test_alias_nottingham(self):
        assert are_same_team("Nottingham Forest", "Nott'm Forest")

    def test_alias_real_sociedad(self):
        assert are_same_team("Real Sociedad", "Real Sociedad de Fútbol")

    # Non-matches
    def test_different_teams(self):
        assert not are_same_team("Arsenal", "Chelsea")

    def test_completely_unrelated(self):
        assert not are_same_team("Arsenal", "Barcelona")

    def test_similar_but_different(self):
        assert not are_same_team("Manchester United", "Manchester City")

    def test_empty_strings(self):
        assert not are_same_team("", "Arsenal")

    # Fuzzy matching for close variants
    def test_fuzzy_close_variant(self):
        assert are_same_team("Athletic Bilbao", "Athletic Club Bilbao")

    def test_fuzzy_espanyol(self):
        assert are_same_team("Espanyol", "RCD Espanyol")
