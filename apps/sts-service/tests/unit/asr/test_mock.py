"""
Unit tests for MockASRComponent.

TDD: These tests are written BEFORE implementation.
"""

import time

import pytest


class TestMockASRComponent:
    """Tests for MockASRComponent behavior."""

    def test_mock_asr_returns_configured_text(self):
        """Test that mock returns the configured text."""
        from sts_service.asr.mock import MockASRComponent, MockASRConfig

        config = MockASRConfig(default_text="Hello world test")
        mock = MockASRComponent(config=config)

        result = mock.transcribe(
            audio_data=b"ignored",
            stream_id="test",
            sequence_number=0,
            start_time_ms=0,
            end_time_ms=2000,
        )

        assert "Hello" in result.segments[0].text
        assert "world" in result.segments[0].text

    def test_mock_asr_returns_configured_confidence(self):
        """Test that mock returns the configured confidence."""
        from sts_service.asr.mock import MockASRComponent, MockASRConfig

        config = MockASRConfig(default_text="Test", default_confidence=0.85)
        mock = MockASRComponent(config=config)

        result = mock.transcribe(
            audio_data=b"ignored",
            stream_id="test",
            sequence_number=0,
            start_time_ms=0,
            end_time_ms=1000,
        )

        assert result.segments[0].confidence == pytest.approx(0.85, rel=0.01)

    def test_mock_asr_ignores_audio_content(self):
        """Test that mock produces same output regardless of audio."""
        from sts_service.asr.mock import MockASRComponent, MockASRConfig

        config = MockASRConfig(default_text="Same output")
        mock = MockASRComponent(config=config)

        result1 = mock.transcribe(
            audio_data=b"audio1",
            stream_id="test",
            sequence_number=0,
            start_time_ms=0,
            end_time_ms=1000,
        )

        result2 = mock.transcribe(
            audio_data=b"completely different audio",
            stream_id="test",
            sequence_number=1,
            start_time_ms=1000,
            end_time_ms=2000,
        )

        assert result1.segments[0].text == result2.segments[0].text

    def test_mock_asr_generates_timestamps_from_words(self):
        """Test that mock generates word timestamps."""
        from sts_service.asr.mock import MockASRComponent, MockASRConfig

        config = MockASRConfig(default_text="One two three")
        mock = MockASRComponent(config=config)

        result = mock.transcribe(
            audio_data=b"ignored",
            stream_id="test",
            sequence_number=0,
            start_time_ms=0,
            end_time_ms=3000,
        )

        # Should have word timestamps
        assert result.segments[0].words is not None
        assert len(result.segments[0].words) == 3  # "One", "two", "three"

    def test_mock_asr_respects_start_end_times(self):
        """Test that timestamps are within fragment bounds."""
        from sts_service.asr.mock import MockASRComponent, MockASRConfig

        config = MockASRConfig(default_text="Test text")
        mock = MockASRComponent(config=config)

        result = mock.transcribe(
            audio_data=b"ignored",
            stream_id="test",
            sequence_number=0,
            start_time_ms=5000,
            end_time_ms=7000,
        )

        segment = result.segments[0]
        assert segment.start_time_ms >= 5000
        assert segment.end_time_ms <= 7000

    def test_mock_asr_implements_protocol(self):
        """Test that MockASRComponent implements ASRComponent protocol."""
        from sts_service.asr.interface import ASRComponent
        from sts_service.asr.mock import MockASRComponent, MockASRConfig

        mock = MockASRComponent(config=MockASRConfig())

        assert isinstance(mock, ASRComponent)

    def test_mock_asr_is_ready_always_true(self):
        """Test that is_ready is always True for mock."""
        from sts_service.asr.mock import MockASRComponent, MockASRConfig

        mock = MockASRComponent(config=MockASRConfig())

        assert mock.is_ready is True

    def test_mock_asr_component_instance_name(self):
        """Test that component_instance returns mock identifier."""
        from sts_service.asr.mock import MockASRComponent, MockASRConfig

        mock = MockASRComponent(config=MockASRConfig())

        assert "mock" in mock.component_instance.lower()

    def test_mock_asr_failure_injection(self):
        """Test that failures can be injected."""
        from sts_service.asr.mock import MockASRComponent, MockASRConfig
        from sts_service.asr.models import TranscriptStatus

        config = MockASRConfig(
            failure_rate=1.0,  # Always fail
            failure_type="timeout",
        )
        mock = MockASRComponent(config=config)

        result = mock.transcribe(
            audio_data=b"ignored",
            stream_id="test",
            sequence_number=0,
            start_time_ms=0,
            end_time_ms=1000,
        )

        assert result.status == TranscriptStatus.FAILED
        assert len(result.errors) > 0

    def test_mock_asr_failure_rate_probability(self):
        """Test that failure rate is probabilistic."""
        from sts_service.asr.mock import MockASRComponent, MockASRConfig
        from sts_service.asr.models import TranscriptStatus

        config = MockASRConfig(
            failure_rate=0.0,  # Never fail
        )
        mock = MockASRComponent(config=config)

        # Run multiple times, should never fail
        for i in range(10):
            result = mock.transcribe(
                audio_data=b"ignored",
                stream_id="test",
                sequence_number=i,
                start_time_ms=0,
                end_time_ms=1000,
            )
            assert result.status == TranscriptStatus.SUCCESS

    def test_mock_asr_simulated_latency(self):
        """Test that latency can be simulated."""
        from sts_service.asr.mock import MockASRComponent, MockASRConfig

        config = MockASRConfig(simulate_latency_ms=100)
        mock = MockASRComponent(config=config)

        start = time.time()
        mock.transcribe(
            audio_data=b"ignored",
            stream_id="test",
            sequence_number=0,
            start_time_ms=0,
            end_time_ms=1000,
        )
        elapsed_ms = (time.time() - start) * 1000

        # Should have added ~100ms latency
        assert elapsed_ms >= 80  # Allow some tolerance

    def test_mock_asr_empty_text_returns_empty_segments(self):
        """Test that empty text returns empty segments."""
        from sts_service.asr.mock import MockASRComponent, MockASRConfig
        from sts_service.asr.models import TranscriptStatus

        config = MockASRConfig(default_text="")
        mock = MockASRComponent(config=config)

        result = mock.transcribe(
            audio_data=b"ignored",
            stream_id="test",
            sequence_number=0,
            start_time_ms=0,
            end_time_ms=1000,
        )

        assert len(result.segments) == 0
        assert result.status == TranscriptStatus.SUCCESS

    def test_mock_config_defaults(self):
        """Test MockASRConfig default values."""
        from sts_service.asr.mock import MockASRConfig

        config = MockASRConfig()

        assert config.default_text == "Mock transcription output."
        assert config.default_confidence == 0.95
        assert config.words_per_second == 3.0
        assert config.simulate_latency_ms == 0
        assert config.failure_rate == 0.0
        assert config.failure_type is None
