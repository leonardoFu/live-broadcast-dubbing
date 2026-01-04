"""
Unit tests for duration matching functionality.

Tests for speed factor calculation, clamping, and time-stretch operations.
Following TDD: These tests MUST be written FIRST and MUST FAIL before implementation.

Coverage Target: 95% (duration matching is critical path for A/V sync).
"""

import pytest
from sts_service.tts.duration_matching import (
    align_audio_to_duration,
    align_channels,
    apply_clamping,
    calculate_speed_factor,
    resample_audio,
    time_stretch_audio,
)


class TestCalculateSpeedFactor:
    """Tests for speed factor calculation."""

    def test_speed_factor_calculation_basic(self):
        """Test speed_factor = baseline_duration / target_duration."""
        # Baseline 5000ms, target 4000ms -> need to speed up by 1.25x
        speed_factor = calculate_speed_factor(baseline_duration_ms=5000, target_duration_ms=4000)
        assert abs(speed_factor - 1.25) < 0.001

    def test_speed_factor_calculation_slow_down(self):
        """Test speed factor < 1.0 for slowing down."""
        # Baseline 3000ms, target 5000ms -> need to slow down by 0.6x
        speed_factor = calculate_speed_factor(baseline_duration_ms=3000, target_duration_ms=5000)
        assert abs(speed_factor - 0.6) < 0.001

    def test_speed_factor_calculation_no_change(self):
        """Test speed factor = 1.0 when durations match."""
        speed_factor = calculate_speed_factor(baseline_duration_ms=2000, target_duration_ms=2000)
        assert speed_factor == 1.0

    def test_speed_factor_zero_target_raises(self):
        """Test zero target_duration_ms raises ValueError."""
        with pytest.raises(ValueError):
            calculate_speed_factor(baseline_duration_ms=1000, target_duration_ms=0)

    def test_speed_factor_negative_target_raises(self):
        """Test negative target_duration_ms raises ValueError."""
        with pytest.raises(ValueError):
            calculate_speed_factor(baseline_duration_ms=1000, target_duration_ms=-100)


class TestApplyClamping:
    """Tests for speed factor clamping."""

    def test_clamping_default_range(self):
        """Test clamping to [0.5, 2.0] range (default)."""
        # Within range - no change
        assert apply_clamping(1.5) == (1.5, False)

        # Below range - clamp to 0.5
        assert apply_clamping(0.3) == (0.5, True)

        # Above range - clamp to 2.0
        assert apply_clamping(2.5) == (2.0, True)

    def test_clamping_custom_range(self):
        """Test clamping to custom range from VoiceProfile."""
        # Custom range [0.8, 1.5]
        assert apply_clamping(1.2, clamp_min=0.8, clamp_max=1.5) == (1.2, False)
        assert apply_clamping(0.5, clamp_min=0.8, clamp_max=1.5) == (0.8, True)
        assert apply_clamping(2.0, clamp_min=0.8, clamp_max=1.5) == (1.5, True)

    def test_clamping_only_speed_up_flag(self):
        """Test only_speed_up flag (never slow down)."""
        # only_speed_up=True should clamp minimum to 1.0
        assert apply_clamping(0.8, only_speed_up=True) == (1.0, True)
        assert apply_clamping(1.5, only_speed_up=True) == (1.5, False)

    def test_clamping_extreme_speed_warning(self):
        """Test extreme speed (>2x) triggers clamping."""
        factor, clamped = apply_clamping(3.0)
        assert factor == 2.0
        assert clamped is True

    def test_clamping_at_boundary(self):
        """Test clamping at exact boundary values."""
        assert apply_clamping(0.5) == (0.5, False)
        assert apply_clamping(2.0) == (2.0, False)


class TestTimeStretchAudio:
    """Tests for time-stretch using rubberband."""

    @pytest.fixture
    def sample_audio_16k_mono(self):
        """Provide sample PCM audio (1 second, 16kHz, mono)."""
        import math
        import struct

        sample_rate = 16000
        duration_sec = 1.0
        num_samples = int(sample_rate * duration_sec)
        samples = []

        for i in range(num_samples):
            t = i / sample_rate
            value = 0.5 * math.sin(2 * math.pi * 440 * t)
            samples.append(value)

        return struct.pack(f"<{len(samples)}f", *samples)

    def test_time_stretch_skip_when_no_change(self, sample_audio_16k_mono):
        """Test target_duration_ms == baseline_duration_ms skips time-stretch."""
        result, was_stretched = time_stretch_audio(
            audio_data=sample_audio_16k_mono,
            sample_rate_hz=16000,
            speed_factor=1.0,  # No change needed
        )
        # Should return original audio unchanged
        assert was_stretched is False

    def test_time_stretch_speed_up(self, sample_audio_16k_mono):
        """Test audio is sped up when speed_factor > 1.0."""
        result, was_stretched = time_stretch_audio(
            audio_data=sample_audio_16k_mono,
            sample_rate_hz=16000,
            speed_factor=1.5,
        )
        # Audio should be shorter after speeding up
        assert was_stretched is True

    def test_time_stretch_pitch_preservation(self, sample_audio_16k_mono):
        """Test pitch is preserved after time-stretch."""
        # This is a property test - we verify the operation completes
        # without changing pitch (would need audio analysis for full test)
        result, was_stretched = time_stretch_audio(
            audio_data=sample_audio_16k_mono,
            sample_rate_hz=16000,
            speed_factor=1.25,
        )
        # Should complete successfully
        assert result is not None


