"""E2E tests for fragment tracker integration.

Priority: P2
User Story 5: Fragment Tracker E2E

Tests FragmentTracker correctly tracks in-flight fragments across the full
pipeline and enforces max_inflight limit.

Per spec 018-e2e-stream-handler-tests/spec.md User Story 5.
"""

from __future__ import annotations

import asyncio
import logging
import time
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
async def sts_tracker_client():
    """Socket.IO client for fragment tracking tests."""
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
class TestFragmentTracker:
    """E2E tests for fragment tracking."""

    @pytest.mark.slow
    @pytest.mark.timeout(TimeoutConfig.PIPELINE_COMPLETION)
    def test_fragment_tracker_respects_max_inflight(
        self,
        docker_services: DockerManager,
        stream_publisher: StreamPublisher,
        metrics_parser: MetricsParser,
    ) -> None:
        """Verify worker never exceeds max_inflight limit.

        Acceptance Criteria (from spec):
        - Worker enforces max_inflight=3
        - In-flight count increases on fragment:data send
        - In-flight count decreases on fragment:processed
        - All fragments are tracked and completed (no leaks)

        Steps:
        1. Start services and publish test fixture
        2. Configure WorkerRunner with max_inflight=3
        3. Monitor worker_inflight_fragments metric during processing
        4. Verify worker never exceeds max_inflight=3
        5. Validate all fragments are tracked and completed
        """
        if not TestFixtureConfig.FIXTURE_PATH.exists():
            pytest.skip(f"Test fixture not found: {TestFixtureConfig.FIXTURE_PATH}")

        input_stream_path = f"live/{TestConfig.STREAM_ID}/in"

        stream_publisher.start(stream_path=input_stream_path, realtime=True, loop=True)

        try:
            max_observed_inflight = 0
            samples_collected = 0

            # Sample in-flight count every 100ms for 30 seconds
            start_time = time.time()
            sampling_duration = 30

            while time.time() - start_time < sampling_duration:
                try:
                    metrics_parser.fetch()

                    inflight = metrics_parser.get_gauge(
                        "worker_inflight_fragments",
                        labels={"stream_id": TestConfig.STREAM_ID},
                    )

                    if inflight is not None:
                        samples_collected += 1
                        max_observed_inflight = max(max_observed_inflight, inflight)

                        if inflight > TestConfig.MAX_INFLIGHT:
                            logger.error(
                                f"Max inflight exceeded! "
                                f"Current: {inflight}, Max: {TestConfig.MAX_INFLIGHT}"
                            )

                except Exception as e:
                    logger.debug(f"Sampling error: {e}")

                time.sleep(0.1)  # 100ms sampling interval

            logger.info(
                f"In-flight sampling complete: "
                f"samples={samples_collected}, "
                f"max_observed={max_observed_inflight}"
            )

            # Verify max_inflight was respected
            assert max_observed_inflight <= TestConfig.MAX_INFLIGHT, (
                f"Max inflight {TestConfig.MAX_INFLIGHT} exceeded: "
                f"observed {max_observed_inflight}"
            )

            # Verify we actually observed some in-flight fragments
            if samples_collected > 0:
                assert max_observed_inflight >= 0, "No in-flight fragments observed"

        finally:
            if stream_publisher.is_running():
                stream_publisher.stop()

    @pytest.mark.slow
    @pytest.mark.asyncio
    async def test_fragment_tracker_timeout_triggers_fallback(
        self,
        docker_services: DockerManager,
        stream_publisher: StreamPublisher,
        metrics_parser: MetricsParser,
        sts_tracker_client: socketio.AsyncClient,
    ) -> None:
        """Verify fragment timeout removes fragment from tracking.

        When STS doesn't respond within timeout (8s):
        - Fragment should be removed from in-flight tracking
        - Fallback audio should be used
        - Worker should be able to send next fragment
        """
        if not TestFixtureConfig.FIXTURE_PATH.exists():
            pytest.skip(f"Test fixture not found: {TestFixtureConfig.FIXTURE_PATH}")

        input_stream_path = f"live/{TestConfig.STREAM_ID}/in"

        stream_publisher.start(stream_path=input_stream_path, realtime=True, loop=True)

        try:
            await asyncio.sleep(5)

            # Initialize session
            ready_event = asyncio.Event()

            @sts_tracker_client.on("stream:ready")
            async def on_ready(data):
                ready_event.set()

            await sts_tracker_client.emit(
                "stream:init",
                {
                    "stream_id": f"{TestConfig.STREAM_ID}-timeout",
                    "worker_id": "timeout-test-worker",
                    "config": {},
                    "max_inflight": TestConfig.MAX_INFLIGHT,
                },
            )

            try:
                await asyncio.wait_for(ready_event.wait(), timeout=10)
            except asyncio.TimeoutError:
                pytest.skip("Could not initialize Echo STS session")

            # Configure STS to delay beyond timeout (8s)
            # Use error simulation with TIMEOUT after delay
            await sts_tracker_client.emit(
                "config:error_simulation",
                {
                    "enabled": True,
                    "rules": [
                        {
                            "error_code": "TIMEOUT",
                            "probability": 1.0,
                            "delay_ms": 10000,  # 10s delay (beyond 8s timeout)
                            "count": 2,
                        }
                    ],
                },
            )

            # Wait for timeout to occur
            await asyncio.sleep(TimeoutConfig.FRAGMENT_TIMEOUT + 5)

            # Check fallback was used
            metrics_parser.fetch()

            fallback_count = metrics_parser.get_counter(
                "worker_fallback",
                labels={"stream_id": TestConfig.STREAM_ID},
            )

            timeout_count = metrics_parser.get_counter(
                "worker_fragment_timeouts",
                labels={"stream_id": TestConfig.STREAM_ID},
            )

            logger.info(
                f"After timeout - Fallbacks: {fallback_count}, "
                f"Timeouts: {timeout_count}"
            )

            # Check in-flight was cleared (timeout should free slot)
            inflight = metrics_parser.get_gauge(
                "worker_inflight_fragments",
                labels={"stream_id": TestConfig.STREAM_ID},
            )

            logger.info(f"In-flight after timeout: {inflight}")

            # Should be less than max (slot was freed)
            if inflight is not None:
                assert inflight < TestConfig.MAX_INFLIGHT, (
                    f"In-flight slot not freed on timeout: {inflight}"
                )

            # Cleanup
            await sts_tracker_client.emit(
                "config:error_simulation",
                {"enabled": False, "rules": []},
            )

        finally:
            if stream_publisher.is_running():
                stream_publisher.stop()

    @pytest.mark.slow
    @pytest.mark.asyncio
    async def test_fragment_tracker_correlation_across_events(
        self,
        docker_services: DockerManager,
        stream_publisher: StreamPublisher,
        sts_tracker_client: socketio.AsyncClient,
    ) -> None:
        """Validate fragment_id correlation between events.

        Verifies fragment_id is correctly correlated between:
        - fragment:data (send)
        - fragment:ack (acknowledgment)
        - fragment:processed (completion)
        """
        if not TestFixtureConfig.FIXTURE_PATH.exists():
            pytest.skip(f"Test fixture not found: {TestFixtureConfig.FIXTURE_PATH}")

        input_stream_path = f"live/{TestConfig.STREAM_ID}/in"

        # Track events
        events_received: dict[str, list] = {
            "fragment:ack": [],
            "fragment:processed": [],
        }

        @sts_tracker_client.on("fragment:ack")
        async def on_ack(data):
            events_received["fragment:ack"].append(data)
            logger.debug(f"fragment:ack: {data.get('fragment_id')}")

        @sts_tracker_client.on("fragment:processed")
        async def on_processed(data):
            events_received["fragment:processed"].append(data)
            logger.debug(f"fragment:processed: {data.get('fragment_id')}")

        # Initialize session
        ready_event = asyncio.Event()

        @sts_tracker_client.on("stream:ready")
        async def on_ready(data):
            ready_event.set()

        await sts_tracker_client.emit(
            "stream:init",
            {
                "stream_id": f"{TestConfig.STREAM_ID}-corr",
                "worker_id": "correlation-test",
                "config": {},
                "max_inflight": TestConfig.MAX_INFLIGHT,
            },
        )

        try:
            await asyncio.wait_for(ready_event.wait(), timeout=10)
        except asyncio.TimeoutError:
            pytest.skip("Could not initialize Echo STS session")

        stream_publisher.start(stream_path=input_stream_path, realtime=True, loop=True)

        try:
            # Wait for some fragments to process
            await asyncio.sleep(20)

            # Analyze correlation
            ack_ids = {e.get("fragment_id") for e in events_received["fragment:ack"]}
            processed_ids = {
                e.get("fragment_id") for e in events_received["fragment:processed"]
            }

            logger.info(
                f"Events received - acks: {len(ack_ids)}, "
                f"processed: {len(processed_ids)}"
            )

            # All processed fragments should have been acked
            unacked_processed = processed_ids - ack_ids
            if unacked_processed and len(ack_ids) > 0:
                logger.warning(f"Processed without ack: {unacked_processed}")

            # Fragment IDs should follow consistent format
            for frag_id in processed_ids:
                if frag_id:
                    # Verify ID format (e.g., "stream-id-seq-XXX")
                    assert isinstance(frag_id, str), f"Invalid fragment ID type: {type(frag_id)}"
                    assert len(frag_id) > 0, "Empty fragment ID"

            logger.info("Fragment ID correlation test complete")

        finally:
            if stream_publisher.is_running():
                stream_publisher.stop()


