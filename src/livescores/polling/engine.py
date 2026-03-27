import asyncio
import logging
import time
from collections.abc import Callable, Coroutine
from datetime import date
from typing import Any

from livescores.config import AppConfig
from livescores.polling.scheduler import MatchScheduler
from livescores.state import MatchDiff, MatchState

logger = logging.getLogger(__name__)

CIRCUIT_BREAKER_THRESHOLD = 5
CIRCUIT_BREAKER_COOLDOWN = 60  # seconds


class PollingEngine:
    def __init__(
        self,
        state: MatchState,
        sources: list[Any],
        broadcast_fn: Callable[[MatchDiff], Coroutine] | None = None,
        config: AppConfig | None = None,
    ) -> None:
        self.state = state
        self.sources = sources
        self.broadcast_fn = broadcast_fn
        self.config = config
        self.scheduler = MatchScheduler()
        self._running = False

        # Circuit breaker state: source_name -> (consecutive_failures, demoted_at_timestamp)
        self._breaker: dict[str, tuple[int, float | None]] = {}

    def is_source_demoted(self, source_name: str) -> bool:
        failures, demoted_at = self._breaker.get(source_name, (0, None))
        if demoted_at is None:
            return False
        elapsed = time.monotonic() - demoted_at
        if elapsed >= CIRCUIT_BREAKER_COOLDOWN:
            # Cooldown expired, reset
            self._breaker[source_name] = (0, None)
            return False
        return True

    def reset_circuit_breaker(self, source_name: str) -> None:
        self._breaker[source_name] = (0, None)

    def _record_failure(self, source_name: str) -> None:
        failures, demoted_at = self._breaker.get(source_name, (0, None))
        failures += 1
        if failures >= CIRCUIT_BREAKER_THRESHOLD:
            self._breaker[source_name] = (failures, time.monotonic())
            logger.warning("Circuit breaker tripped for %s after %d failures", source_name, failures)
        else:
            self._breaker[source_name] = (failures, demoted_at)

    def _record_success(self, source_name: str) -> None:
        self._breaker[source_name] = (0, None)

    async def poll_once(self) -> None:
        """Execute a single poll cycle: fetch from sources, update state, broadcast changes."""
        for source in self.sources:
            source_name = getattr(source, "name", "unknown")

            if self.is_source_demoted(source_name):
                logger.debug("Skipping demoted source: %s", source_name)
                continue

            try:
                leagues = self.config.leagues.tracked if self.config else ["premier_league", "laliga", "international_friendly"]
                today = date.today()
                matches = await source.get_schedule(today, leagues)

                for match in matches:
                    diff = await self.state.update(match)
                    if diff is not None and self.broadcast_fn is not None:
                        await self.broadcast_fn(diff)

                self._record_success(source_name)
                # Primary source succeeded, no need to try fallbacks
                return
            except Exception:
                logger.exception("Source %s failed during poll", source_name)
                self._record_failure(source_name)
                continue

    async def run(self) -> None:
        """Run the polling loop until stopped."""
        self._running = True
        logger.info("Polling engine started")

        while self._running:
            try:
                all_matches = self.state.get_all()
                in_window = self.scheduler.is_active_window(all_matches)

                if in_window or not all_matches:
                    await self.poll_once()

                interval = self.scheduler.get_poll_interval(self.state.get_all())
                await asyncio.sleep(interval)
            except asyncio.CancelledError:
                break
            except Exception:
                logger.exception("Polling loop error")
                await asyncio.sleep(30)

        logger.info("Polling engine stopped")

    async def stop(self) -> None:
        """Stop the polling loop."""
        self._running = False
