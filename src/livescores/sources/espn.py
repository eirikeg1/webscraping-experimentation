import logging
from datetime import date, datetime, timezone

import httpx

from livescores.models import (
    EventType,
    Match,
    MatchEvent,
    MatchStats,
    MatchStatus,
    Team,
)
from livescores.sources.base import FootballSource
from livescores.sources.ids import ESPN_LEAGUE_NAMES, ESPN_LEAGUES
from livescores.utils.http import get_client

logger = logging.getLogger(__name__)

BASE_URL = "https://site.api.espn.com/apis/site/v2/sports/soccer"

# ESPN status name -> our MatchStatus
_STATUS_MAP: dict[str, MatchStatus] = {
    "STATUS_SCHEDULED": MatchStatus.SCHEDULED,
    "STATUS_FIRST_HALF": MatchStatus.FIRST_HALF,
    "STATUS_HALFTIME": MatchStatus.HALFTIME,
    "STATUS_SECOND_HALF": MatchStatus.SECOND_HALF,
    "STATUS_FULL_TIME": MatchStatus.FINISHED,
    "STATUS_POSTPONED": MatchStatus.POSTPONED,
    "STATUS_CANCELED": MatchStatus.CANCELLED,
    "STATUS_ABANDONED": MatchStatus.CANCELLED,
    "STATUS_EXTRA_TIME": MatchStatus.EXTRA_TIME,
    "STATUS_PENALTIES": MatchStatus.PENALTIES,
}

# ESPN detail type IDs -> our EventType
_EVENT_TYPE_MAP: dict[str, EventType] = {
    "70": EventType.GOAL,         # Goal
    "137": EventType.GOAL,        # Goal - Header
    "94": EventType.YELLOW_CARD,  # Yellow Card
    "93": EventType.RED_CARD,     # Red Card
    "98": EventType.PENALTY_GOAL, # Penalty - Scored
}

# ESPN stat names we care about
_STAT_NAMES = {
    "possessionPct", "totalShots", "shotsOnTarget",
    "wonCorners", "foulsCommitted",
}


def _parse_status(status_data: dict) -> tuple[MatchStatus, str | None]:
    """Parse ESPN status into MatchStatus and optional clock string."""
    type_data = status_data.get("type", {})
    status_name = type_data.get("name", "")
    match_status = _STATUS_MAP.get(status_name, MatchStatus.SCHEDULED)

    clock = None
    if match_status.is_live:
        clock = status_data.get("displayClock")
    elif match_status == MatchStatus.FINISHED:
        clock = type_data.get("shortDetail", "FT")

    return match_status, clock


def _parse_team(competitor: dict) -> Team:
    """Parse an ESPN competitor into a Team."""
    team_data = competitor.get("team", {})
    return Team(
        name=team_data.get("displayName", "Unknown"),
        short_name=team_data.get("abbreviation"),
        source_ids={"espn": str(team_data.get("id", ""))},
    )


def _parse_events(details: list[dict], home_team_id: str) -> list[MatchEvent]:
    """Parse ESPN match details into MatchEvents."""
    events = []
    for detail in details:
        type_data = detail.get("type", {})
        type_id = type_data.get("id", "")

        event_type = _EVENT_TYPE_MAP.get(type_id)
        if event_type is None:
            continue

        # Handle own goals
        if detail.get("ownGoal"):
            event_type = EventType.OWN_GOAL

        # Parse minute from clock
        clock_data = detail.get("clock", {})
        display = clock_data.get("displayValue", "0'")
        minute, added_time = _parse_clock_display(display)

        # Get player name
        athletes = detail.get("athletesInvolved", [])
        player_name = athletes[0].get("shortName") if athletes else None

        # Determine home/away
        detail_team_id = str(detail.get("team", {}).get("id", ""))
        is_home = detail_team_id == home_team_id

        events.append(MatchEvent(
            type=event_type,
            minute=minute,
            added_time=added_time,
            player_name=player_name,
            is_home=is_home,
        ))

    return events


def _parse_clock_display(display: str) -> tuple[int, int | None]:
    """Parse '45\'+2\\'' into (45, 2) or '14\\'' into (14, None)."""
    display = display.replace("'", "").strip()
    if "+" in display:
        parts = display.split("+")
        return int(parts[0]), int(parts[1])
    try:
        return int(display), None
    except ValueError:
        return 0, None


