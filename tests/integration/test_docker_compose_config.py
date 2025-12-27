"""
Unit tests for Docker Compose configuration validation.

Tests FR-001: Docker Compose starts MediaMTX and stream-orchestration services.
"""

from pathlib import Path

import pytest
import yaml


@pytest.mark.unit
class TestDockerComposeConfig:
    """Test Docker Compose configuration validity."""

    @pytest.fixture
    def compose_file_path(self) -> Path:
        """Path to docker-compose.yml file."""
        return Path("/Users/leonardofu/dev/back-end/live-broadcast-dubbing-cloud/deploy/docker-compose.yml")

    def test_compose_file_exists(self, compose_file_path: Path) -> None:
        """Test that docker-compose.yml file exists."""
        assert compose_file_path.exists(), f"docker-compose.yml not found at {compose_file_path}"

    def test_compose_file_valid_yaml(self, compose_file_path: Path) -> None:
        """Test that docker-compose.yml is valid YAML."""
        with open(compose_file_path) as f:
            config = yaml.safe_load(f)
        assert config is not None
        assert isinstance(config, dict)

    def test_compose_has_required_services(self, compose_file_path: Path) -> None:
        """Test that docker-compose.yml includes required services."""
        with open(compose_file_path) as f:
            config = yaml.safe_load(f)

        assert "services" in config
        services = config["services"]

        # Required services for User Story 1
        assert "mediamtx" in services, "MediaMTX service not defined"
        assert "stream-orchestration" in services, "stream-orchestration service not defined"

    def test_mediamtx_service_configuration(self, compose_file_path: Path) -> None:
        """Test MediaMTX service has correct configuration."""
        with open(compose_file_path) as f:
            config = yaml.safe_load(f)

        mediamtx = config["services"]["mediamtx"]

        # Verify image is specified
        assert "image" in mediamtx, "MediaMTX image not specified"

        # Verify required ports are exposed
        assert "ports" in mediamtx, "MediaMTX ports not configured"
        ports = mediamtx["ports"]

        # Required ports: 1935 (RTMP), 8554 (RTSP), 9997 (API), 9998 (metrics), 9996 (playback)
        port_numbers = [str(p).split(":")[0] for p in ports]
        assert "1935" in port_numbers, "RTMP port 1935 not exposed"
        assert "8554" in port_numbers, "RTSP port 8554 not exposed"
        assert "9997" in port_numbers, "API port 9997 not exposed"
        assert "9998" in port_numbers, "Metrics port 9998 not exposed"

    def test_stream_orchestration_service_configuration(self, compose_file_path: Path) -> None:
        """Test stream-orchestration service has correct configuration."""
        with open(compose_file_path) as f:
            config = yaml.safe_load(f)

        orchestrator = config["services"]["stream-orchestration"]

        # Verify build context or image is specified
        assert "build" in orchestrator or "image" in orchestrator, "stream-orchestration build/image not specified"

        # Verify port 8080 is exposed
        assert "ports" in orchestrator, "stream-orchestration ports not configured"
        ports = orchestrator["ports"]
        port_numbers = [str(p).split(":")[0] for p in ports]
        assert "8080" in port_numbers, "stream-orchestration port 8080 not exposed"

    def test_compose_has_networks(self, compose_file_path: Path) -> None:
        """Test that docker-compose.yml defines custom network for service discovery."""
        with open(compose_file_path) as f:
            config = yaml.safe_load(f)

        # Should have networks section
        assert "networks" in config or all(
            "networks" in svc for svc in config["services"].values()
        ), "No custom network defined"