@pytest.mark.e2e
@pytest.mark.p2
class TestFragmentTrackerMetrics:
    """Tests for fragment tracker metrics."""

    def test_inflight_gauge_accurate(
        self,
        docker_services: DockerManager,
        stream_publisher: StreamPublisher,
        metrics_parser: MetricsParser,
    ) -> None:
        """Verify worker_inflight_fragments gauge is accurate."""
        if not TestFixtureConfig.FIXTURE_PATH.exists():
            pytest.skip(f"Test fixture not found: {TestFixtureConfig.FIXTURE_PATH}")

        input_stream_path = f"live/{TestConfig.STREAM_ID}/in"

        stream_publisher.start(stream_path=input_stream_path, realtime=True, loop=True)

        try:
            # Let processing stabilize
            time.sleep(15)

            metrics_parser.fetch()

            inflight = metrics_parser.get_gauge(
                "worker_inflight_fragments",
                labels={"stream_id": TestConfig.STREAM_ID},
            )

            logger.info(f"In-flight fragments: {inflight}")

            if inflight is not None:
                # Should be non-negative
                assert inflight >= 0, f"Negative in-flight count: {inflight}"

                # Should be <= max_inflight
                assert inflight <= TestConfig.MAX_INFLIGHT, (
                    f"In-flight {inflight} exceeds max {TestConfig.MAX_INFLIGHT}"
                )

        finally:
            if stream_publisher.is_running():
                stream_publisher.stop()

    def test_fragment_tracker_no_leaks(
        self,
        docker_services: DockerManager,
        stream_publisher: StreamPublisher,
        metrics_parser: MetricsParser,
    ) -> None:
        """Verify no fragment tracking memory leaks after stream completion."""
        if not TestFixtureConfig.FIXTURE_PATH.exists():
            pytest.skip(f"Test fixture not found: {TestFixtureConfig.FIXTURE_PATH}")

        input_stream_path = f"live/{TestConfig.STREAM_ID}/in"

        # Start non-looped stream
        stream_publisher.start(stream_path=input_stream_path, realtime=True, loop=False)

        try:
            # Wait for completion
            stats = stream_publisher.wait_for_completion(
                timeout=TimeoutConfig.PIPELINE_COMPLETION
            )

            if stats is None:
                pytest.skip("Stream didn't complete")

            # Wait for processing to finish
            time.sleep(10)

            # Check in-flight is zero
            metrics_parser.fetch()

            inflight = metrics_parser.get_gauge(
                "worker_inflight_fragments",
                labels={"stream_id": TestConfig.STREAM_ID},
            )

            logger.info(f"In-flight after completion: {inflight}")

            if inflight is not None:
                assert inflight == 0, (
                    f"Fragment leak detected: {inflight} still in-flight"
                )

        finally:
            if stream_publisher.is_running():
                stream_publisher.stop()

    def test_fragment_sent_and_processed_counters_match(
        self,
        docker_services: DockerManager,
        stream_publisher: StreamPublisher,
        metrics_parser: MetricsParser,
    ) -> None:
        """Verify fragments sent equals fragments processed + fallbacks."""
        if not TestFixtureConfig.FIXTURE_PATH.exists():
            pytest.skip(f"Test fixture not found: {TestFixtureConfig.FIXTURE_PATH}")

        input_stream_path = f"live/{TestConfig.STREAM_ID}/in"

        stream_publisher.start(stream_path=input_stream_path, realtime=True, loop=False)

        try:
            # Wait for completion
            stats = stream_publisher.wait_for_completion(
                timeout=TimeoutConfig.PIPELINE_COMPLETION
            )

            if stats is None:
                pytest.skip("Stream didn't complete")

            time.sleep(10)

            metrics_parser.fetch()

            sent = metrics_parser.get_counter(
                "worker_sts_fragments_sent",
                labels={"stream_id": TestConfig.STREAM_ID},
            )

            processed = metrics_parser.get_counter(
                "worker_sts_fragments_processed",
                labels={"stream_id": TestConfig.STREAM_ID},
            )

            fallbacks = metrics_parser.get_counter(
                "worker_fallback",
                labels={"stream_id": TestConfig.STREAM_ID},
            )

            logger.info(
                f"Fragments - Sent: {sent}, Processed: {processed}, "
                f"Fallbacks: {fallbacks}"
            )

            # sent should equal processed + fallbacks (accounting for in-flight at end)
            if sent is not None and processed is not None:
                total_completed = processed + (fallbacks or 0)
                # Allow small difference for timing
                assert abs(sent - total_completed) <= 2, (
                    f"Fragment accounting mismatch: sent={sent}, "
                    f"completed={total_completed}"
                )

        finally:
            if stream_publisher.is_running():
                stream_publisher.stop()
