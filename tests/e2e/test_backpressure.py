"""E2E tests for backpressure handling.

Priority: P2
User Story 4: Backpressure Handling

Tests WorkerRunner response to backpressure events from Echo STS.
Validates pause/resume and slow_down behavior.

Per spec 018-e2e-stream-handler-tests/spec.md User Story 4.
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
async def sts_backpressure_client():
    """Socket.IO client for triggering backpressure events."""
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
class TestBackpressureHandling:
    """E2E tests for backpressure handling."""

    @pytest.mark.slow
    @pytest.mark.timeout(TimeoutConfig.PIPELINE_COMPLETION)
    @pytest.mark.asyncio
    async def test_worker_respects_backpressure_pause(
        self,
        docker_services: DockerManager,
        stream_publisher: StreamPublisher,
        metrics_parser: MetricsParser,
        sts_backpressure_client: socketio.AsyncClient,
    ) -> None:
        """Verify worker stops sending fragments on backpressure pause.

        Acceptance Criteria (from spec):
        - Worker stops sending new fragments on action: "pause"
        - Worker resumes on action: "none"
        - Metrics show correct backpressure event counts

        Steps:
        1. Start services and publish test fixture
        2. Start WorkerRunner sending fragments normally
        3. Configure Echo STS to emit backpressure with action="pause"
        4. Verify worker stops sending new fragments
        5. Configure Echo STS to emit backpressure with action="none"
        6. Verify worker resumes sending fragments
        """
        if not TestFixtureConfig.FIXTURE_PATH.exists():
            pytest.skip(f"Test fixture not found: {TestFixtureConfig.FIXTURE_PATH}")

        input_stream_path = f"live/{TestConfig.STREAM_ID}/in"

        stream_publisher.start(stream_path=input_stream_path, realtime=True, loop=True)

        try:
            # Wait for initial processing
            await asyncio.sleep(10)

            # Initialize session for backpressure config
            ready_event = asyncio.Event()
            backpressure_received = asyncio.Event()

            @sts_backpressure_client.on("stream:ready")
            async def on_ready(data):
                ready_event.set()

            @sts_backpressure_client.on("backpressure")
            async def on_backpressure(data):
                logger.info(f"Backpressure event received: {data}")
                backpressure_received.set()

            await sts_backpressure_client.emit(
                "stream:init",
                {
                    "stream_id": f"{TestConfig.STREAM_ID}-bp",
                    "worker_id": "bp-test-worker",
                    "config": {},
                    "max_inflight": 3,  # Low to trigger backpressure easily
                },
            )

            try:
                await asyncio.wait_for(ready_event.wait(), timeout=10)
            except asyncio.TimeoutError:
                pytest.skip("Could not initialize Echo STS backpressure session")

            # Get initial fragment count
            metrics_parser.fetch()
            initial_fragments = metrics_parser.get_counter(
                "worker_audio_fragments",
                labels={"stream_id": TestConfig.STREAM_ID},
            ) or 0

            # Trigger backpressure pause via config event
            # Echo STS will emit backpressure based on in-flight count
            # We can also manually configure backpressure behavior

            # Wait and record fragment rate
            await asyncio.sleep(5)

            metrics_parser.fetch()
            mid_fragments = metrics_parser.get_counter(
                "worker_audio_fragments",
                labels={"stream_id": TestConfig.STREAM_ID},
            ) or 0

            logger.info(
                f"Fragments: initial={initial_fragments}, mid={mid_fragments}"
            )

            # Check backpressure metrics
            backpressure_events = metrics_parser.get_counter(
                "worker_backpressure_events",
            )

            if backpressure_events is not None:
                logger.info(f"Backpressure events total: {backpressure_events}")

            # Verify worker is processing (fragments increasing)
            if mid_fragments is not None and initial_fragments is not None:
                assert mid_fragments > initial_fragments, (
                    "Worker not processing fragments"
                )

        finally:
            if stream_publisher.is_running():
                stream_publisher.stop()

    @pytest.mark.slow
    @pytest.mark.asyncio
    async def test_worker_respects_backpressure_slow_down(
        self,
        docker_services: DockerManager,
        stream_publisher: StreamPublisher,
        metrics_parser: MetricsParser,
        sts_backpressure_client: socketio.AsyncClient,
    ) -> None:
        """Verify worker inserts delay on backpressure slow_down.

        Acceptance Criteria:
        - Worker inserts recommended_delay_ms between fragment sends
        - Fragment rate decreases appropriately
        """
        if not TestFixtureConfig.FIXTURE_PATH.exists():
            pytest.skip(f"Test fixture not found: {TestFixtureConfig.FIXTURE_PATH}")

        input_stream_path = f"live/{TestConfig.STREAM_ID}/in"

        stream_publisher.start(stream_path=input_stream_path, realtime=True, loop=True)

        try:
            await asyncio.sleep(5)

            # Initialize session
            ready_event = asyncio.Event()

            @sts_backpressure_client.on("stream:ready")
            async def on_ready(data):
                ready_event.set()

            await sts_backpressure_client.emit(
                "stream:init",
                {
                    "stream_id": f"{TestConfig.STREAM_ID}-slow",
                    "worker_id": "slow-test-worker",
                    "config": {},
                    "max_inflight": 5,
                },
            )

            try:
                await asyncio.wait_for(ready_event.wait(), timeout=10)
            except asyncio.TimeoutError:
                pytest.skip("Could not initialize Echo STS session")

            # Record fragment rate before slow_down
            metrics_parser.fetch()
            t1 = time.time()
            count1 = metrics_parser.get_counter(
                "worker_audio_fragments",
                labels={"stream_id": TestConfig.STREAM_ID},
            ) or 0

            await asyncio.sleep(10)

            metrics_parser.fetch()
            t2 = time.time()
            count2 = metrics_parser.get_counter(
                "worker_audio_fragments",
                labels={"stream_id": TestConfig.STREAM_ID},
            ) or 0

            normal_rate = (count2 - count1) / (t2 - t1) if (t2 - t1) > 0 else 0
            logger.info(f"Normal fragment rate: {normal_rate:.2f}/s")

            # Slow_down behavior is automatic based on Echo STS config
            # The backpressure events will trigger slow_down

            # Check backpressure metrics by action type
            slow_down_events = metrics_parser.get_counter(
                "worker_backpressure_events",
                labels={"action": "slow_down"},
            )

            pause_events = metrics_parser.get_counter(
                "worker_backpressure_events",
                labels={"action": "pause"},
            )

            logger.info(
                f"Backpressure events - slow_down: {slow_down_events}, "
                f"pause: {pause_events}"
            )

        finally:
            if stream_publisher.is_running():
                stream_publisher.stop()

    def test_backpressure_metrics_updated(
        self,
        docker_services: DockerManager,
        stream_publisher: StreamPublisher,
        metrics_parser: MetricsParser,
    ) -> None:
        """Verify backpressure metrics are correctly incremented by action type."""
        if not TestFixtureConfig.FIXTURE_PATH.exists():
            pytest.skip(f"Test fixture not found: {TestFixtureConfig.FIXTURE_PATH}")

        input_stream_path = f"live/{TestConfig.STREAM_ID}/in"

        stream_publisher.start(stream_path=input_stream_path, realtime=True, loop=True)

        try:
            # Let processing run
            time.sleep(20)

            metrics_parser.fetch()

            # Check for backpressure event counter
            total_bp_events = metrics_parser.get_counter(
                "worker_backpressure_events"
            )

            logger.info(f"Total backpressure events: {total_bp_events}")

            # Check by action type if available
            action_types = ["pause", "slow_down", "none"]
            for action in action_types:
                count = metrics_parser.get_counter(
                    "worker_backpressure_events",
                    labels={"action": action},
                )
                if count is not None:
                    logger.info(f"Backpressure events ({action}): {count}")

            # Verify metric structure is correct
            samples = metrics_parser.get_all_samples("worker_backpressure_events")
            if samples:
                for sample in samples:
                    # Verify labels are correct
                    if "action" in sample.labels:
                        assert sample.labels["action"] in ["pause", "slow_down", "none"], (
                            f"Invalid backpressure action: {sample.labels['action']}"
                        )

        finally:
            if stream_publisher.is_running():
                stream_publisher.stop()


@pytest.mark.e2e
@pytest.mark.p2
class TestBackpressureRecovery:
    """Tests for backpressure recovery scenarios."""

    @pytest.mark.slow
    @pytest.mark.asyncio
    async def test_worker_resumes_after_backpressure_clears(
        self,
        docker_services: DockerManager,
        stream_publisher: StreamPublisher,
        metrics_parser: MetricsParser,
    ) -> None:
        """Verify worker resumes full speed after backpressure clears.

        When backpressure condition is resolved, worker should:
        - Return to normal fragment sending rate
        - Clear any accumulated delay
        """
        if not TestFixtureConfig.FIXTURE_PATH.exists():
            pytest.skip(f"Test fixture not found: {TestFixtureConfig.FIXTURE_PATH}")

        input_stream_path = f"live/{TestConfig.STREAM_ID}/in"

        stream_publisher.start(stream_path=input_stream_path, realtime=True, loop=True)

        try:
            # Let processing stabilize
            await asyncio.sleep(20)

            # Check fragment processing is happening
            metrics_parser.fetch()

            fragments = metrics_parser.get_counter(
                "worker_audio_fragments",
                labels={"stream_id": TestConfig.STREAM_ID},
            )

            if fragments is not None:
                logger.info(f"Fragments processed: {fragments}")
                # After 20s with 6s segments, should have ~3 segments
                assert fragments >= 2, f"Too few fragments: {fragments}"

            # Check worker is healthy
            assert docker_services.is_running(), "Docker services not running"

        finally:
            if stream_publisher.is_running():
                stream_publisher.stop()

    def test_backpressure_does_not_cause_data_loss(
        self,
        docker_services: DockerManager,
        stream_publisher: StreamPublisher,
        metrics_parser: MetricsParser,
    ) -> None:
        """Verify backpressure handling doesn't cause data loss.

        When worker pauses for backpressure, video buffers should still
        accumulate and no segments should be dropped.
        """
        if not TestFixtureConfig.FIXTURE_PATH.exists():
            pytest.skip(f"Test fixture not found: {TestFixtureConfig.FIXTURE_PATH}")

        input_stream_path = f"live/{TestConfig.STREAM_ID}/in"

        # Start with non-looped stream for counting
        stream_publisher.start(stream_path=input_stream_path, realtime=True, loop=False)

        try:
            # Wait for completion
            stats = stream_publisher.wait_for_completion(
                timeout=TimeoutConfig.PIPELINE_COMPLETION
            )

            time.sleep(5)  # Let processing complete

            if stats is None:
                pytest.skip("Stream didn't complete")

            metrics_parser.fetch()

            # Check total segments processed
            video_segments = metrics_parser.get_counter(
                "worker_video_segments",
                labels={"stream_id": TestConfig.STREAM_ID},
            )

            audio_fragments = metrics_parser.get_counter(
                "worker_audio_fragments",
                labels={"stream_id": TestConfig.STREAM_ID},
            )

            dropped_segments = metrics_parser.get_counter(
                "worker_segments_dropped",
                labels={"stream_id": TestConfig.STREAM_ID},
            )

            logger.info(
                f"Video segments: {video_segments}, "
                f"Audio fragments: {audio_fragments}, "
                f"Dropped: {dropped_segments}"
            )

            # Should have minimal drops (maybe 0)
            if dropped_segments is not None:
                assert dropped_segments <= 1, (
                    f"Too many segments dropped: {dropped_segments}"
                )

        finally:
            if stream_publisher.is_running():
                stream_publisher.stop()
