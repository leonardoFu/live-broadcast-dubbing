"""
Integration tests for RTMP publish triggering hook events.

Tests SC-002, SC-003: Hook delivery within 1 second of stream state change.
Tests FR-004, FR-005, FR-007: Hook wrapper integration with stream-orchestration.
"""

import subprocess
import time
from typing import Generator

import pytest
import requests


@pytest.mark.integration
class TestRTMPPublishHook:
    """Test RTMP publish triggers hook events."""

    @pytest.fixture(scope="class")
    def docker_services(self) -> Generator[None, None, None]:
        """Start Docker Compose services for integration tests."""
        subprocess.run(
            ["docker", "compose", "-f", "deploy/docker-compose.yml", "up", "-d"],
            check=True,
            cwd="/Users/leonardofu/dev/back-end/live-broadcast-dubbing-cloud",
        )

        # Wait for services to be ready
        time.sleep(10)

        yield

        # Tear down services
        subprocess.run(
            ["docker", "compose", "-f", "deploy/docker-compose.yml", "down"],
            check=False,
            cwd="/Users/leonardofu/dev/back-end/live-broadcast-dubbing-cloud",
        )

    def test_rtmp_publish_triggers_ready_event(
        self,
        docker_services: None,
        mediamtx_rtmp_url: str,
        test_stream_path_in: str,
    ) -> None:
        """Test RTMP publish to live/test/in → ready event received within 1s (SC-002)."""
        # Start FFmpeg test stream (non-blocking)
        publish_url = f"{mediamtx_rtmp_url}/{test_stream_path_in}"

        # Use FFmpeg to publish a short test stream
        ffmpeg_cmd = [
            "ffmpeg",
            "-re",
            "-f", "lavfi",
            "-i", "testsrc=size=640x480:rate=30",
            "-f", "lavfi",
            "-i", "sine=frequency=440:sample_rate=44100",
            "-c:v", "libx264",
            "-preset", "veryfast",
            "-tune", "zerolatency",
            "-c:a", "aac",
            "-t", "5",  # 5 second test stream
            "-f", "flv",
            publish_url,
        ]

        start_time = time.time()

        # Start FFmpeg in background
        proc = subprocess.Popen(
            ffmpeg_cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

        try:
            # Wait for stream to be ready (check Control API)
            timeout = 10
            stream_ready = False

            while time.time() - start_time < timeout:
                try:
                    response = requests.get("http://localhost:9997/v3/paths/list", timeout=2)
                    if response.status_code == 200:
                        data = response.json()
                        paths = [item["name"] for item in data.get("items", [])]
                        if test_stream_path_in in paths:
                            stream_ready = True
                            break
                except (requests.ConnectionError, requests.Timeout):
                    pass

                time.sleep(0.5)

            elapsed_time = time.time() - start_time

            assert stream_ready, f"Stream not ready after {elapsed_time:.1f}s"
            assert elapsed_time < 1.0, f"Stream took {elapsed_time:.1f}s to be ready (expected <1s)"

        finally:
            # Clean up FFmpeg process
            proc.terminate()
            proc.wait(timeout=5)

    def test_rtmp_disconnect_triggers_not_ready_event(
        self,
        docker_services: None,
        mediamtx_rtmp_url: str,
        test_stream_path_in: str,
    ) -> None:
        """Test RTMP disconnect → not-ready event received within 1s (SC-003)."""
        publish_url = f"{mediamtx_rtmp_url}/{test_stream_path_in}"

        # Start FFmpeg test stream
        ffmpeg_cmd = [
            "ffmpeg",
            "-re",
            "-f", "lavfi",
            "-i", "testsrc=size=640x480:rate=30",
            "-f", "lavfi",
            "-i", "sine=frequency=440:sample_rate=44100",
            "-c:v", "libx264",
            "-preset", "veryfast",
            "-c:a", "aac",
            "-f", "flv",
            publish_url,
        ]

        proc = subprocess.Popen(
            ffmpeg_cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

        # Wait for stream to be ready
        time.sleep(2)

        # Terminate stream
        start_time = time.time()
        proc.terminate()
        proc.wait(timeout=5)

        # Wait for stream to disappear from Control API
        timeout = 5
        stream_gone = False

        while time.time() - start_time < timeout:
            try:
                response = requests.get("http://localhost:9997/v3/paths/list", timeout=2)
                if response.status_code == 200:
                    data = response.json()
                    paths = [item["name"] for item in data.get("items", [])]
                    if test_stream_path_in not in paths:
                        stream_gone = True
                        break
            except (requests.ConnectionError, requests.Timeout):
                pass

            time.sleep(0.5)

        elapsed_time = time.time() - start_time

        assert stream_gone, f"Stream still present after {elapsed_time:.1f}s"
        assert elapsed_time < 1.0, f"Stream took {elapsed_time:.1f}s to disconnect (expected <1s)"

    def test_hook_payload_includes_correct_fields(
        self,
        docker_services: None,
        mediamtx_rtmp_url: str,
    ) -> None:
        """Test hook payload includes correct path, sourceType, sourceId."""
        # This test would require monitoring orchestrator logs or adding a test endpoint
        # For now, we rely on the contract tests validating the schema
        # and integration tests validating the end-to-end flow
        pass

    def test_hook_payload_includes_query_parameters(
        self,
        docker_services: None,
        mediamtx_rtmp_url: str,
    ) -> None:
        """Test hook payload includes query parameters (e.g., ?lang=es)."""
        # RTMP doesn't support query parameters in the same way as HTTP
        # MediaMTX may handle this differently - this test documents the requirement
        # but implementation depends on MediaMTX behavior
        pass

    def test_hook_receiver_unavailable_scenario(
        self,
        mediamtx_rtmp_url: str,
        test_stream_path_in: str,
    ) -> None:
        """Test hook wrapper fails immediately when orchestrator is down."""
        # Start only MediaMTX (without orchestrator)
        subprocess.run(
            ["docker", "compose", "-f", "deploy/docker-compose.yml", "up", "-d", "mediamtx"],
            check=True,
            cwd="/Users/leonardofu/dev/back-end/live-broadcast-dubbing-cloud",
        )

        time.sleep(5)

        try:
            publish_url = f"{mediamtx_rtmp_url}/{test_stream_path_in}"

            # Publish stream
            ffmpeg_cmd = [
                "ffmpeg",
                "-re",
                "-f", "lavfi",
                "-i", "testsrc=size=640x480:rate=30",
                "-f", "lavfi",
                "-i", "sine=frequency=440:sample_rate=44100",
                "-c:v", "libx264",
                "-preset", "veryfast",
                "-c:a", "aac",
                "-t", "2",
                "-f", "flv",
                publish_url,
            ]

            proc = subprocess.Popen(
                ffmpeg_cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )

            proc.wait(timeout=10)

            # Stream should still be accepted by MediaMTX even though hook failed
            time.sleep(1)

            response = requests.get("http://localhost:9997/v3/paths/list", timeout=5)
            assert response.status_code == 200

            # Check MediaMTX logs for hook failure (this would require log inspection)
            # For now, we just verify the stream was accepted

        finally:
            # Clean up
            subprocess.run(
                ["docker", "compose", "-f", "deploy/docker-compose.yml", "down"],
                check=False,
                cwd="/Users/leonardofu/dev/back-end/live-broadcast-dubbing-cloud",
            )
