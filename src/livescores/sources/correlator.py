"""Cross-source match correlation."""

import logging
from datetime import timedelta

from livescores.models import Match
from livescores.utils.team_names import are_same_team

logger = logging.getLogger(__name__)

MAX_KICKOFF_DIFF = timedelta(minutes=5)


def correlate_matches(
    primary: list[Match],
    secondary: list[Match],
) -> None:
    """Correlate matches between primary and secondary sources.

    Mutates primary matches in-place by adding source_match_ids from secondary.
    """
    if not primary or not secondary:
        return

    # For each secondary match, extract source name and match ID
    if not secondary:
        return
    secondary_source = secondary[0].source

    used_secondary: set[int] = set()

    for p_match in primary:
        for i, s_match in enumerate(secondary):
            if i in used_secondary:
                continue

            # Check kickoff time
            kickoff_diff = abs(p_match.kickoff - s_match.kickoff)
            if kickoff_diff > MAX_KICKOFF_DIFF:
                continue

            # Check team names
            home_match = are_same_team(p_match.home_team.name, s_match.home_team.name)
            away_match = are_same_team(p_match.away_team.name, s_match.away_team.name)

            if home_match and away_match:
                # Found correlation
                s_id = s_match.source_match_ids.get(secondary_source, "")
                if s_id:
                    p_match.source_match_ids[secondary_source] = s_id
                used_secondary.add(i)
                logger.debug(
                    "Correlated %s ↔ %s (%s vs %s)",
                    p_match.id, s_match.id,
                    p_match.home_team.name, p_match.away_team.name,
                )
                break
