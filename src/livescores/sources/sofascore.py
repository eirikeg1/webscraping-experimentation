import logging
from datetime import date, datetime, timezone


from livescores.models import (
    EventType,
    Match,
    MatchEvent,
    MatchStats,
    MatchStatus,
    Team,
)
from livescores.sources.base import FootballSource
from livescores.utils.http import get_client

logger = logging.getLogger(__name__)

BASE_URL = "https://api.sofascore.com/api/v1"

# SofaScore status code -> MatchStatus
_STATUS_MAP: dict[int, MatchStatus] = {
    0: MatchStatus.SCHEDULED,
    6: MatchStatus.FIRST_HALF,
    7: MatchStatus.SECOND_HALF,
    20: MatchStatus.FIRST_HALF,  # "Started" - treat as 1H
    31: MatchStatus.HALFTIME,
    100: MatchStatus.FINISHED,
    120: MatchStatus.FINISHED,  # "AP" (after penalties) = finished
    70: MatchStatus.CANCELLED,
    80: MatchStatus.POSTPONED,
}

# SofaScore incident type/class -> EventType
_GOAL_CLASS_MAP: dict[str, EventType] = {
    "regular": EventType.GOAL,
    "ownGoal": EventType.OWN_GOAL,
    "penalty": EventType.PENALTY_GOAL,
}

_CARD_CLASS_MAP: dict[str, EventType] = {
    "yellow": EventType.YELLOW_CARD,
    "red": EventType.RED_CARD,
    "yellowRed": EventType.SECOND_YELLOW,
}

# SofaScore stat keys we care about
_STAT_KEY_MAP = {
    "ballPossession": "possession",
    "totalShotsOnGoal": "shots",
    "shotsOnGoal": "shots_on_target",
    "wonCorners": "corners",
    "fouls": "fouls",
}


def _parse_team(team_data: dict) -> Team:
    return Team(
        name=team_data.get("name", "Unknown"),
        short_name=team_data.get("nameCode"),
        source_ids={"sofascore": str(team_data.get("id", ""))},
    )


def _parse_match(event: dict) -> Match:
    """Parse a single SofaScore event into a Match."""
    status_code = event.get("status", {}).get("code", 0)
    match_status = _STATUS_MAP.get(status_code, MatchStatus.SCHEDULED)

    home_team = _parse_team(event.get("homeTeam", {}))
    away_team = _parse_team(event.get("awayTeam", {}))

    # Scores
    home_score_data = event.get("homeScore", {})
    away_score_data = event.get("awayScore", {})

    if match_status in (MatchStatus.SCHEDULED, MatchStatus.CANCELLED, MatchStatus.POSTPONED):
        home_score = None
        away_score = None
    else:
        home_score = home_score_data.get("current")
        away_score = away_score_data.get("current")

    # Kickoff from startTimestamp
    start_ts = event.get("startTimestamp", 0)
    kickoff = datetime.fromtimestamp(start_ts, tz=timezone.utc)

    # Competition name
    tournament = event.get("tournament", {})
    competition = tournament.get("name", "")

    event_id = str(event.get("id", ""))

    return Match(
        id=f"sofascore-{event_id}",
        home_team=home_team,
        away_team=away_team,
        home_score=home_score,
        away_score=away_score,
        status=match_status,
        kickoff=kickoff,
        competition=competition,
        source="sofascore",
        source_match_ids={"sofascore": event_id},
    )


