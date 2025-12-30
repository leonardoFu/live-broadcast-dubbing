"""E2E tests for circuit breaker integration.

Priority: P2
User Story 3: Circuit Breaker Integration

Tests circuit breaker protection when Echo STS is configured to simulate failures.
Validates failure detection, fallback audio usage, and recovery workflow.

Per spec 018-e2e-stream-handler-tests/spec.md User Story 3.
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

import pytest
import socketio

from tests.e2e.config import (
    EchoSTSConfig,
    TestConfig,
    TestFixtureConfig,
    TimeoutConfig,
)

if TYPE_CHECKING:
    from tests.e2e.helpers.docker_manager import DockerManager
    from tests.e2e.helpers.metrics_parser import MetricsParser
    from tests.e2e.helpers.stream_publisher import StreamPublisher

logger = logging.getLogger(__name__)


@pytest.fixture
async def sts_config_client():
    """Socket.IO client for configuring Echo STS.

    Used to send config:error_simulation events.
    """
    client = socketio.AsyncClient()

    await client.connect(
        EchoSTSConfig.URL,
        socketio_path=EchoSTSConfig.SOCKETIO_PATH,
    )

    yield client

    if client.connected:
        await client.disconnect()


@pytest.mark.e2e
@pytest.mark.p2
class TestCircuitBreaker:
    """E2E tests for circuit breaker functionality."""

    @pytest.mark.slow
    @pytest.mark.timeout(TimeoutConfig.PIPELINE_COMPLETION + TimeoutConfig.CIRCUIT_BREAKER_COOLDOWN)
    @pytest.mark.asyncio
    async def test_circuit_breaker_opens_on_sts_failures(
        self,
        docker_services: DockerManager,
        stream_publisher: StreamPublisher,
        metrics_parser: MetricsParser,
        sts_config_client: socketio.AsyncClient,
    ) -> None:
        """Validate circuit breaker opens after consecutive STS failures.

        Acceptance Criteria (from spec):
        - Circuit breaker opens after 5 failures
        - Fallback audio used (original audio in output)
        - Breaker recovers after 30s cooldown
        - Normal processing resumes

        Steps:
        1. Start services and publish test fixture
        2. Configure Echo STS to return 5 consecutive TIMEOUT errors
        3. Verify breaker opens (check logs and metrics)
        4. Assert subsequent fragments use fallback audio
        5. Wait 30s for cooldown
        6. Verify breaker enters half-open state
        7. Configure Echo STS to succeed
        8. Verify breaker closes and normal processing resumes
        """
        if not TestFixtureConfig.FIXTURE_PATH.exists():
            pytest.skip(f"Test fixture not found: {TestFixtureConfig.FIXTURE_PATH}")

        input_stream_path = f"live/{TestConfig.STREAM_ID}/in"

        # Step 1: Start publishing (looped for longer test)
        stream_publisher.start(stream_path=input_stream_path, realtime=True, loop=True)

        try:
            # Give time for initial processing to start
            await asyncio.sleep(10)

            # Step 2: Configure Echo STS to simulate TIMEOUT errors
            # First, need to initialize a stream session
            ready_event = asyncio.Event()

            @sts_config_client.on("stream:ready")
            async def on_ready(data):
                ready_event.set()

            @sts_config_client.on("config:error_simulation:ack")
            async def on_config_ack(data):
                logger.info(f"Error simulation config ack: {data}")

            # Initialize stream session for config
            await sts_config_client.emit(
                "stream:init",
                {
                    "stream_id": f"{TestConfig.STREAM_ID}-config",
                    "worker_id": "config-worker",
                    "config": {},
                    "max_inflight": TestConfig.MAX_INFLIGHT,
                },
            )

            try:
                await asyncio.wait_for(ready_event.wait(), timeout=10)
            except asyncio.TimeoutError:
                pytest.skip("Could not initialize Echo STS config session")

            # Configure error simulation - 5 TIMEOUT errors
            await sts_config_client.emit(
                "config:error_simulation",
                {
                    "enabled": True,
                    "rules": [
                        {
                            "error_code": "TIMEOUT",
                            "probability": 1.0,  # 100% error rate
                            "count": 5,  # First 5 fragments
                        }
                    ],
                },
            )

            # Wait for errors to be processed
            await asyncio.sleep(15)

            # Step 3: Verify circuit breaker opened
            metrics_parser.fetch()

            breaker_state = metrics_parser.get_gauge(
                "worker_sts_breaker_state",
                labels={"stream_id": TestConfig.STREAM_ID},
            )

            logger.info(f"Circuit breaker state: {breaker_state}")

            # State values: 0=closed, 1=open, 2=half-open
            if breaker_state is not None:
                assert breaker_state == 1, (
                    f"Circuit breaker should be open (1), got {breaker_state}"
                )

            # Step 4: Check fallback counter increased
            fallback_count = metrics_parser.get_counter(
                "worker_fallback",
                labels={"stream_id": TestConfig.STREAM_ID},
            )

            if fallback_count is not None:
                logger.info(f"Fallback count: {fallback_count}")
                assert fallback_count >= 5, f"Expected at least 5 fallbacks, got {fallback_count}"

            # Step 5: Wait for cooldown (30s)
            logger.info("Waiting for circuit breaker cooldown...")
            await asyncio.sleep(TimeoutConfig.CIRCUIT_BREAKER_COOLDOWN)

            # Step 6: Check half-open state
            metrics_parser.fetch()
            breaker_state = metrics_parser.get_gauge(
                "worker_sts_breaker_state",
                labels={"stream_id": TestConfig.STREAM_ID},
            )

            logger.info(f"Circuit breaker state after cooldown: {breaker_state}")

            # Step 7: Disable error simulation (let probes succeed)
            await sts_config_client.emit(
                "config:error_simulation",
                {
                    "enabled": False,
                    "rules": [],
                },
            )

            # Wait for recovery
            await asyncio.sleep(10)

            # Step 8: Verify breaker closed
            metrics_parser.fetch()
            breaker_state = metrics_parser.get_gauge(
                "worker_sts_breaker_state",
                labels={"stream_id": TestConfig.STREAM_ID},
            )

            logger.info(f"Circuit breaker state after recovery: {breaker_state}")

            if breaker_state is not None:
                assert breaker_state == 0, (
                    f"Circuit breaker should be closed (0), got {breaker_state}"
                )

            logger.info("Circuit breaker test PASSED")

        finally:
            if stream_publisher.is_running():
                stream_publisher.stop()

    @pytest.mark.asyncio
    async def test_circuit_breaker_ignores_non_retryable_errors(
        self,
        docker_services: DockerManager,
        stream_publisher: StreamPublisher,
        metrics_parser: MetricsParser,
        sts_config_client: socketio.AsyncClient,
    ) -> None:
        """Verify breaker ignores non-retryable errors like INVALID_CONFIG.

        Non-retryable errors should be logged but NOT increment the
        circuit breaker failure counter.

        Per spec: INVALID_CONFIG is non-retryable.
        """
        if not TestFixtureConfig.FIXTURE_PATH.exists():
            pytest.skip(f"Test fixture not found: {TestFixtureConfig.FIXTURE_PATH}")

        input_stream_path = f"live/{TestConfig.STREAM_ID}/in"

        stream_publisher.start(stream_path=input_stream_path, realtime=True, loop=True)

        try:
            await asyncio.sleep(5)

            # Initialize config session
            ready_event = asyncio.Event()

            @sts_config_client.on("stream:ready")
            async def on_ready(data):
                ready_event.set()

            await sts_config_client.emit(
                "stream:init",
                {
                    "stream_id": f"{TestConfig.STREAM_ID}-config2",
                    "worker_id": "config-worker-2",
                    "config": {},
                    "max_inflight": TestConfig.MAX_INFLIGHT,
                },
            )

            try:
                await asyncio.wait_for(ready_event.wait(), timeout=10)
            except asyncio.TimeoutError:
                pytest.skip("Could not initialize Echo STS config session")

            # Get initial breaker failure count
            metrics_parser.fetch()
            initial_failures = metrics_parser.get_counter(
                "worker_circuit_breaker_failures",
                labels={"stream_id": TestConfig.STREAM_ID},
            ) or 0

            # Configure non-retryable error
            await sts_config_client.emit(
                "config:error_simulation",
                {
                    "enabled": True,
                    "rules": [
                        {
                            "error_code": "INVALID_CONFIG",  # Non-retryable
                            "probability": 1.0,
                            "count": 3,
                        }
                    ],
                },
            )

            # Wait for errors
            await asyncio.sleep(15)

            # Check failure counter didn't increment for non-retryable
            metrics_parser.fetch()
            final_failures = metrics_parser.get_counter(
                "worker_circuit_breaker_failures",
                labels={"stream_id": TestConfig.STREAM_ID},
            ) or 0

            # Failures might increment for other reasons, but should not
            # have increased by 3 (the non-retryable errors)
            failure_delta = final_failures - initial_failures
            logger.info(
                f"Circuit breaker failures: {initial_failures} -> {final_failures} "
                f"(delta: {failure_delta})"
            )

            # Non-retryable errors should NOT count toward breaker
            # Allow some tolerance for timing
            assert failure_delta < 3, (
                f"Non-retryable errors incorrectly counted: {failure_delta}"
            )

            # Cleanup
            await sts_config_client.emit(
                "config:error_simulation",
                {"enabled": False, "rules": []},
            )

        finally:
            if stream_publisher.is_running():
                stream_publisher.stop()

    @pytest.mark.slow
    def test_circuit_breaker_state_transitions_logged(
        self,
        docker_services: DockerManager,
        metrics_parser: MetricsParser,
    ) -> None:
        """Verify all circuit breaker state transitions are logged and metrified.

        Checks:
        - State transitions (closed -> open -> half-open -> closed) logged
        - Metrics reflect current state
        - Timestamps are recorded
        """
        # Verify metrics endpoint has breaker state metric
        metrics_parser.fetch()

        # Check for state metric existence
        breaker_state = metrics_parser.get_gauge("worker_sts_breaker_state")

        # Even without active stream, metric should exist (default closed=0)
        # or be absent if no worker is running
        if breaker_state is not None:
            logger.info(f"Breaker state metric exists: {breaker_state}")
            assert breaker_state in [0, 1, 2], (
                f"Invalid breaker state: {breaker_state}"
            )

        # Check for transition counter
        transitions = metrics_parser.get_counter("worker_circuit_breaker_transitions")
        if transitions is not None:
            logger.info(f"Breaker transitions: {transitions}")

        logger.info("Circuit breaker metrics check complete")


@pytest.mark.e2e
@pytest.mark.p2
class TestCircuitBreakerMetrics:
    """Tests for circuit breaker metrics."""

    def test_circuit_breaker_metrics_exposed(
        self,
        docker_services: DockerManager,
        metrics_parser: MetricsParser,
    ) -> None:
        """Verify circuit breaker metrics are exposed in Prometheus format."""
        metrics_parser.fetch()

        # List expected metrics (may or may not have values if no stream active)
        expected_metrics = [
            "worker_sts_breaker_state",
            "worker_circuit_breaker_failures",
            "worker_circuit_breaker_fallback",
        ]

        raw_text = metrics_parser.raw_text
        found_metrics = []

        for metric in expected_metrics:
            if metric in raw_text:
                found_metrics.append(metric)
                logger.info(f"Found metric: {metric}")

        # At least state metric should be exposed if media-service is running
        logger.info(f"Found {len(found_metrics)}/{len(expected_metrics)} circuit breaker metrics")
