from abc import ABC, abstractmethod
from datetime import date

from livescores.models import Match


class FootballSource(ABC):
    name: str

    @abstractmethod
    async def get_schedule(self, target_date: date, leagues: list[str]) -> list[Match]:
        """Fetch the match schedule for a given date and list of league keys."""

    @abstractmethod
    async def get_match_detail(self, match_id: str) -> Match:
        """Fetch full match detail including events and stats."""
