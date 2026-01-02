"""Dual Compose E2E Test: Full Pipeline (User Story 1).

Tests the complete dubbing pipeline with real STS service:
- Test fixture published to MediaMTX
- WorkerRunner ingests RTSP stream
- Segments sent to real STS service (ASR + Translation + TTS)
- Dubbed audio returns via Socket.IO
- A/V sync and remux
- New RTMP stream output

Priority: P1 (MVP)
"""

import asyncio
import logging
from pathlib import Path

import httpx
import pytest

from tests.e2e.helpers.metrics_parser import MetricsParser
from tests.e2e.helpers.stream_analyzer import StreamAnalyzer

logger = logging.getLogger(__name__)


@pytest.mark.e2e
@pytest.mark.slow
@pytest.mark.requires_docker
@pytest.mark.requires_sts
@pytest.mark.full_pipeline
@pytest.mark.asyncio
async def test_full_pipeline_media_to_sts_to_output(
    dual_compose_env,
    publish_test_fixture,
    sts_monitor,
):
    """Test complete dubbing pipeline from fixture to dubbed output.

    Test Scenario:
    1. Start dual compose environments (media + STS)
    2. Publish 1-min NFL fixture to MediaMTX RTSP
    3. Verify WorkerRunner connects and starts processing
    4. Verify all 10 segments (6s each) sent to real STS service
    5. Verify all fragments return with real dubbed audio
    6. Verify output RTMP stream available and playable
    7. Verify pipeline completes within 300s (allowing real STS latency)

    Expected Results:
    - WorkerRunner connects within 5s
    - 10 segments processed (60s / 6s = 10)
    - All fragment:processed events received with dubbed_audio
    - Output stream duration matches input (60s +/- 1s)
    - A/V sync delta < 120ms throughout
    - Pipeline completes within 300s total

    This test MUST initially FAIL because:
    - Docker compose files may not be complete
    - Health checks may not be configured
    - STS service may not be running
    - Services may not be able to communicate
    """
    # Test setup validation
    stream_path, rtmp_url = publish_test_fixture
    assert stream_path is not None, "Stream path should be provided"
    assert rtmp_url is not None, "RTMP URL should be provided"

    logger.info(f"Test fixture publishing to: {rtmp_url}")
    logger.info(f"Expected output stream: rtmp://localhost:1935/live/{stream_path.replace('/in', '/out')}")

    # Step 1: Verify MediaMTX received the stream
    logger.info("Step 1: Verifying MediaMTX received stream...")
    mediamtx_api = "http://localhost:8889"

    # Wait for stream to be active in MediaMTX
    stream_active = False
    available_paths = []
    for attempt in range(10):
        try:
            async with httpx.AsyncClient(follow_redirects=True) as client:
                resp = await client.get(f"{mediamtx_api}/v3/paths/list")
                resp.raise_for_status()
                paths = resp.json()

                # Debug logging
                logger.debug(f"Attempt {attempt + 1}: MediaMTX API response: {paths}")
                available_paths = [p.get("name", "") for p in paths.get("items", [])]
                logger.debug(f"Available paths: {available_paths}")

                # Check if our stream is in the list
                stream_name = stream_path.split("/")[1]  # Extract stream name
                logger.debug(f"Looking for stream containing: {stream_name}")

                if any(stream_name in p.get("name", "") for p in paths.get("items", [])):
                    stream_active = True
                    matching_path = [p for p in available_paths if stream_name in p][0]
                    logger.info(f"Stream {stream_name} is active in MediaMTX")
                    logger.info(f"Full path: {matching_path}")
                    break
        except Exception as e:
            logger.warning(f"Attempt {attempt + 1}: MediaMTX check failed: {e}")

        await asyncio.sleep(1)

    # Log failure details if stream didn't appear
    if not stream_active:
        logger.error(f"Stream {stream_path.split('/')[1]} never appeared in MediaMTX")
        logger.error(f"Final available paths: {available_paths if available_paths else 'N/A'}")

    assert stream_active, "Stream should be active in MediaMTX within 10 seconds"

    # Step 2: Verify WorkerRunner connects and starts processing
    logger.info("Step 2: Verifying WorkerRunner connects...")

    # Wait for media-service to start processing (check metrics)
    metrics_parser = MetricsParser(metrics_url="http://localhost:8080/metrics")

    worker_connected = False
    for attempt in range(10):
        try:
            metrics = metrics_parser.get_all_metrics()

            # Check for worker metrics (indicates WorkerRunner has started and connected to STS)
            # Look for any of: worker_info, sts_inflight_fragments, or circuit_breaker_state
            worker_metrics = [k for k in metrics.keys() if any(
                metric_name in k for metric_name in [
                    "media_service_worker_info_info",
                    "media_service_worker_sts_inflight_fragments",
                    "media_service_worker_circuit_breaker_state"
                ]
            )]

            if worker_metrics:
                worker_connected = True
                logger.info(f"WorkerRunner has started (found metrics: {worker_metrics})")
                break
        except Exception as e:
            logger.debug(f"Attempt {attempt + 1}: Metrics check failed: {e}")

        await asyncio.sleep(1)

    assert worker_connected, "WorkerRunner should connect and start within 10 seconds"

    # Step 3: Monitor Socket.IO events for fragment:processed
    logger.info("Step 3: Monitoring Socket.IO for fragment:processed events...")

    # Expected: 10 segments (60s / 6s = 10)
    expected_segments = 10

    try:
        # Wait for all fragment:processed events (timeout 300s for real STS latency)
        processed_events = await sts_monitor.wait_for_events(
            event_name="fragment:processed",
            count=expected_segments,
            timeout=300.0,
        )

        assert len(processed_events) == expected_segments, \
            f"Expected {expected_segments} fragment:processed events, got {len(processed_events)}"

        logger.info(f"Received {len(processed_events)} fragment:processed events")

        # Step 4: Verify each event has dubbed_audio
        logger.info("Step 4: Verifying fragment:processed events contain dubbed_audio...")

        for idx, event in enumerate(processed_events):
            data = event.data
            assert "dubbed_audio" in data, \
                f"Event {idx + 1} should contain dubbed_audio field"
            assert data["dubbed_audio"] is not None, \
                f"Event {idx + 1} dubbed_audio should not be None"
            assert len(data["dubbed_audio"]) > 0, \
                f"Event {idx + 1} dubbed_audio should not be empty"

            # Verify transcript and translation fields (real STS processing)
            assert "transcript" in data, \
                f"Event {idx + 1} should contain transcript field"
            assert "translated_text" in data, \
                f"Event {idx + 1} should contain translated_text field"

            logger.debug(
                f"Fragment {idx + 1}: transcript='{data.get('transcript', '')[:50]}...', "
                f"translation='{data.get('translated_text', '')[:50]}...'"
            )

        logger.info("All fragment:processed events valid")

    except asyncio.TimeoutError as e:
        # If timeout, capture metrics for debugging
        metrics = metrics_parser.get_all_metrics()
        logger.error(f"Timeout waiting for fragment:processed events. Metrics: {metrics}")
        raise AssertionError(f"Timeout waiting for {expected_segments} fragment:processed events") from e

    # Step 5: Verify output RTMP stream is available
    logger.info("Step 5: Verifying output RTMP stream...")

    output_stream_path = stream_path.replace("/in", "/out")
    output_rtmp_url = f"rtmp://localhost:1935/{output_stream_path}"

    # Wait a bit for output stream to be published
    await asyncio.sleep(5)

    # Use ffprobe to verify output stream
    stream_analyzer = StreamAnalyzer(rtmp_base_url="rtmp://localhost:1935")

    try:
        stream_info = stream_analyzer.inspect_stream(output_stream_path)

        assert stream_info is not None, "Output stream should be available"
        assert "format" in stream_info, "Stream info should contain format"
        assert "streams" in stream_info, "Stream info should contain streams"

        # Verify video and audio tracks
        streams = stream_info["streams"]
        video_streams = [s for s in streams if s.get("codec_type") == "video"]
        audio_streams = [s for s in streams if s.get("codec_type") == "audio"]

        assert len(video_streams) >= 1, "Output should have at least 1 video stream"
        assert len(audio_streams) >= 1, "Output should have at least 1 audio stream"

        # Verify codecs
        assert video_streams[0].get("codec_name") == "h264", "Video codec should be h264"
        assert audio_streams[0].get("codec_name") == "aac", "Audio codec should be aac"

        # Verify duration (60s +/- 1s tolerance)
        duration = float(stream_info["format"].get("duration", 0))
        assert 59.0 <= duration <= 61.0, \
            f"Output duration should be ~60s, got {duration}s"

        logger.info(f"Output stream verified: duration={duration}s, video={video_streams[0]['codec_name']}, audio={audio_streams[0]['codec_name']}")

    except Exception as e:
        logger.error(f"Failed to verify output stream: {e}")
        raise AssertionError(f"Output stream verification failed: {e}") from e

    # Step 6: Verify metrics show successful processing
    logger.info("Step 6: Verifying metrics...")

    metrics = metrics_parser.get_all_metrics()

    # Verify segment processing metrics
    # Find all audio segment processing metrics for this stream
    audio_segment_metrics = {
        k: v for k, v in metrics.items()
        if "media_service_worker_segments_processed_total" in k
        and 'type="audio"' in k
    }
    processed_count = sum(audio_segment_metrics.values())

    assert processed_count == expected_segments, \
        f"Metrics should show {expected_segments} processed audio segments, got {processed_count}"

    # Verify A/V sync metrics (if available)
    if "worker_av_sync_delta_ms" in metrics:
        av_sync_delta = metrics["worker_av_sync_delta_ms"]
        assert av_sync_delta < 120, \
            f"A/V sync delta should be < 120ms, got {av_sync_delta}ms"
        logger.info(f"A/V sync delta: {av_sync_delta}ms")

    logger.info("Full pipeline test PASSED")


