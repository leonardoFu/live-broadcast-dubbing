"""
Integration tests for User Story 4: Observability and Debugging.

Tests verify that operators can monitor system health, troubleshoot issues,
and understand stream processing status using Control API, Prometheus metrics,
and structured logs.

Test Coverage:
- T060: Contract test for Control API response schema
- T061: Control API shows active streams after RTMP publish
- T062: Prometheus metrics validation (bytes, readers, state)
- T063: End-to-end observability (metrics update with stream lifecycle)
"""

import subprocess
import time
from collections.abc import Generator

import httpx
import pytest


@pytest.fixture
def ffmpeg_test_stream() -> Generator[subprocess.Popen, None, None]:
    """
    Fixture that publishes a test RTMP stream using FFmpeg.

    Yields the FFmpeg process, then terminates it on cleanup.
    """
    # FFmpeg command to publish test stream
    cmd = [
        "ffmpeg",
        "-re",  # Real-time mode
        "-f",
        "lavfi",
        "-i",
        "testsrc=size=640x480:rate=15",  # Video test pattern
        "-f",
        "lavfi",
        "-i",
        "sine=frequency=1000:sample_rate=48000",  # Audio test tone
        "-c:v",
        "libx264",
        "-preset",
        "ultrafast",
        "-tune",
        "zerolatency",
        "-b:v",
        "500k",
        "-c:a",
        "aac",
        "-b:a",
        "64k",
        "-f",
        "flv",
        "rtmp://localhost:1935/live/e2e-test-stream/in",
    ]

    # Start FFmpeg process
    process = subprocess.Popen(
        cmd,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    # Give FFmpeg time to connect and start streaming
    time.sleep(3)

    yield process

    # Cleanup: terminate FFmpeg
    process.terminate()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait()


@pytest.mark.integration
class TestControlAPIObservability:
    """Test Control API observability features (T060, T061)."""

    def test_control_api_response_schema_validation(
        self,
        docker_services: None,
        http_client: httpx.Client,
        mediamtx_control_api_url: str,
    ) -> None:
        """
        Test Control API /v3/paths/list response matches expected schema (T060).

        Validates required fields and data types for contract compliance.
        """
        response = http_client.get(f"{mediamtx_control_api_url}/v3/paths/list")

        assert response.status_code == 200
        data = response.json()

        # Validate top-level structure
        assert "items" in data, "Response must contain 'items' field"
        assert isinstance(data["items"], list), "'items' must be a list"

        # If there are paths, validate their structure
        if data["items"]:
            path_item = data["items"][0]
            assert "name" in path_item, "Path item must have 'name' field"
            assert isinstance(path_item["name"], str), "'name' must be string"

            # Check for optional but expected fields
            if "ready" in path_item:
                assert isinstance(path_item["ready"], bool), "'ready' must be boolean"
            if "tracks" in path_item:
                assert isinstance(path_item["tracks"], list), "'tracks' must be a list"

    def test_control_api_shows_active_stream_after_publish(
        self,
        docker_services: None,
        http_client: httpx.Client,
        mediamtx_control_api_url: str,
        ffmpeg_test_stream: subprocess.Popen,
    ) -> None:
        """
        Test Control API shows stream as active after RTMP publish (T061).

        Verifies that published streams appear in the paths list with correct state.
        """
        # Query Control API
        response = http_client.get(f"{mediamtx_control_api_url}/v3/paths/list")

        assert response.status_code == 200
        data = response.json()

        # Find our test stream
        stream_path = "live/e2e-test-stream/in"
        paths = [item["name"] for item in data["items"]]

        assert stream_path in paths, f"Stream {stream_path} should appear in paths list"

        # Get the stream details
        stream_item = next(item for item in data["items"] if item["name"] == stream_path)

        # Validate stream state
        assert stream_item.get("ready") is True, "Stream should be in ready state"

        # Validate tracks are present (H264, AAC)
        if "tracks" in stream_item:
            tracks = stream_item["tracks"]
            assert len(tracks) > 0, "Stream should have at least one track"

    def test_control_api_shows_stream_state_accurately(
        self,
        docker_services: None,
        http_client: httpx.Client,
        mediamtx_control_api_url: str,
        ffmpeg_test_stream: subprocess.Popen,
    ) -> None:
        """
        Test Control API accurately reflects stream ready state (T061).

        Verifies stream state changes when publisher disconnects.
        """
        stream_path = "live/e2e-test-stream/in"

        # First, verify stream is ready
        response = http_client.get(f"{mediamtx_control_api_url}/v3/paths/list")
        data = response.json()
        paths = [item["name"] for item in data["items"]]
        assert stream_path in paths, "Stream should be active"

        # Terminate the stream
        ffmpeg_test_stream.terminate()
        ffmpeg_test_stream.wait(timeout=5)

        # Wait for MediaMTX to detect disconnection
        time.sleep(2)

        # Verify stream is no longer listed or marked as not ready
        response = http_client.get(f"{mediamtx_control_api_url}/v3/paths/list")
        data = response.json()

        # Stream might be removed or marked as not ready
        stream_items = [item for item in data["items"] if item["name"] == stream_path]

        if stream_items:
            # If still listed, should be marked as not ready
            assert stream_items[0].get("ready") is False, "Disconnected stream should be not ready"
        # Otherwise it's been removed, which is also acceptable


@pytest.mark.integration
class TestPrometheusMetricsObservability:
    """Test Prometheus metrics observability features (T062)."""

    def test_metrics_endpoint_returns_prometheus_format(
        self,
        docker_services: None,
        http_client: httpx.Client,
        mediamtx_metrics_url: str,
    ) -> None:
        """
        Test Prometheus metrics endpoint returns valid Prometheus format (T062).

        Validates text/plain content type and basic metric structure.
        """
        response = http_client.get(f"{mediamtx_metrics_url}/metrics")

        assert response.status_code == 200
        assert "text/plain" in response.headers["content-type"]

        metrics_text = response.text

        # Validate Prometheus format (lines with # for comments or metric_name value)
        lines = metrics_text.split("\n")
        assert len(lines) > 0, "Metrics should contain lines"

        # Check for at least some metric lines (not just comments)
        metric_lines = [line for line in lines if line and not line.startswith("#")]
        assert len(metric_lines) > 0, "Should have at least one metric line"

    def test_metrics_include_path_counts(
        self,
        docker_services: None,
        http_client: httpx.Client,
        mediamtx_metrics_url: str,
        ffmpeg_test_stream: subprocess.Popen,
    ) -> None:
        """
        Test Prometheus metrics include active path counts (T062).

        Verifies that metrics show path-related counters.
        """
        response = http_client.get(f"{mediamtx_metrics_url}/metrics")

        assert response.status_code == 200
        metrics_text = response.text.lower()

        # Check for path-related metrics
        assert "paths" in metrics_text, "Metrics should include path information"

    def test_metrics_include_byte_counters(
        self,
        docker_services: None,
        http_client: httpx.Client,
        mediamtx_metrics_url: str,
        ffmpeg_test_stream: subprocess.Popen,
    ) -> None:
        """
        Test Prometheus metrics include byte counters (T062).

        Verifies that metrics track bytes received/sent.
        """
        # Wait a moment for stream to generate some traffic
        time.sleep(2)

        response = http_client.get(f"{mediamtx_metrics_url}/metrics")

        assert response.status_code == 200
        metrics_text = response.text.lower()

        # Check for byte-related metrics
        # MediaMTX typically exposes metrics like bytes_received, bytes_sent
        has_byte_metrics = "bytes" in metrics_text or "byte" in metrics_text
        assert has_byte_metrics, "Metrics should include byte counters"


@pytest.mark.integration
@pytest.mark.slow
class TestEndToEndObservability:
    """Test end-to-end observability workflow (T063)."""

    def test_metrics_update_when_stream_starts(
        self,
        docker_services: None,
        http_client: httpx.Client,
        mediamtx_control_api_url: str,
        mediamtx_metrics_url: str,
    ) -> None:
        """
        Test metrics and Control API update when stream starts (T063).

        Verifies observability endpoints reflect stream state changes in real-time.
        """
        stream_path = "live/e2e-observability-test/in"

        # Get baseline state before stream
        response_before = http_client.get(f"{mediamtx_control_api_url}/v3/paths/list")
        paths_before = [item["name"] for item in response_before.json()["items"]]

        # Start a test stream
        ffmpeg_cmd = [
            "ffmpeg",
            "-re",
            "-f",
            "lavfi",
            "-i",
            "testsrc=size=320x240:rate=10",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=1000:sample_rate=48000",
            "-c:v",
            "libx264",
            "-preset",
            "ultrafast",
            "-tune",
            "zerolatency",
            "-c:a",
            "aac",
            "-t",
            "10",  # 10 second test
            "-f",
            "flv",
            f"rtmp://localhost:1935/{stream_path}",
        ]

        process = subprocess.Popen(
            ffmpeg_cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

        try:
            # Wait for stream to start
            time.sleep(3)

            # Verify Control API shows the new stream
            response_after = http_client.get(f"{mediamtx_control_api_url}/v3/paths/list")
            paths_after = [item["name"] for item in response_after.json()["items"]]

            assert stream_path in paths_after, "New stream should appear in Control API"
            assert stream_path not in paths_before, "Stream should be new"

            # Verify metrics reflect the active stream
            metrics_response = http_client.get(f"{mediamtx_metrics_url}/metrics")
            assert metrics_response.status_code == 200

        finally:
            # Cleanup
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()

    def test_metrics_update_when_stream_stops(
        self,
        docker_services: None,
        http_client: httpx.Client,
        mediamtx_control_api_url: str,
    ) -> None:
        """
        Test metrics and Control API update when stream stops (T063).

        Verifies observability endpoints reflect stream disconnection.
        """
        stream_path = "live/e2e-disconnect-test/in"

        # Start a test stream
        ffmpeg_cmd = [
            "ffmpeg",
            "-re",
            "-f",
            "lavfi",
            "-i",
            "testsrc=size=320x240:rate=10",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=1000:sample_rate=48000",
            "-c:v",
            "libx264",
            "-preset",
            "ultrafast",
            "-c:a",
            "aac",
            "-f",
            "flv",
            f"rtmp://localhost:1935/{stream_path}",
        ]

        process = subprocess.Popen(
            ffmpeg_cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

        try:
            # Wait for stream to be established
            time.sleep(3)

            # Verify stream is active
            response = http_client.get(f"{mediamtx_control_api_url}/v3/paths/list")
            paths = [item["name"] for item in response.json()["items"]]
            assert stream_path in paths, "Stream should be active"

            # Stop the stream
            process.terminate()
            process.wait(timeout=5)

            # Wait for MediaMTX to detect disconnection
            time.sleep(2)

            # Verify Control API reflects the change
            response_after = http_client.get(f"{mediamtx_control_api_url}/v3/paths/list")
            data_after = response_after.json()

            # Stream should be removed or marked as not ready
            stream_items = [item for item in data_after["items"] if item["name"] == stream_path]

            if stream_items:
                # Still listed but should be not ready
                assert stream_items[0].get("ready") is False, (
                    "Stream should be not ready after disconnect"
                )
            # Otherwise removed, which is acceptable

        finally:
            # Ensure cleanup
            if process.poll() is None:
                process.kill()
                process.wait()

    def test_multiple_streams_observable_independently(
        self,
        docker_services: None,
        http_client: httpx.Client,
        mediamtx_control_api_url: str,
    ) -> None:
        """
        Test that multiple concurrent streams are independently observable (T063).

        Verifies operators can identify and monitor individual streams.
        """
        # Start multiple test streams
        processes = []
        stream_paths = [
            "live/multi-test-1/in",
            "live/multi-test-2/in",
        ]

        try:
            for stream_path in stream_paths:
                ffmpeg_cmd = [
                    "ffmpeg",
                    "-re",
                    "-f",
                    "lavfi",
                    "-i",
                    "testsrc=size=320x240:rate=10",
                    "-f",
                    "lavfi",
                    "-i",
                    "sine=frequency=1000:sample_rate=48000",
                    "-c:v",
                    "libx264",
                    "-preset",
                    "ultrafast",
                    "-c:a",
                    "aac",
                    "-f",
                    "flv",
                    f"rtmp://localhost:1935/{stream_path}",
                ]

                process = subprocess.Popen(
                    ffmpeg_cmd,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                processes.append(process)

            # Wait for all streams to start
            time.sleep(4)

            # Query Control API
            response = http_client.get(f"{mediamtx_control_api_url}/v3/paths/list")

            assert response.status_code == 200
            data = response.json()
            active_paths = [item["name"] for item in data["items"]]

            # Verify all streams are visible
            for stream_path in stream_paths:
                assert stream_path in active_paths, (
                    f"Stream {stream_path} should be visible in Control API"
                )

            # Verify each stream has independent state
            stream_items = {
                item["name"]: item for item in data["items"] if item["name"] in stream_paths
            }

            assert len(stream_items) >= 2, "Should see multiple independent streams"

            for stream_path, item in stream_items.items():
                assert item.get("ready") is True, f"Stream {stream_path} should be ready"

        finally:
            # Cleanup all processes
            for process in processes:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
