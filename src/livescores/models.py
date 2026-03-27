from datetime import datetime, timezone
from enum import Enum

from pydantic import BaseModel, Field


class MatchStatus(str, Enum):
    SCHEDULED = "SCHEDULED"
    FIRST_HALF = "1H"
    HALFTIME = "HT"
    SECOND_HALF = "2H"
    EXTRA_TIME = "ET"
    PENALTIES = "PEN"
    FINISHED = "FT"
    POSTPONED = "PPD"
    CANCELLED = "CAN"

    @property
    def is_live(self) -> bool:
        return self in {
            MatchStatus.FIRST_HALF,
            MatchStatus.SECOND_HALF,
            MatchStatus.EXTRA_TIME,
            MatchStatus.PENALTIES,
        }


class EventType(str, Enum):
    GOAL = "goal"
    OWN_GOAL = "own_goal"
    PENALTY_GOAL = "penalty_goal"
    YELLOW_CARD = "yellow_card"
    RED_CARD = "red_card"
    SECOND_YELLOW = "second_yellow"
    SUBSTITUTION = "substitution"


class Team(BaseModel):
    name: str
    short_name: str | None = None
    source_ids: dict[str, str] = Field(default_factory=dict)


class MatchEvent(BaseModel):
    type: EventType
    minute: int
    added_time: int | None = None
    player_name: str | None = None
    assist_name: str | None = None
    player_in: str | None = None
    player_out: str | None = None
    is_home: bool


class MatchStats(BaseModel):
    possession_home: float | None = None
    possession_away: float | None = None
    shots_home: int | None = None
    shots_away: int | None = None
    shots_on_target_home: int | None = None
    shots_on_target_away: int | None = None
    corners_home: int | None = None
    corners_away: int | None = None
    fouls_home: int | None = None
    fouls_away: int | None = None


class Match(BaseModel):
    id: str
    home_team: Team
    away_team: Team
    home_score: int | None = None
    away_score: int | None = None
    status: MatchStatus
    match_clock: str | None = None
    kickoff: datetime
    competition: str
    events: list[MatchEvent] = Field(default_factory=list)
    stats: MatchStats | None = None
    source: str
    source_match_ids: dict[str, str] = Field(default_factory=dict)
    last_updated: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
