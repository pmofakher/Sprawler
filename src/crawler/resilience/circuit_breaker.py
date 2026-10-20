"""Domain-specific Circuit Breaker state machine (CLOSED -> OPEN -> HALF_OPEN)."""

import asyncio
import time
from typing import Dict, Optional

from crawler.core.exceptions import CircuitBreakerOpenException
from crawler.core.logging import logger
from crawler.domain.enums import CircuitState


class DomainCircuitBreaker:
    """Manages failure counts, cool-down, and state transitions for a single host domain."""

    def __init__(
        self,
        domain: str,
        failure_threshold: int = 5,
        recovery_timeout: float = 60.0,
        half_open_success_threshold: int = 2,
    ):
        self.domain = domain
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.half_open_success_threshold = half_open_success_threshold

        self.state: CircuitState = CircuitState.CLOSED
        self.consecutive_failures: int = 0
        self.consecutive_successes: int = 0
        self.last_failure_time: float = 0.0
        self._lock = asyncio.Lock()

    async def can_execute(self) -> bool:
        """Determines if a request should be allowed through or blocked."""
        async with self._lock:
            now = time.monotonic()

            if self.state == CircuitState.CLOSED:
                return True

            if self.state == CircuitState.OPEN:
                # Check if recovery timeout has passed to attempt trial in HALF_OPEN
                if now - self.last_failure_time >= self.recovery_timeout:
                    self.state = CircuitState.HALF_OPEN
                    self.consecutive_successes = 0
                    logger.info(
                        f"Circuit breaker for {self.domain} transitioning from OPEN to HALF_OPEN",
                        extra={"domain": self.domain},
                    )
                    return True
                return False

            if self.state == CircuitState.HALF_OPEN:
                return True

            return False

    async def record_success(self) -> None:
        """Records a successful operation and resets counters when appropriate."""
        async with self._lock:
            if self.state == CircuitState.HALF_OPEN:
                self.consecutive_successes += 1
                if self.consecutive_successes >= self.half_open_success_threshold:
                    self.state = CircuitState.CLOSED
                    self.consecutive_failures = 0
                    self.consecutive_successes = 0
                    logger.info(
                        f"Circuit breaker for {self.domain} successfully recovered to CLOSED",
                        extra={"domain": self.domain},
                    )
            elif self.state == CircuitState.CLOSED:
                self.consecutive_failures = 0

    async def record_failure(self, error_msg: str = "") -> None:
        """Records a failed operation and trips the breaker if threshold is reached."""
        async with self._lock:
            now = time.monotonic()
            self.last_failure_time = now
            self.consecutive_failures += 1

            if self.state == CircuitState.HALF_OPEN:
                self.state = CircuitState.OPEN
                logger.warning(
                    f"Circuit breaker for {self.domain} failed during HALF_OPEN. Tripping back to OPEN: {error_msg}",
                    extra={"domain": self.domain},
                )
            elif self.state == CircuitState.CLOSED:
                if self.consecutive_failures >= self.failure_threshold:
                    self.state = CircuitState.OPEN
                    logger.error(
                        f"Circuit breaker for {self.domain} tripped to OPEN after {self.consecutive_failures} failures: {error_msg}",
                        extra={"domain": self.domain},
                    )


class CircuitBreakerRegistry:
    """Global manager holding circuit breakers keyed by target domain."""

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: float = 60.0,
        half_open_success_threshold: int = 2,
    ):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.half_open_success_threshold = half_open_success_threshold
        self._breakers: Dict[str, DomainCircuitBreaker] = {}
        self._lock = asyncio.Lock()

    async def get_breaker(self, domain: str) -> DomainCircuitBreaker:
        async with self._lock:
            if domain not in self._breakers:
                self._breakers[domain] = DomainCircuitBreaker(
                    domain=domain,
                    failure_threshold=self.failure_threshold,
                    recovery_timeout=self.recovery_timeout,
                    half_open_success_threshold=self.half_open_success_threshold,
                )
            return self._breakers[domain]
