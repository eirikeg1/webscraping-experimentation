import asyncio
from dataclasses import dataclass

from livescores.models import Match


@dataclass
class MatchDiff:
    match: Match
    score_changed: bool = False
    status_changed: bool = False
    events_changed: bool = False

    def to_dict(self) -> dict:
        return {
            "match": self.match.model_dump(mode="json"),
            "score_changed": self.score_changed,
            "status_changed": self.status_changed,
            "events_changed": self.events_changed,
        }


class MatchState:
    def __init__(self) -> None:
        self._matches: dict[str, Match] = {}
        self._lock = asyncio.Lock()

    async def update(self, match: Match) -> MatchDiff | None:
        """Update a match in the store. Returns a diff if anything changed, None otherwise."""
        async with self._lock:
            existing = self._matches.get(match.id)

            if existing is None:
                self._matches[match.id] = match
                return MatchDiff(match=match, score_changed=True, status_changed=True, events_changed=bool(match.events))

            score_changed = (existing.home_score != match.home_score or existing.away_score != match.away_score)
            status_changed = existing.status != match.status
            events_changed = len(existing.events) != len(match.events)

            # Always update and broadcast for live matches (clock is always ticking)
            is_live = match.status.is_live

            if not score_changed and not status_changed and not events_changed and not is_live:
                return None

            self._matches[match.id] = match
            return MatchDiff(
                match=match,
                score_changed=score_changed,
                status_changed=status_changed,
                events_changed=events_changed,
            )

    def get(self, match_id: str) -> Match | None:
        return self._matches.get(match_id)

    def get_all(self) -> list[Match]:
        return sorted(self._matches.values(), key=lambda m: m.kickoff)

    def get_live(self) -> list[Match]:
        return [m for m in self._matches.values() if m.status.is_live]

    def get_by_competition(self) -> dict[str, list[Match]]:
        result: dict[str, list[Match]] = {}
        for match in sorted(self._matches.values(), key=lambda m: m.kickoff):
            result.setdefault(match.competition, []).append(match)
        return result

    def get_all_serialized(self) -> list[dict]:
        return [m.model_dump(mode="json") for m in self.get_all()]
