"""
Unit tests for SegmentationConfig.

Tests MUST be written FIRST per Constitution Principle VIII.
These tests verify VAD configuration loading from environment variables.

Per spec 023-vad-audio-segmentation:
- Default values match specification
- Environment variable loading works correctly
- Validation constraints enforced
- Nanosecond conversion properties work
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError


class TestSegmentationConfigDefaults:
    """Tests for default configuration values."""

    def test_default_values_match_specification(self):
        """Verify default values when no environment variables set."""
        from media_service.config.segmentation_config import SegmentationConfig

        config = SegmentationConfig()

        assert config.silence_threshold_db == -50.0
        assert config.silence_duration_s == 1.0
        assert config.min_segment_duration_s == 1.0
        assert config.max_segment_duration_s == 15.0
        assert config.level_interval_ns == 100_000_000  # 100ms
        assert config.memory_limit_bytes == 10_485_760  # 10MB

    def test_silence_threshold_db_default(self):
        """Verify silence threshold default is -50dB."""
        from media_service.config.segmentation_config import SegmentationConfig

        config = SegmentationConfig()
        assert config.silence_threshold_db == -50.0

    def test_silence_duration_s_default(self):
        """Verify silence duration default is 1.0 second."""
        from media_service.config.segmentation_config import SegmentationConfig

        config = SegmentationConfig()
        assert config.silence_duration_s == 1.0

    def test_min_segment_duration_s_default(self):
        """Verify min segment duration default is 1.0 second."""
        from media_service.config.segmentation_config import SegmentationConfig

        config = SegmentationConfig()
        assert config.min_segment_duration_s == 1.0

    def test_max_segment_duration_s_default(self):
        """Verify max segment duration default is 15.0 seconds."""
        from media_service.config.segmentation_config import SegmentationConfig

        config = SegmentationConfig()
        assert config.max_segment_duration_s == 15.0


class TestSegmentationConfigEnvironmentVariables:
    """Tests for environment variable loading."""

    def test_silence_threshold_db_from_env(self, monkeypatch):
        """Verify VAD_SILENCE_THRESHOLD_DB environment variable loading."""
        monkeypatch.setenv("VAD_SILENCE_THRESHOLD_DB", "-40")

        from media_service.config.segmentation_config import SegmentationConfig

        config = SegmentationConfig()
        assert config.silence_threshold_db == -40.0

    def test_silence_duration_s_from_env(self, monkeypatch):
        """Verify VAD_SILENCE_DURATION_S environment variable loading."""
        monkeypatch.setenv("VAD_SILENCE_DURATION_S", "0.5")

        from media_service.config.segmentation_config import SegmentationConfig

        config = SegmentationConfig()
        assert config.silence_duration_s == 0.5

    def test_min_segment_duration_s_from_env(self, monkeypatch):
        """Verify VAD_MIN_SEGMENT_DURATION_S environment variable loading."""
        monkeypatch.setenv("VAD_MIN_SEGMENT_DURATION_S", "2.0")

        from media_service.config.segmentation_config import SegmentationConfig

        config = SegmentationConfig()
        assert config.min_segment_duration_s == 2.0

    def test_max_segment_duration_s_from_env(self, monkeypatch):
        """Verify VAD_MAX_SEGMENT_DURATION_S environment variable loading."""
        monkeypatch.setenv("VAD_MAX_SEGMENT_DURATION_S", "20")

        from media_service.config.segmentation_config import SegmentationConfig

        config = SegmentationConfig()
        assert config.max_segment_duration_s == 20.0

    def test_level_interval_ns_from_env(self, monkeypatch):
        """Verify VAD_LEVEL_INTERVAL_NS environment variable loading."""
        monkeypatch.setenv("VAD_LEVEL_INTERVAL_NS", "200000000")

        from media_service.config.segmentation_config import SegmentationConfig

        config = SegmentationConfig()
        assert config.level_interval_ns == 200_000_000  # 200ms

    def test_memory_limit_bytes_from_env(self, monkeypatch):
        """Verify VAD_MEMORY_LIMIT_BYTES environment variable loading."""
        monkeypatch.setenv("VAD_MEMORY_LIMIT_BYTES", "20971520")

        from media_service.config.segmentation_config import SegmentationConfig

        config = SegmentationConfig()
        assert config.memory_limit_bytes == 20_971_520  # 20MB

    def test_multiple_env_vars_loaded(self, monkeypatch):
        """Verify multiple environment variables loaded correctly."""
        monkeypatch.setenv("VAD_SILENCE_THRESHOLD_DB", "-45")
        monkeypatch.setenv("VAD_MAX_SEGMENT_DURATION_S", "20")

        from media_service.config.segmentation_config import SegmentationConfig

        config = SegmentationConfig()
        assert config.silence_threshold_db == -45.0
        assert config.max_segment_duration_s == 20.0
        # Defaults still apply for unset vars
        assert config.silence_duration_s == 1.0


class TestSegmentationConfigValidation:
    """Tests for validation constraints."""

    def test_silence_threshold_db_above_max_raises_error(self):
        """Verify silence_threshold_db > 0 raises ValidationError."""
        from media_service.config.segmentation_config import SegmentationConfig

        with pytest.raises(ValidationError):
            SegmentationConfig(silence_threshold_db=10.0)

    def test_silence_threshold_db_below_min_raises_error(self):
        """Verify silence_threshold_db < -100 raises ValidationError."""
        from media_service.config.segmentation_config import SegmentationConfig

        with pytest.raises(ValidationError):
            SegmentationConfig(silence_threshold_db=-110.0)

    def test_silence_threshold_db_valid_range(self):
        """Verify silence_threshold_db accepts -100 to 0 range."""
        from media_service.config.segmentation_config import SegmentationConfig

        config = SegmentationConfig(silence_threshold_db=-100.0)
        assert config.silence_threshold_db == -100.0

        config = SegmentationConfig(silence_threshold_db=0.0)
        assert config.silence_threshold_db == 0.0

    def test_silence_duration_s_below_min_raises_error(self):
        """Verify silence_duration_s < 0.1 raises ValidationError."""
        from media_service.config.segmentation_config import SegmentationConfig

        with pytest.raises(ValidationError):
            SegmentationConfig(silence_duration_s=0.05)

    def test_silence_duration_s_above_max_raises_error(self):
        """Verify silence_duration_s > 5.0 raises ValidationError."""
        from media_service.config.segmentation_config import SegmentationConfig

        with pytest.raises(ValidationError):
            SegmentationConfig(silence_duration_s=6.0)

    def test_min_segment_duration_s_below_min_raises_error(self):
        """Verify min_segment_duration_s < 0.5 raises ValidationError."""
        from media_service.config.segmentation_config import SegmentationConfig

        with pytest.raises(ValidationError):
            SegmentationConfig(min_segment_duration_s=0.1)

    def test_min_segment_duration_s_above_max_raises_error(self):
        """Verify min_segment_duration_s > 5.0 raises ValidationError."""
        from media_service.config.segmentation_config import SegmentationConfig

        with pytest.raises(ValidationError):
            SegmentationConfig(min_segment_duration_s=6.0)

    def test_max_segment_duration_s_below_min_raises_error(self):
        """Verify max_segment_duration_s < 5.0 raises ValidationError."""
        from media_service.config.segmentation_config import SegmentationConfig

        with pytest.raises(ValidationError):
            SegmentationConfig(max_segment_duration_s=4.0)

    def test_max_segment_duration_s_above_max_raises_error(self):
        """Verify max_segment_duration_s > 60.0 raises ValidationError."""
        from media_service.config.segmentation_config import SegmentationConfig

        with pytest.raises(ValidationError):
            SegmentationConfig(max_segment_duration_s=70.0)

    def test_level_interval_ns_below_min_raises_error(self):
        """Verify level_interval_ns < 50ms raises ValidationError."""
        from media_service.config.segmentation_config import SegmentationConfig

        with pytest.raises(ValidationError):
            SegmentationConfig(level_interval_ns=10_000_000)  # 10ms

    def test_level_interval_ns_above_max_raises_error(self):
        """Verify level_interval_ns > 500ms raises ValidationError."""
        from media_service.config.segmentation_config import SegmentationConfig

        with pytest.raises(ValidationError):
            SegmentationConfig(level_interval_ns=600_000_000)  # 600ms

    def test_memory_limit_bytes_below_min_raises_error(self):
        """Verify memory_limit_bytes < 1MB raises ValidationError."""
        from media_service.config.segmentation_config import SegmentationConfig

        with pytest.raises(ValidationError):
            SegmentationConfig(memory_limit_bytes=500_000)  # 500KB

    def test_memory_limit_bytes_above_max_raises_error(self):
        """Verify memory_limit_bytes > 100MB raises ValidationError."""
        from media_service.config.segmentation_config import SegmentationConfig

        with pytest.raises(ValidationError):
            SegmentationConfig(memory_limit_bytes=200_000_000)  # 200MB


class TestSegmentationConfigNanosecondConversions:
    """Tests for nanosecond conversion properties."""

    def test_silence_duration_ns_conversion(self):
        """Verify silence_duration_ns property converts correctly."""
        from media_service.config.segmentation_config import SegmentationConfig

        config = SegmentationConfig(silence_duration_s=1.5)
        assert config.silence_duration_ns == 1_500_000_000

    def test_min_segment_duration_ns_conversion(self):
        """Verify min_segment_duration_ns property converts correctly."""
        from media_service.config.segmentation_config import SegmentationConfig

        config = SegmentationConfig(min_segment_duration_s=2.0)
        assert config.min_segment_duration_ns == 2_000_000_000

    def test_max_segment_duration_ns_conversion(self):
        """Verify max_segment_duration_ns property converts correctly."""
        from media_service.config.segmentation_config import SegmentationConfig

        config = SegmentationConfig(max_segment_duration_s=10.0)
        assert config.max_segment_duration_ns == 10_000_000_000

    def test_default_ns_conversions(self):
        """Verify default nanosecond conversions are correct."""
        from media_service.config.segmentation_config import SegmentationConfig

        config = SegmentationConfig()
        assert config.silence_duration_ns == 1_000_000_000  # 1s
        assert config.min_segment_duration_ns == 1_000_000_000  # 1s
        assert config.max_segment_duration_ns == 15_000_000_000  # 15s

    def test_fractional_seconds_ns_conversion(self):
        """Verify fractional seconds convert correctly to nanoseconds."""
        from media_service.config.segmentation_config import SegmentationConfig

        config = SegmentationConfig(
            silence_duration_s=0.5,
            min_segment_duration_s=0.75,
            max_segment_duration_s=7.5,
        )
        assert config.silence_duration_ns == 500_000_000  # 0.5s
        assert config.min_segment_duration_ns == 750_000_000  # 0.75s
        assert config.max_segment_duration_ns == 7_500_000_000  # 7.5s
