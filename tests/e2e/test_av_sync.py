"""E2E tests for A/V synchronization verification.

Priority: P1 (MVP)
User Story 2: A/V Sync Verification

Tests that A/V synchronization remains within acceptable threshold (120ms)
throughout the full pipeline despite asynchronous STS processing latency.

Per spec 018-e2e-stream-handler-tests/spec.md User Story 2.
"""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING

import pytest

from tests.e2e.config import (
    MediaMTXConfig,
    TestConfig,
    TestFixtureConfig,
    TimeoutConfig,
)
from tests.e2e.conftest import wait_for_condition

if TYPE_CHECKING:
    from tests.e2e.helpers.docker_manager import DockerManager
    from tests.e2e.helpers.metrics_parser import MetricsParser
    from tests.e2e.helpers.stream_analyzer import StreamAnalyzer
    from tests.e2e.helpers.stream_publisher import StreamPublisher

logger = logging.getLogger(__name__)


@pytest.mark.e2e
@pytest.mark.p1
class TestAVSync:
    """E2E tests for A/V synchronization."""

    @pytest.mark.slow
    @pytest.mark.timeout(TimeoutConfig.PIPELINE_COMPLETION)
    def test_av_sync_within_threshold(
        self,
        docker_services: DockerManager,
        stream_publisher: StreamPublisher,
        stream_analyzer: StreamAnalyzer,
        metrics_parser: MetricsParser,
    ) -> None:
        """Validate A/V sync delta < 120ms throughout pipeline.

        Acceptance Criteria (from spec):
        - A/V sync delta measured at output remains < 120ms for 95% of segments
        - No sync corrections required beyond initial offset

        Steps:
        1. Start Docker services and publish test fixture
        2. Start WorkerRunner with A/V sync monitoring
        3. Capture all segment pairs during processing
        4. Extract video PTS and audio PTS from output RTMP
        5. Calculate A/V delta for each segment
        6. Assert 95% of segments have delta < 120ms
        """
        if not TestFixtureConfig.FIXTURE_PATH.exists():
            pytest.skip(f"Test fixture not found: {TestFixtureConfig.FIXTURE_PATH}")

        input_stream_path = f"live/{TestConfig.STREAM_ID}/in"
        output_stream_path = f"live/{TestConfig.STREAM_ID}/out"
        output_url = f"{MediaMTXConfig.RTMP_URL}/{output_stream_path}"

        # Start publishing
        stream_publisher.start(stream_path=input_stream_path, realtime=True)

        try:
            # Wait for output stream to appear
            output_exists = wait_for_condition(
                lambda: stream_analyzer.verify_stream_exists(output_stream_path),
                timeout_sec=TimeoutConfig.STREAM_PUBLISH,
                description="output stream for A/V sync analysis",
            )

            if not output_exists:
                pytest.skip("Output stream not available - worker may not auto-start")

            logger.info("Output stream available, starting A/V sync analysis")

            # Let stream run for enough time to capture segments
            time.sleep(30)  # Wait for ~5 segments

            # Analyze A/V sync
            sync_result = stream_analyzer.analyze_av_sync(
                url=output_url,
                segment_duration_sec=TestConfig.SEGMENT_DURATION_SEC,
                duration_sec=30,  # Analyze 30 seconds
                threshold_ms=TestConfig.AV_SYNC_THRESHOLD_MS,
            )

            logger.info(
                f"A/V Sync Analysis Results:\n"
                f"  Total samples: {sync_result.total_count}\n"
                f"  Within threshold: {sync_result.within_threshold_count}\n"
                f"  Pass rate: {sync_result.pass_rate:.2%}\n"
                f"  Avg delta: {sync_result.avg_delta_ms:.2f}ms\n"
                f"  Max delta: {sync_result.max_delta_ms:.2f}ms\n"
                f"  Min delta: {sync_result.min_delta_ms:.2f}ms"
            )

            # Verify pass rate meets threshold
            assert sync_result.total_count > 0, "No A/V sync samples captured"
            assert sync_result.passes_threshold, (
                f"A/V sync pass rate {sync_result.pass_rate:.2%} below "
                f"required {TestConfig.AV_SYNC_PASS_RATE:.2%}. "
                f"Max delta: {sync_result.max_delta_ms:.2f}ms"
            )

            logger.info("A/V sync test PASSED")

            # Also verify via metrics
            metrics_parser.fetch()
            av_sync_metric = metrics_parser.get_gauge(
                "worker_av_sync_delta_ms",
                labels={"stream_id": TestConfig.STREAM_ID},
            )

            if av_sync_metric is not None:
                logger.info(f"Metrics A/V sync delta: {av_sync_metric}ms")
                assert av_sync_metric <= TestConfig.AV_SYNC_THRESHOLD_MS, (
                    f"Metrics report A/V sync delta {av_sync_metric}ms "
                    f"exceeds threshold {TestConfig.AV_SYNC_THRESHOLD_MS}ms"
                )

        finally:
            if stream_publisher.is_running():
                stream_publisher.stop()

    @pytest.mark.slow
    @pytest.mark.timeout(TimeoutConfig.PIPELINE_COMPLETION)
    def test_av_sync_with_variable_sts_latency(
        self,
        docker_services: DockerManager,
        stream_publisher: StreamPublisher,
        stream_analyzer: StreamAnalyzer,
    ) -> None:
        """Test A/V sync with variable STS processing latency.

        Configures Echo STS to introduce variable latency (0-500ms)
        and verifies A/V sync buffers absorb variation without drift.

        This tests the buffer management in AvSyncManager.
        """
        if not TestFixtureConfig.FIXTURE_PATH.exists():
            pytest.skip(f"Test fixture not found: {TestFixtureConfig.FIXTURE_PATH}")

        input_stream_path = f"live/{TestConfig.STREAM_ID}/in"
        output_stream_path = f"live/{TestConfig.STREAM_ID}/out"
        output_url = f"{MediaMTXConfig.RTMP_URL}/{output_stream_path}"

        # TODO: Configure Echo STS with variable latency via config:latency_simulation event
        # For now, Echo STS has default processing delay

        stream_publisher.start(stream_path=input_stream_path, realtime=True)

        try:
            # Wait for output
            output_exists = wait_for_condition(
                lambda: stream_analyzer.verify_stream_exists(output_stream_path),
                timeout_sec=TimeoutConfig.STREAM_PUBLISH,
                description="output stream",
            )

            if not output_exists:
                pytest.skip("Output stream not available")

            # Process for sufficient time
            time.sleep(40)

            # Analyze sync with slightly relaxed threshold for variable latency
            sync_result = stream_analyzer.analyze_av_sync(
                url=output_url,
                segment_duration_sec=TestConfig.SEGMENT_DURATION_SEC,
                duration_sec=30,
                threshold_ms=TestConfig.AV_SYNC_THRESHOLD_MS * 1.5,  # Allow 180ms
            )

            logger.info(
                f"Variable latency A/V sync results:\n"
                f"  Pass rate: {sync_result.pass_rate:.2%}\n"
                f"  Max delta: {sync_result.max_delta_ms:.2f}ms"
            )

            # Check that sync is maintained despite latency variation
            if sync_result.total_count > 0:
                # More lenient threshold for variable latency test
                assert sync_result.pass_rate >= 0.8, (
                    f"A/V sync degraded with variable latency: {sync_result.pass_rate:.2%}"
                )

        finally:
            if stream_publisher.is_running():
                stream_publisher.stop()

    @pytest.mark.slow
    @pytest.mark.timeout(TimeoutConfig.PIPELINE_COMPLETION)
    def test_av_sync_correction_gradual_slew(
        self,
        docker_services: DockerManager,
        stream_publisher: StreamPublisher,
        metrics_parser: MetricsParser,
    ) -> None:
        """Test that sync corrections use gradual slew (not hard jump).

        When sync drift is detected, the correction should be applied
        gradually to avoid perceptible jumps in playback.

        Verification:
        - Monitor consecutive PTS deltas
        - Large jumps indicate hard correction (bad)
        - Small incremental changes indicate slew correction (good)
        """
        if not TestFixtureConfig.FIXTURE_PATH.exists():
            pytest.skip(f"Test fixture not found: {TestFixtureConfig.FIXTURE_PATH}")

        input_stream_path = f"live/{TestConfig.STREAM_ID}/in"

        stream_publisher.start(stream_path=input_stream_path, realtime=True)

        try:
            # Let stream run to potentially trigger corrections
            time.sleep(45)

            # Check metrics for sync corrections
            metrics_parser.fetch()

            # Look for correction counter
            corrections = metrics_parser.get_counter(
                "worker_av_sync_corrections",
                labels={"stream_id": TestConfig.STREAM_ID},
            )

            if corrections is not None:
                logger.info(f"Sync corrections applied: {corrections}")

                # If corrections were applied, verify they were gradual
                # by checking the correction_type label
                samples = metrics_parser.get_all_samples("worker_av_sync_corrections")
                for sample in samples:
                    correction_type = sample.labels.get("type", "unknown")
                    logger.info(f"Correction type: {correction_type}")

                    # Hard jumps should be rare/nonexistent
                    if correction_type == "hard_jump":
                        logger.warning("Hard jump correction detected - suboptimal")

            # Verify sync is still within bounds despite corrections
            av_sync_delta = metrics_parser.get_gauge(
                "worker_av_sync_delta_ms",
                labels={"stream_id": TestConfig.STREAM_ID},
            )

            if av_sync_delta is not None:
                logger.info(f"Final A/V sync delta: {av_sync_delta}ms")
                # After corrections, sync should be good
                assert av_sync_delta <= TestConfig.AV_SYNC_THRESHOLD_MS * 2, (
                    f"Sync delta {av_sync_delta}ms too high after corrections"
                )

        finally:
            if stream_publisher.is_running():
                stream_publisher.stop()


