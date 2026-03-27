import random
from datetime import datetime, timedelta, timezone

from livescores.models import Match
from livescores.utils.team_names import are_same_team

# How long before first kickoff to start polling
PRE_MATCH_BUFFER = timedelta(minutes=15)
# Expected match duration + buffer after last kickoff
POST_MATCH_BUFFER = timedelta(hours=3)
# Upcoming match threshold
UPCOMING_THRESHOLD = timedelta(minutes=15)


class MatchScheduler:
    def is_active_window(self, matches: list[Match], now: datetime | None = None) -> bool:
        """Check if we're in an active polling window based on match schedule."""
        if not matches:
            return False

        now = now or datetime.now(timezone.utc)
        first_kickoff = min(m.kickoff for m in matches)
        last_kickoff = max(m.kickoff for m in matches)

        window_start = first_kickoff - PRE_MATCH_BUFFER
        window_end = last_kickoff + POST_MATCH_BUFFER

        return window_start <= now <= window_end

    def get_poll_interval(
        self, matches: list[Match], now: datetime | None = None
    ) -> float:
        """Determine the appropriate poll interval based on match states."""
        now = now or datetime.now(timezone.utc)

        has_live = any(m.status.is_live for m in matches)
        if has_live:
            return random.uniform(5.0, 10.0)

        has_upcoming = any(
            m.status.value == "SCHEDULED" and (m.kickoff - now) < UPCOMING_THRESHOLD
            for m in matches
        )
        if has_upcoming:
            return random.uniform(25.0, 35.0)

        # No live or imminent matches
        return 300.0  # 5 minutes

    def filter_top_team_matches(
        self, matches: list[Match], top_teams: list[str]
    ) -> list[Match]:
        """Filter matches to only include those involving top teams."""
        result = []
        for match in matches:
            for team_name in top_teams:
                if are_same_team(match.home_team.name, team_name) or are_same_team(
                    match.away_team.name, team_name
                ):
                    result.append(match)
                    break
        return result