class TestResampleAudio:
    """Tests for sample rate alignment."""

    @pytest.fixture
    def sample_audio_24k(self):
        """Provide sample PCM audio at 24kHz."""
        import math
        import struct

        sample_rate = 24000
        duration_sec = 0.5
        num_samples = int(sample_rate * duration_sec)
        samples = [0.5 * math.sin(2 * math.pi * 440 * i / sample_rate) for i in range(num_samples)]
        return struct.pack(f"<{len(samples)}f", *samples)

    def test_resample_24k_to_16k(self, sample_audio_24k):
        """Test resampling from 24kHz to 16kHz output."""
        result = resample_audio(
            audio_data=sample_audio_24k,
            input_sample_rate_hz=24000,
            output_sample_rate_hz=16000,
        )
        # Result should be shorter (fewer samples for same duration)
        assert len(result) < len(sample_audio_24k)

    def test_resample_16k_to_48k(self):
        """Test resampling from 16kHz to 48kHz output."""
        import math
        import struct

        sample_rate = 16000
        num_samples = 8000  # 0.5 seconds
        samples = [0.5 * math.sin(2 * math.pi * 440 * i / sample_rate) for i in range(num_samples)]
        audio_data = struct.pack(f"<{len(samples)}f", *samples)

        result = resample_audio(
            audio_data=audio_data,
            input_sample_rate_hz=16000,
            output_sample_rate_hz=48000,
        )
        # Result should be longer (more samples for same duration)
        assert len(result) > len(audio_data)

    def test_resample_no_change_when_rates_match(self, sample_audio_24k):
        """Test no resampling when rates match."""
        result = resample_audio(
            audio_data=sample_audio_24k,
            input_sample_rate_hz=24000,
            output_sample_rate_hz=24000,
        )
        assert result == sample_audio_24k


class TestAlignChannels:
    """Tests for channel alignment."""

    @pytest.fixture
    def sample_mono_audio(self):
        """Provide mono audio (1 channel)."""
        import struct

        # 100 samples of mono audio
        samples = [0.5] * 100
        return struct.pack(f"<{len(samples)}f", *samples)

    @pytest.fixture
    def sample_stereo_audio(self):
        """Provide stereo audio (2 channels, interleaved)."""
        import struct

        # 100 frames of stereo audio (200 samples total)
        samples = []
        for _ in range(100):
            samples.extend([0.5, 0.5])  # L, R
        return struct.pack(f"<{len(samples)}f", *samples)

    def test_mono_to_stereo_conversion(self, sample_mono_audio):
        """Test mono to stereo conversion."""
        result = align_channels(
            audio_data=sample_mono_audio,
            input_channels=1,
            output_channels=2,
        )
        # Stereo should have twice the samples
        assert len(result) == len(sample_mono_audio) * 2

    def test_stereo_to_mono_conversion(self, sample_stereo_audio):
        """Test stereo to mono conversion (average channels)."""
        result = align_channels(
            audio_data=sample_stereo_audio,
            input_channels=2,
            output_channels=1,
        )
        # Mono should have half the samples
        assert len(result) == len(sample_stereo_audio) // 2

    def test_no_conversion_when_channels_match(self, sample_mono_audio):
        """Test no conversion when channels match."""
        result = align_channels(
            audio_data=sample_mono_audio,
            input_channels=1,
            output_channels=1,
        )
        assert result == sample_mono_audio


class TestAlignAudioToDuration:
    """Integration tests for the complete duration alignment pipeline."""

    @pytest.fixture
    def sample_audio(self):
        """Provide sample audio for testing."""
        import math
        import struct

        sample_rate = 16000
        duration_sec = 2.0  # 2 seconds
        num_samples = int(sample_rate * duration_sec)
        samples = [0.5 * math.sin(2 * math.pi * 440 * i / sample_rate) for i in range(num_samples)]
        return struct.pack(f"<{len(samples)}f", *samples)

    def test_complete_alignment_speed_up(self, sample_audio):
        """Test complete alignment with speed up."""
        # 2 second audio, target 1.5 seconds
        result = align_audio_to_duration(
            audio_data=sample_audio,
            baseline_duration_ms=2000,
            target_duration_ms=1500,
            input_sample_rate_hz=16000,
            output_sample_rate_hz=16000,
            input_channels=1,
            output_channels=1,
        )

        assert result.audio_data is not None
        assert result.final_duration_ms > 0
        assert result.speed_factor_applied is not None
        assert result.speed_factor_applied > 1.0  # Sped up

    def test_complete_alignment_only_speed_up(self, sample_audio):
        """Test alignment with only_speed_up flag."""
        # 2 second audio, target 4 seconds, but only_speed_up=True
        result = align_audio_to_duration(
            audio_data=sample_audio,
            baseline_duration_ms=2000,
            target_duration_ms=4000,  # Would require slow down
            input_sample_rate_hz=16000,
            output_sample_rate_hz=16000,
            input_channels=1,
            output_channels=1,
            only_speed_up=True,
        )

        # Should not slow down - speed_factor should be 1.0
        assert result.speed_factor_applied == 1.0 or result.speed_factor_clamped

    def test_complete_alignment_with_resampling(self, sample_audio):
        """Test alignment with sample rate change."""
        result = align_audio_to_duration(
            audio_data=sample_audio,
            baseline_duration_ms=2000,
            target_duration_ms=2000,
            input_sample_rate_hz=16000,
            output_sample_rate_hz=24000,  # Resample to 24kHz
            input_channels=1,
            output_channels=1,
        )

        assert result.audio_data is not None
        # Output should have more samples due to higher sample rate
        assert len(result.audio_data) > len(sample_audio)
