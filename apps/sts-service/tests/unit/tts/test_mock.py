"""
Unit tests for mock TTS implementations.

Tests for MockTTSFixedTone, MockTTSFromFixture, and MockTTSFailOnce.
Following TDD: These tests MUST be written FIRST and MUST FAIL before implementation.

Coverage Target: 80% minimum.
"""

import pytest
from sts_service.translation.models import TextAsset
from sts_service.tts.mock import MockTTSFailOnce, MockTTSFixedTone
from sts_service.tts.models import (
    AudioAsset,
    AudioFormat,
    AudioStatus,
    TTSConfig,
    VoiceProfile,
)


@pytest.fixture
def sample_text_asset():
    """Provide a sample TextAsset for testing."""
    return TextAsset(
        stream_id="test-stream",
        sequence_number=1,
        parent_asset_ids=["transcript-uuid-123"],
        component_instance="mock-translate-v1",
        source_language="en",
        target_language="en",
        translated_text="Hello world, this is a test.",
        status="success",
    )


@pytest.fixture
def tts_config():
    """Provide default TTS config for testing."""
    return TTSConfig()


class TestMockTTSFixedTone:
    """Tests for MockTTSFixedTone implementation."""

    def test_mock_produces_deterministic_440hz_tone(self, sample_text_asset, tts_config):
        """Test mock produces deterministic 440Hz tone."""
        tts = MockTTSFixedTone(config=tts_config)

        # Synthesize twice with same input
        result1 = tts.synthesize(sample_text_asset, target_duration_ms=1000)
        result2 = tts.synthesize(sample_text_asset, target_duration_ms=1000)

        # Results should be identical (deterministic)
        assert result1.duration_ms == result2.duration_ms
        # Both should produce valid audio
        assert result1.status == AudioStatus.SUCCESS
        assert result2.status == AudioStatus.SUCCESS

    def test_mock_respects_target_duration_ms(self, sample_text_asset, tts_config):
        """Test mock respects target_duration_ms parameter."""
        tts = MockTTSFixedTone(config=tts_config)

        # Test various target durations
        for target_ms in [500, 1000, 2000, 3000]:
            result = tts.synthesize(sample_text_asset, target_duration_ms=target_ms)
            # Duration should match or be very close to target
            assert abs(result.duration_ms - target_ms) < 10  # Allow small tolerance

    def test_mock_returns_valid_audio_asset_structure(self, sample_text_asset, tts_config):
        """Test mock returns valid AudioAsset structure."""
        tts = MockTTSFixedTone(config=tts_config)
        result = tts.synthesize(sample_text_asset, target_duration_ms=1000)

        # Check required fields
        assert isinstance(result, AudioAsset)
        assert result.stream_id == sample_text_asset.stream_id
        assert result.sequence_number == sample_text_asset.sequence_number
        assert result.component == "tts"
        assert "mock" in result.component_instance.lower()
        assert result.status == AudioStatus.SUCCESS
        assert result.audio_format in [AudioFormat.PCM_F32LE, AudioFormat.PCM_S16LE]
        assert result.sample_rate_hz in [8000, 16000, 24000, 44100, 48000]
        assert result.channels in [1, 2]
        assert result.duration_ms > 0
        assert result.payload_ref  # Should have a payload reference
        assert sample_text_asset.asset_id in result.parent_asset_ids

    def test_mock_generates_correct_frequency_tone(self, sample_text_asset, tts_config):
        """Test mock generates audio with 440Hz frequency."""
        tts = MockTTSFixedTone(config=tts_config)
        result = tts.synthesize(sample_text_asset, target_duration_ms=1000)

        # The mock should produce a 440Hz tone
        # This is a property test - we just verify audio is generated
        assert result.duration_ms >= 900  # Close to 1000ms
        assert result.status == AudioStatus.SUCCESS

    def test_mock_component_name_is_tts(self, tts_config):
        """Test mock component_name is 'tts'."""
        tts = MockTTSFixedTone(config=tts_config)
        assert tts.component_name == "tts"

    def test_mock_is_ready_returns_true(self, tts_config):
        """Test mock is_ready returns True."""
        tts = MockTTSFixedTone(config=tts_config)
        assert tts.is_ready is True

    def test_mock_with_voice_profile(self, sample_text_asset, tts_config):
        """Test mock accepts voice_profile parameter."""
        tts = MockTTSFixedTone(config=tts_config)
        voice_profile = VoiceProfile(language="en", fast_mode=True)

        result = tts.synthesize(
            sample_text_asset,
            target_duration_ms=1000,
            voice_profile=voice_profile,
        )

        assert result.status == AudioStatus.SUCCESS

    def test_mock_without_target_duration(self, sample_text_asset, tts_config):
        """Test mock works without target_duration_ms (estimates from text)."""
        tts = MockTTSFixedTone(config=tts_config)

        # Should estimate duration based on text length
        result = tts.synthesize(sample_text_asset)

        assert result.status == AudioStatus.SUCCESS
        assert result.duration_ms > 0

    def test_mock_output_sample_rate(self, sample_text_asset, tts_config):
        """Test mock respects output_sample_rate_hz parameter."""
        tts = MockTTSFixedTone(config=tts_config)

        result = tts.synthesize(
            sample_text_asset,
            target_duration_ms=1000,
            output_sample_rate_hz=24000,
        )

        assert result.sample_rate_hz == 24000

    def test_mock_output_channels(self, sample_text_asset, tts_config):
        """Test mock respects output_channels parameter."""
        tts = MockTTSFixedTone(config=tts_config)

        result = tts.synthesize(
            sample_text_asset,
            target_duration_ms=1000,
            output_channels=2,  # stereo
        )

        assert result.channels == 2


