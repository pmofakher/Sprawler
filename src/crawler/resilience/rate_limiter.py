"""Rate limiting and politeness delay manager."""

import asyncio
import time
from typing import Dict


class DomainRateLimiter:
    """Enforces per-domain politeness delay and request throttling."""

    def __init__(self, default_delay: float = 0.5):
        self.default_delay = default_delay
        self._domain_delays: Dict[str, float] = {}
        self._last_request_times: Dict[str, float] = {}
        self._locks: Dict[str, asyncio.Lock] = {}
        self._global_lock = asyncio.Lock()

    def set_domain_delay(self, domain: str, delay: float) -> None:
        """Sets a domain-specific crawl-delay (e.g. parsed from robots.txt)."""
        self._domain_delays[domain] = max(self.default_delay, delay)

    async def _get_domain_lock(self, domain: str) -> asyncio.Lock:
        async with self._global_lock:
            if domain not in self._locks:
                self._locks[domain] = asyncio.Lock()
            return self._locks[domain]

    async def wait(self, domain: str) -> None:
        """Pauses the calling coroutine until the required politeness interval has elapsed."""
        lock = await self._get_domain_lock(domain)
        async with lock:
            now = time.monotonic()
            delay = self._domain_delays.get(domain, self.default_delay)
            last_time = self._last_request_times.get(domain, 0.0)
            elapsed = now - last_time

            if elapsed < delay:
                sleep_needed = delay - elapsed
                await asyncio.sleep(sleep_needed)

            self._last_request_times[domain] = time.monotonic()
