"""Unit tests for the Circuit Breaker resilience state machine."""

import asyncio
import pytest
from crawler.domain.enums import CircuitState
from crawler.resilience.circuit_breaker import DomainCircuitBreaker


@pytest.mark.asyncio
async def test_circuit_breaker_transitions():
    cb = DomainCircuitBreaker(
        domain="example.com",
        failure_threshold=3,
        recovery_timeout=0.1,  # Short timeout for quick testing
        half_open_success_threshold=2,
    )

    # Initial state is CLOSED
    assert cb.state == CircuitState.CLOSED
    assert await cb.can_execute()

    # Failures 1 and 2
    await cb.record_failure("Error 1")
    await cb.record_failure("Error 2")
    assert cb.state == CircuitState.CLOSED
    assert await cb.can_execute()

    # Failure 3 trips breaker to OPEN
    await cb.record_failure("Error 3")
    assert cb.state == CircuitState.OPEN
    assert not await cb.can_execute()

    # Wait for recovery timeout to pass
    await asyncio.sleep(0.15)

    # Should transition to HALF_OPEN on next execution query
    assert await cb.can_execute()
    assert cb.state == CircuitState.HALF_OPEN

    # First success in HALF_OPEN (needs 2)
    await cb.record_success()
    assert cb.state == CircuitState.HALF_OPEN

    # Second success recovers to CLOSED
    await cb.record_success()
    assert cb.state == CircuitState.CLOSED
    assert cb.consecutive_failures == 0