def _parse_stats(home_comp: dict, away_comp: dict) -> MatchStats | None:
    """Parse statistics from both competitors."""
    home_stats = {s["name"]: s["displayValue"] for s in home_comp.get("statistics", [])}
    away_stats = {s["name"]: s["displayValue"] for s in away_comp.get("statistics", [])}

    if not home_stats and not away_stats:
        return None

    def _get_int(stats: dict, key: str) -> int | None:
        val = stats.get(key)
        if val is None:
            return None
        try:
            return int(val)
        except ValueError:
            return None

    def _get_float(stats: dict, key: str) -> float | None:
        val = stats.get(key)
        if val is None:
            return None
        try:
            return float(val)
        except ValueError:
            return None

    return MatchStats(
        possession_home=_get_float(home_stats, "possessionPct"),
        possession_away=_get_float(away_stats, "possessionPct"),
        shots_home=_get_int(home_stats, "totalShots"),
        shots_away=_get_int(away_stats, "totalShots"),
        shots_on_target_home=_get_int(home_stats, "shotsOnTarget"),
        shots_on_target_away=_get_int(away_stats, "shotsOnTarget"),
        corners_home=_get_int(home_stats, "wonCorners"),
        corners_away=_get_int(away_stats, "wonCorners"),
        fouls_home=_get_int(home_stats, "foulsCommitted"),
        fouls_away=_get_int(away_stats, "foulsCommitted"),
    )


def _parse_match(event: dict) -> Match:
    """Parse a single ESPN event into a Match."""
    competition = event.get("competitions", [{}])[0]
    competitors = competition.get("competitors", [])

    home_comp = next((c for c in competitors if c.get("homeAway") == "home"), competitors[0])
    away_comp = next((c for c in competitors if c.get("homeAway") == "away"), competitors[-1])

    home_team = _parse_team(home_comp)
    away_team = _parse_team(away_comp)

    status, clock = _parse_status(event.get("status", {}))

    # Scores: ESPN always provides score as string, even "0" for scheduled
    home_score_str = home_comp.get("score", "0")
    away_score_str = away_comp.get("score", "0")

    if status == MatchStatus.SCHEDULED or status == MatchStatus.POSTPONED:
        home_score = None
        away_score = None
    else:
        home_score = int(home_score_str) if home_score_str else 0
        away_score = int(away_score_str) if away_score_str else 0

    # Parse kickoff
    date_str = event.get("date", "")
    try:
        kickoff = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        kickoff = datetime.now(timezone.utc)

    # Parse events
    details = competition.get("details", [])
    home_team_id = str(home_comp.get("team", {}).get("id", ""))
    events = _parse_events(details, home_team_id)

    # Parse stats
    stats = _parse_stats(home_comp, away_comp)

    # Competition name from the league data
    league_data = event.get("season", {})
    comp_name = league_data.get("displayName", "")
    if not comp_name:
        leagues = event.get("leagues", [])
        if leagues:
            comp_name = leagues[0].get("name", "Unknown")

    event_id = str(event.get("id", ""))

    return Match(
        id=f"espn-{event_id}",
        home_team=home_team,
        away_team=away_team,
        home_score=home_score,
        away_score=away_score,
        status=status,
        match_clock=clock,
        kickoff=kickoff,
        competition=comp_name,
        events=events,
        stats=stats,
        source="espn",
        source_match_ids={"espn": event_id},
    )


class ESPNSource(FootballSource):
    name = "espn"

    async def get_schedule_for_league(
        self, client: httpx.AsyncClient, league_code: str, date_str: str
    ) -> list[Match]:
        """Fetch matches for a single ESPN league code on a given date."""
        url = f"{BASE_URL}/{league_code}/scoreboard"
        params = {"dates": date_str}
        response = await client.get(url, params=params)
        response.raise_for_status()
        data = response.json()

        matches = []
        for event in data.get("events", []):
            try:
                match = _parse_match(event)
                # Set competition name from league data if not set
                if not match.competition:
                    for league in data.get("leagues", []):
                        match.competition = league.get("name", "")
                        break
                matches.append(match)
            except Exception:
                logger.exception("Failed to parse ESPN event: %s", event.get("id"))

        return matches

    async def get_schedule(self, target_date: date, leagues: list[str]) -> list[Match]:
        """Fetch schedule for all requested leagues."""
        client = await get_client()
        date_str = target_date.strftime("%Y%m%d")

        all_matches = []
        for league_key in leagues:
            espn_code = ESPN_LEAGUES.get(league_key)
            if not espn_code:
                logger.warning("Unknown league key for ESPN: %s", league_key)
                continue
            try:
                matches = await self.get_schedule_for_league(client, espn_code, date_str)
                # Set competition name from our registry if empty
                for m in matches:
                    if not m.competition:
                        m.competition = ESPN_LEAGUE_NAMES.get(espn_code, league_key)
                all_matches.extend(matches)
            except httpx.HTTPError:
                logger.exception("Failed to fetch ESPN schedule for %s", league_key)

        return all_matches

    async def get_match_detail(self, match_id: str) -> Match:
        """Fetch full match detail. For ESPN, re-fetch the scoreboard and find the match."""
        # ESPN doesn't have a dedicated match detail endpoint in the public API,
        # so we'd need to know the league. For now, this is a placeholder.
        raise NotImplementedError("ESPN match detail requires league context")