class SofaScoreSource(FootballSource):
    name = "sofascore"

    def parse_events_response(self, data: dict) -> list[Match]:
        """Parse a SofaScore events response into Match objects."""
        matches = []
        for event in data.get("events", []):
            try:
                matches.append(_parse_match(event))
            except Exception:
                logger.exception("Failed to parse SofaScore event: %s", event.get("id"))
        return matches

    def parse_incidents(self, data: dict) -> list[MatchEvent]:
        """Parse SofaScore incidents into MatchEvents."""
        events = []
        for incident in data.get("incidents", []):
            inc_type = incident.get("incidentType", "")

            if inc_type == "goal":
                inc_class = incident.get("incidentClass", "regular")
                event_type = _GOAL_CLASS_MAP.get(inc_class, EventType.GOAL)
                player = incident.get("player", {})
                events.append(MatchEvent(
                    type=event_type,
                    minute=incident.get("time", 0),
                    added_time=incident.get("addedTime"),
                    player_name=player.get("name"),
                    is_home=incident.get("isHome", True),
                ))

            elif inc_type == "card":
                inc_class = incident.get("incidentClass", "yellow")
                event_type = _CARD_CLASS_MAP.get(inc_class, EventType.YELLOW_CARD)
                player = incident.get("player", {})
                events.append(MatchEvent(
                    type=event_type,
                    minute=incident.get("time", 0),
                    added_time=incident.get("addedTime"),
                    player_name=player.get("name"),
                    is_home=incident.get("isHome", True),
                ))

            elif inc_type == "substitution":
                player_in = incident.get("playerIn", {})
                player_out = incident.get("playerOut", {})
                events.append(MatchEvent(
                    type=EventType.SUBSTITUTION,
                    minute=incident.get("time", 0),
                    added_time=incident.get("addedTime"),
                    player_in=player_in.get("name"),
                    player_out=player_out.get("name"),
                    is_home=incident.get("isHome", True),
                ))

            # Skip period markers and other types

        return events

    def parse_statistics(self, data: dict) -> MatchStats | None:
        """Parse SofaScore statistics response."""
        stats_list = data.get("statistics", [])
        if not stats_list:
            return None

        # Use the "ALL" period (first entry) or whatever is available
        all_stats = stats_list[0]
        flat: dict[str, tuple[int | None, int | None]] = {}

        for group in all_stats.get("groups", []):
            for item in group.get("statisticsItems", []):
                key = item.get("key", "")
                flat[key] = (item.get("homeValue"), item.get("awayValue"))

        if not flat:
            return None

        poss = flat.get("ballPossession", (None, None))
        shots = flat.get("totalShotsOnGoal", (None, None))
        on_target = flat.get("shotsOnGoal", (None, None))
        corners = flat.get("wonCorners", (None, None))
        fouls = flat.get("fouls", (None, None))

        return MatchStats(
            possession_home=float(poss[0]) if poss[0] is not None else None,
            possession_away=float(poss[1]) if poss[1] is not None else None,
            shots_home=shots[0],
            shots_away=shots[1],
            shots_on_target_home=on_target[0],
            shots_on_target_away=on_target[1],
            corners_home=corners[0],
            corners_away=corners[1],
            fouls_home=fouls[0],
            fouls_away=fouls[1],
        )

    async def get_schedule(self, target_date: date, leagues: list[str]) -> list[Match]:
        """Fetch all scheduled events for a date from SofaScore."""
        client = await get_client()
        date_str = target_date.isoformat()
        url = f"{BASE_URL}/sport/football/scheduled-events/{date_str}"

        response = await client.get(url)
        response.raise_for_status()
        data = response.json()

        return self.parse_events_response(data)

    async def get_match_detail(self, match_id: str) -> Match:
        """Fetch full match detail including events and stats."""
        client = await get_client()

        # Fetch event detail
        url = f"{BASE_URL}/event/{match_id}"
        response = await client.get(url)
        response.raise_for_status()
        event_data = response.json()

        match = _parse_match(event_data.get("event", event_data))

        # Fetch incidents
        try:
            inc_url = f"{BASE_URL}/event/{match_id}/incidents"
            inc_response = await client.get(inc_url)
            if inc_response.status_code == 200:
                match.events = self.parse_incidents(inc_response.json())
        except Exception:
            logger.debug("Failed to fetch incidents for %s", match_id)

        # Fetch statistics
        try:
            stats_url = f"{BASE_URL}/event/{match_id}/statistics"
            stats_response = await client.get(stats_url)
            if stats_response.status_code == 200:
                match.stats = self.parse_statistics(stats_response.json())
        except Exception:
            logger.debug("Failed to fetch statistics for %s", match_id)

        return match