@pytest.mark.e2e
@pytest.mark.requires_docker
def test_docker_compose_files_exist():
    """Verify docker-compose.e2e.yml files exist for both services.

    This is a sanity check that should pass if files are created.
    """
    project_root = Path(__file__).parent.parent.parent

    media_compose = project_root / "apps/media-service/docker-compose.e2e.yml"
    sts_compose = project_root / "apps/sts-service/docker-compose.e2e.yml"

    assert media_compose.exists(), f"Media compose file should exist at {media_compose}"
    assert sts_compose.exists(), f"STS compose file should exist at {sts_compose}"

    logger.info("Docker compose files verified")


@pytest.mark.e2e
@pytest.mark.requires_docker
def test_test_fixture_exists():
    """Verify 1-min NFL test fixture exists.

    This is a sanity check that should pass if fixture is created.
    """
    fixture_path = Path(__file__).parent.parent / "fixtures/test-streams/1-min-nfl.mp4"

    assert fixture_path.exists(), f"Test fixture should exist at {fixture_path}"

    # Verify fixture properties with ffprobe
    import subprocess

    result = subprocess.run(
        ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", "-show_streams", str(fixture_path)],
        capture_output=True,
        text=True,
        check=True,
    )

    import json
    info = json.loads(result.stdout)

    duration = float(info["format"]["duration"])
    assert 59.0 <= duration <= 61.0, f"Fixture duration should be ~60s, got {duration}s"

    video_streams = [s for s in info["streams"] if s["codec_type"] == "video"]
    audio_streams = [s for s in info["streams"] if s["codec_type"] == "audio"]

    assert len(video_streams) == 1, "Fixture should have 1 video stream"
    assert len(audio_streams) == 1, "Fixture should have 1 audio stream"

    assert video_streams[0]["codec_name"] == "h264", "Video codec should be h264"
    assert audio_streams[0]["codec_name"] == "aac", "Audio codec should be aac"
    assert int(audio_streams[0]["sample_rate"]) == 44100, "Audio sample rate should be 44100Hz"

    logger.info(f"Test fixture verified: duration={duration}s, video=h264, audio=aac@44.1kHz")