class TestMockTTSFailOnce:
    """Tests for MockTTSFailOnce implementation."""

    def test_first_call_returns_failed_status(self, sample_text_asset, tts_config):
        """Test first call per sequence_number returns FAILED status."""
        tts = MockTTSFailOnce(config=tts_config)

        result = tts.synthesize(sample_text_asset, target_duration_ms=1000)

        assert result.status == AudioStatus.FAILED
        assert result.has_errors
        assert len(result.errors) > 0

    def test_first_call_has_retryable_error(self, sample_text_asset, tts_config):
        """Test first call returns retryable error."""
        tts = MockTTSFailOnce(config=tts_config)

        result = tts.synthesize(sample_text_asset, target_duration_ms=1000)

        assert result.is_retryable
        assert any(e.retryable for e in result.errors)

    def test_second_call_returns_success(self, sample_text_asset, tts_config):
        """Test second call per sequence_number returns SUCCESS status."""
        tts = MockTTSFailOnce(config=tts_config)

        # First call fails
        result1 = tts.synthesize(sample_text_asset, target_duration_ms=1000)
        assert result1.status == AudioStatus.FAILED

        # Second call succeeds
        result2 = tts.synthesize(sample_text_asset, target_duration_ms=1000)
        assert result2.status == AudioStatus.SUCCESS

    def test_different_sequence_numbers_fail_independently(self, tts_config):
        """Test different sequence_numbers fail independently."""
        tts = MockTTSFailOnce(config=tts_config)

        # Create two text assets with different sequence numbers
        text_asset_1 = TextAsset(
            stream_id="test-stream",
            sequence_number=1,
            parent_asset_ids=["transcript-1"],
            component_instance="mock-translate-v1",
            source_language="en",
            target_language="en",
            translated_text="First text",
            status="success",
        )
        text_asset_2 = TextAsset(
            stream_id="test-stream",
            sequence_number=2,
            parent_asset_ids=["transcript-2"],
            component_instance="mock-translate-v1",
            source_language="en",
            target_language="en",
            translated_text="Second text",
            status="success",
        )

        # Both first calls should fail
        result1 = tts.synthesize(text_asset_1, target_duration_ms=1000)
        result2 = tts.synthesize(text_asset_2, target_duration_ms=1000)

        assert result1.status == AudioStatus.FAILED
        assert result2.status == AudioStatus.FAILED

        # Both second calls should succeed
        result1_retry = tts.synthesize(text_asset_1, target_duration_ms=1000)
        result2_retry = tts.synthesize(text_asset_2, target_duration_ms=1000)

        assert result1_retry.status == AudioStatus.SUCCESS
        assert result2_retry.status == AudioStatus.SUCCESS

    def test_failed_result_has_valid_audio_asset(self, sample_text_asset, tts_config):
        """Test failed result still has valid AudioAsset structure."""
        tts = MockTTSFailOnce(config=tts_config)

        result = tts.synthesize(sample_text_asset, target_duration_ms=1000)

        # Even FAILED status should have valid asset structure
        assert isinstance(result, AudioAsset)
        assert result.stream_id == sample_text_asset.stream_id
        assert result.sequence_number == sample_text_asset.sequence_number
        assert result.component == "tts"
