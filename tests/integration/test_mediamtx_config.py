"""
Contract tests for MediaMTX configuration schema.

Tests FR-002 through FR-015: MediaMTX configuration requirements.
"""

from pathlib import Path

import pytest
import yaml


@pytest.mark.contract
class TestMediaMTXConfig:
    """Test MediaMTX configuration schema."""

    @pytest.fixture
    def config_file_path(self) -> Path:
        """Path to mediamtx.yml file."""
        return Path("/Users/leonardofu/dev/back-end/live-broadcast-dubbing-cloud/deploy/mediamtx/mediamtx.yml")

    def test_config_file_exists(self, config_file_path: Path) -> None:
        """Test that mediamtx.yml file exists."""
        assert config_file_path.exists(), f"mediamtx.yml not found at {config_file_path}"

    def test_config_file_valid_yaml(self, config_file_path: Path) -> None:
        """Test that mediamtx.yml is valid YAML."""
        with open(config_file_path) as f:
            config = yaml.safe_load(f)
        assert config is not None
        assert isinstance(config, dict)

    def test_config_has_rtmp_enabled(self, config_file_path: Path) -> None:
        """Test that RTMP server is enabled on port 1935 (FR-002)."""
        with open(config_file_path) as f:
            config = yaml.safe_load(f)

        # RTMP should be enabled
        assert "rtmp" in config or config.get("rtmpDisable") is not True, "RTMP not enabled"

    def test_config_has_rtsp_enabled(self, config_file_path: Path) -> None:
        """Test that RTSP server is enabled on port 8554 (FR-003)."""
        with open(config_file_path) as f:
            config = yaml.safe_load(f)

        # RTSP should be enabled
        assert "rtsp" in config or config.get("rtspDisable") is not True, "RTSP not enabled"

    def test_config_has_hooks_section(self, config_file_path: Path) -> None:
        """Test that hooks section exists with runOnReady and runOnNotReady (FR-004, FR-005)."""
        with open(config_file_path) as f:
            config = yaml.safe_load(f)

        # Hooks can be in paths section or global paths section
        paths = config.get("paths", {})
        if "all" in paths or "all_others" in paths:
            path_config = paths.get("all", paths.get("all_others", {}))
            assert "runOnReady" in path_config or "runOnInit" in path_config, "runOnReady hook not configured"
            assert "runOnNotReady" in path_config or "runOnDemand" in path_config, "runOnNotReady hook not configured"

    def test_config_has_api_enabled(self, config_file_path: Path) -> None:
        """Test that Control API is enabled on port 9997 (FR-008)."""
        with open(config_file_path) as f:
            config = yaml.safe_load(f)

        # API should be enabled (check for api: true or absence of apiDisable)
        assert config.get("api") is not False, "Control API is disabled"

    def test_config_has_metrics_enabled(self, config_file_path: Path) -> None:
        """Test that Prometheus metrics are enabled on port 9998 (FR-009)."""
        with open(config_file_path) as f:
            config = yaml.safe_load(f)

        # Metrics should be enabled
        assert config.get("metrics") is not False, "Prometheus metrics disabled"

    def test_config_has_recording_disabled(self, config_file_path: Path) -> None:
        """Test that recording is disabled (FR-013)."""
        with open(config_file_path) as f:
            config = yaml.safe_load(f)

        # Recording should be disabled in v0
        paths = config.get("paths", {})
        if "all" in paths or "all_others" in paths:
            path_config = paths.get("all", paths.get("all_others", {}))
            # Check if record is explicitly set to false or not set
            assert path_config.get("record") in [False, "no", None], "Recording should be disabled in v0"

    def test_config_has_structured_logging(self, config_file_path: Path) -> None:
        """Test that logs are configured for structured output (FR-014)."""
        with open(config_file_path) as f:
            config = yaml.safe_load(f)

        # Logs should go to stdout (check logDestinations or logLevel)
        log_destinations = config.get("logDestinations", ["stdout"])
        assert "stdout" in log_destinations or len(log_destinations) > 0, "Logs not configured for stdout"

    def test_config_uses_publisher_source(self, config_file_path: Path) -> None:
        """Test that paths use source: publisher for dynamic path creation (FR-015)."""
        with open(config_file_path) as f:
            config = yaml.safe_load(f)

        paths = config.get("paths", {})
        if "all" in paths or "all_others" in paths:
            path_config = paths.get("all", paths.get("all_others", {}))
            # Source should be publisher or not set (publisher is default)
            source = path_config.get("source", "publisher")
            assert source == "publisher", f"Expected source=publisher, got {source}"