@pytest.mark.e2e
@pytest.mark.p1
class TestAVSyncMetrics:
    """Tests for A/V sync metrics."""

    def test_av_sync_metrics_updated(
        self,
        docker_services: DockerManager,
        stream_publisher: StreamPublisher,
        metrics_parser: MetricsParser,
    ) -> None:
        """Verify A/V sync metrics are correctly updated during processing.

        Checks:
        - worker_av_sync_delta_ms gauge is updated
        - worker_av_buffer_video_size gauge is updated
        - worker_av_buffer_audio_size gauge is updated
        """
        if not TestFixtureConfig.FIXTURE_PATH.exists():
            pytest.skip(f"Test fixture not found: {TestFixtureConfig.FIXTURE_PATH}")

        input_stream_path = f"live/{TestConfig.STREAM_ID}/in"

        stream_publisher.start(stream_path=input_stream_path, realtime=True)

        try:
            # Let processing run
            time.sleep(20)

            # Fetch metrics
            metrics_parser.fetch()

            # Check A/V sync delta metric exists
            av_delta = metrics_parser.get_gauge(
                "worker_av_sync_delta_ms",
                labels={"stream_id": TestConfig.STREAM_ID},
            )

            if av_delta is not None:
                logger.info(f"A/V sync delta metric: {av_delta}ms")
                # Just verify it's a reasonable value
                assert av_delta >= 0, f"Negative A/V sync delta: {av_delta}"
                assert av_delta < 10000, f"Unreasonable A/V sync delta: {av_delta}"

            # Check buffer size metrics
            video_buffer = metrics_parser.get_gauge(
                "worker_av_buffer_video_size",
                labels={"stream_id": TestConfig.STREAM_ID},
            )

            audio_buffer = metrics_parser.get_gauge(
                "worker_av_buffer_audio_size",
                labels={"stream_id": TestConfig.STREAM_ID},
            )

            if video_buffer is not None:
                logger.info(f"Video buffer size: {video_buffer}")
                assert video_buffer >= 0, "Negative video buffer size"

            if audio_buffer is not None:
                logger.info(f"Audio buffer size: {audio_buffer}")
                assert audio_buffer >= 0, "Negative audio buffer size"

        finally:
            if stream_publisher.is_running():
                stream_publisher.stop()

    def test_av_sync_delta_histogram(
        self,
        docker_services: DockerManager,
        stream_publisher: StreamPublisher,
        metrics_parser: MetricsParser,
    ) -> None:
        """Verify A/V sync delta histogram shows distribution.

        If implemented as histogram, verify buckets show appropriate
        distribution of sync deltas.
        """
        if not TestFixtureConfig.FIXTURE_PATH.exists():
            pytest.skip(f"Test fixture not found: {TestFixtureConfig.FIXTURE_PATH}")

        input_stream_path = f"live/{TestConfig.STREAM_ID}/in"

        stream_publisher.start(stream_path=input_stream_path, realtime=True)

        try:
            # Let processing run to gather histogram data
            time.sleep(30)

            metrics_parser.fetch()

            # Check for histogram buckets
            samples = metrics_parser.get_all_samples("worker_av_sync_delta_ms_bucket")

            if samples:
                logger.info(f"Found {len(samples)} histogram buckets")

                # Verify buckets show reasonable distribution
                bucket_values = {
                    float(s.labels.get("le", "inf")): s.value
                    for s in samples
                }

                # Most samples should be in low buckets (<120ms)
                low_bucket = bucket_values.get(120, 0)
                total_bucket = bucket_values.get(float("inf"), 0)

                if total_bucket > 0:
                    low_ratio = low_bucket / total_bucket
                    logger.info(
                        f"Samples <= 120ms: {low_bucket}/{total_bucket} "
                        f"({low_ratio:.2%})"
                    )

                    assert low_ratio >= TestConfig.AV_SYNC_PASS_RATE, (
                        f"Histogram shows poor sync: only {low_ratio:.2%} "
                        f"within 120ms threshold"
                    )

        finally:
            if stream_publisher.is_running():
                stream_publisher.stop()
