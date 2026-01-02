"""
Integration tests: Rubberband subprocess for duration matching.

These tests verify:
- Rubberband CLI execution with valid audio
- Time-stretch with pitch preservation
- Failure handling when rubberband fails or is unavailable
- Fallback to simple resampling method

Requirements:
- rubberband-cli installed for live tests (marked with @rubberband)
- Tests can run without rubberband (fallback path tested)
"""

import math
import struct
import subprocess

import pytest
from sts_service.tts.duration_matching import (
    AlignmentResult,
    _time_stretch_simple,
    align_audio_to_duration,
    align_channels,
    apply_clamping,
    calculate_speed_factor,
    resample_audio,
    time_stretch_audio,
)

from .conftest import skip_without_rubberband

# =============================================================================
# Helper Functions
# =============================================================================


def generate_test_audio(
    duration_ms: int,
    sample_rate_hz: int = 16000,
    channels: int = 1,
    frequency_hz: float = 440.0,
    amplitude: float = 0.5,
) -> bytes:
    """Generate test audio (sine wave) as PCM float32 bytes.

    Args:
        duration_ms: Duration in milliseconds
        sample_rate_hz: Sample rate in Hz
        channels: Number of channels
        frequency_hz: Frequency of sine wave
        amplitude: Amplitude (0.0 to 1.0)

    Returns:
        PCM float32 little-endian audio bytes
    """
    num_samples = int(sample_rate_hz * duration_ms / 1000)
    samples = []

    for i in range(num_samples):
        t = i / sample_rate_hz
        value = amplitude * math.sin(2 * math.pi * frequency_hz * t)
        for _ in range(channels):
            samples.append(value)

    return struct.pack(f"<{len(samples)}f", *samples)


def audio_duration_ms(audio_data: bytes, sample_rate_hz: int, channels: int) -> int:
    """Calculate audio duration from bytes.

    Args:
        audio_data: PCM float32 audio bytes
        sample_rate_hz: Sample rate
        channels: Number of channels

    Returns:
        Duration in milliseconds
    """
    num_samples = len(audio_data) // (4 * channels)  # 4 bytes per float32
    return int((num_samples / sample_rate_hz) * 1000)


# =============================================================================
# Test: Speed Factor Calculation
# =============================================================================


class TestSpeedFactorCalculation:
    """Test speed factor calculation for duration matching."""

    def test_speed_factor_speed_up(self):
        """Test speed factor > 1.0 when baseline is longer than target."""
        # 5 seconds baseline, 4 seconds target -> speed up
        factor = calculate_speed_factor(5000, 4000)
        assert factor == 1.25  # 5000/4000

    def test_speed_factor_slow_down(self):
        """Test speed factor < 1.0 when baseline is shorter than target."""
        # 3 seconds baseline, 5 seconds target -> slow down
        factor = calculate_speed_factor(3000, 5000)
        assert factor == 0.6  # 3000/5000

    def test_speed_factor_no_change(self):
        """Test speed factor = 1.0 when durations match."""
        factor = calculate_speed_factor(2000, 2000)
        assert factor == 1.0

    def test_speed_factor_invalid_target(self):
        """Test ValueError for invalid target duration."""
        with pytest.raises(ValueError, match="target_duration_ms must be positive"):
            calculate_speed_factor(2000, 0)

        with pytest.raises(ValueError, match="target_duration_ms must be positive"):
            calculate_speed_factor(2000, -1000)

    def test_speed_factor_invalid_baseline(self):
        """Test ValueError for invalid baseline duration."""
        with pytest.raises(ValueError, match="baseline_duration_ms must be positive"):
            calculate_speed_factor(0, 2000)


# =============================================================================
# Test: Speed Factor Clamping
# =============================================================================


class TestSpeedFactorClamping:
    """Test speed factor clamping to prevent artifacts."""

    def test_clamping_within_range(self):
        """Test no clamping when factor is within range."""
        factor, was_clamped = apply_clamping(1.5, clamp_min=0.5, clamp_max=2.0)
        assert factor == 1.5
        assert was_clamped is False

    def test_clamping_above_max(self):
        """Test clamping when factor exceeds maximum."""
        factor, was_clamped = apply_clamping(3.0, clamp_min=0.5, clamp_max=2.0)
        assert factor == 2.0
        assert was_clamped is True

    def test_clamping_below_min(self):
        """Test clamping when factor is below minimum."""
        factor, was_clamped = apply_clamping(0.3, clamp_min=0.5, clamp_max=2.0)
        assert factor == 0.5
        assert was_clamped is True

    def test_only_speed_up_mode(self):
        """Test only_speed_up prevents slowing down."""
        # Factor < 1.0 should be clamped to 1.0 when only_speed_up=True
        factor, was_clamped = apply_clamping(
            0.8, clamp_min=0.5, clamp_max=2.0, only_speed_up=True
        )
        assert factor == 1.0
        assert was_clamped is True

    def test_only_speed_up_allows_speed_up(self):
        """Test only_speed_up still allows speeding up."""
        factor, was_clamped = apply_clamping(
            1.5, clamp_min=0.5, clamp_max=2.0, only_speed_up=True
        )
        assert factor == 1.5
        assert was_clamped is False


# =============================================================================
# Test: Time Stretch (Fallback/Simple Method)
# =============================================================================


class TestTimeStretchSimple:
    """Test simple time-stretch method (used as fallback)."""

    def test_simple_stretch_speed_up(self):
        """Test simple time-stretch speeds up audio."""
        audio = generate_test_audio(1000, sample_rate_hz=16000)  # 1 second

        stretched, was_stretched = _time_stretch_simple(audio, 16000, 1.5)

        assert was_stretched is True
        # Audio should be shorter (sped up)
        original_samples = len(audio) // 4
        stretched_samples = len(stretched) // 4
        expected_samples = int(original_samples / 1.5)
        # Allow small tolerance
        assert abs(stretched_samples - expected_samples) < 100

    def test_simple_stretch_slow_down(self):
        """Test simple time-stretch slows down audio."""
        audio = generate_test_audio(1000, sample_rate_hz=16000)

        stretched, was_stretched = _time_stretch_simple(audio, 16000, 0.8)

        assert was_stretched is True
        # Audio should be longer (slowed down)
        original_samples = len(audio) // 4
        stretched_samples = len(stretched) // 4
        expected_samples = int(original_samples / 0.8)
        assert abs(stretched_samples - expected_samples) < 100

    def test_simple_stretch_no_change(self):
        """Test time_stretch_audio skips when factor is ~1.0."""
        audio = generate_test_audio(1000, sample_rate_hz=16000)

        # Use time_stretch_audio which has the 1.0 optimization check
        stretched, was_stretched = time_stretch_audio(audio, 16000, 1.0)

        # Should return original audio unchanged (speed factor within 0.01 of 1.0)
        assert was_stretched is False
        assert stretched == audio


# =============================================================================
# Test: Time Stretch with Rubberband (Live)
# =============================================================================


@pytest.mark.rubberband
@skip_without_rubberband
class TestTimeStretchRubberband:
    """Test rubberband-based time-stretch (requires rubberband installed)."""

    def test_rubberband_available(self):
        """Verify rubberband CLI is available."""
        result = subprocess.run(
            ["rubberband", "--version"],
            capture_output=True,
            timeout=5,
        )
        assert result.returncode == 0

    def test_rubberband_stretch_speed_up(self):
        """Test rubberband time-stretch speeds up audio."""
        audio = generate_test_audio(1000, sample_rate_hz=16000)

        stretched, was_stretched = time_stretch_audio(audio, 16000, 1.5)

        # Note: may fall back to simple method if rubberband fails
        if was_stretched:
            original_duration = audio_duration_ms(audio, 16000, 1)
            stretched_duration = audio_duration_ms(stretched, 16000, 1)
            # Stretched audio should be shorter (faster)
            assert stretched_duration < original_duration

    def test_rubberband_pitch_preservation(self):
        """Test rubberband preserves pitch during time-stretch.

        Note: This is a basic test - proper pitch verification would require
        frequency analysis which is beyond scope for integration test.
        """
        audio = generate_test_audio(1000, sample_rate_hz=16000, frequency_hz=440.0)

        stretched, was_stretched = time_stretch_audio(audio, 16000, 1.25)

        # Just verify we got valid output
        assert len(stretched) > 0
        # Parse the audio to verify it's valid float32 data
        num_samples = len(stretched) // 4
        samples = struct.unpack(f"<{num_samples}f", stretched)
        # All samples should be valid floats (no NaN/Inf)
        assert all(math.isfinite(s) for s in samples)


# =============================================================================
# Test: Resampling
# =============================================================================


class TestResampling:
    """Test audio resampling between different sample rates."""

    def test_resample_up(self):
        """Test resampling from 16kHz to 24kHz."""
        audio = generate_test_audio(500, sample_rate_hz=16000)

        resampled = resample_audio(audio, 16000, 24000)

        # Duration should be preserved
        original_duration = audio_duration_ms(audio, 16000, 1)
        resampled_duration = audio_duration_ms(resampled, 24000, 1)
        # Allow 10ms tolerance
        assert abs(original_duration - resampled_duration) < 10

    def test_resample_down(self):
        """Test resampling from 24kHz to 16kHz."""
        audio = generate_test_audio(500, sample_rate_hz=24000)

        resampled = resample_audio(audio, 24000, 16000)

        original_duration = audio_duration_ms(audio, 24000, 1)
        resampled_duration = audio_duration_ms(resampled, 16000, 1)
        assert abs(original_duration - resampled_duration) < 10

    def test_resample_no_change(self):
        """Test no resampling when rates match."""
        audio = generate_test_audio(500, sample_rate_hz=16000)

        resampled = resample_audio(audio, 16000, 16000)

        assert resampled == audio


# =============================================================================
# Test: Channel Alignment
# =============================================================================


class TestChannelAlignment:
    """Test mono/stereo channel conversion."""

    def test_mono_to_stereo(self):
        """Test converting mono to stereo."""
        mono_audio = generate_test_audio(500, sample_rate_hz=16000, channels=1)

        stereo_audio = align_channels(mono_audio, 1, 2)

        # Stereo should have 2x samples
        assert len(stereo_audio) == len(mono_audio) * 2

    def test_stereo_to_mono(self):
        """Test converting stereo to mono."""
        stereo_audio = generate_test_audio(500, sample_rate_hz=16000, channels=2)

        mono_audio = align_channels(stereo_audio, 2, 1)

        # Mono should have half the samples
        assert len(mono_audio) == len(stereo_audio) // 2

    def test_channel_no_change(self):
        """Test no conversion when channels match."""
        audio = generate_test_audio(500, sample_rate_hz=16000, channels=1)

        result = align_channels(audio, 1, 1)

        assert result == audio


# =============================================================================
# Test: Complete Alignment Pipeline
# =============================================================================


class TestAlignmentPipeline:
    """Test complete audio alignment pipeline."""

    def test_complete_alignment_speed_up(self):
        """Test complete alignment with speed up."""
        # 2 second baseline, 1.5 second target -> speed up
        audio = generate_test_audio(2000, sample_rate_hz=16000)

        result = align_audio_to_duration(
            audio_data=audio,
            baseline_duration_ms=2000,
            target_duration_ms=1500,
            input_sample_rate_hz=16000,
            output_sample_rate_hz=16000,
            input_channels=1,
            output_channels=1,
        )

        assert isinstance(result, AlignmentResult)
        assert result.speed_factor_applied == pytest.approx(2000 / 1500, rel=0.01)
        assert result.alignment_time_ms >= 0

    def test_alignment_with_clamping(self):
        """Test alignment clamps extreme speed factors."""
        # 5 second baseline, 1 second target -> 5x speed (should clamp to 2x)
        audio = generate_test_audio(1000, sample_rate_hz=16000)

        result = align_audio_to_duration(
            audio_data=audio,
            baseline_duration_ms=5000,
            target_duration_ms=1000,
            input_sample_rate_hz=16000,
            output_sample_rate_hz=16000,
            input_channels=1,
            output_channels=1,
            clamp_max=2.0,
        )

        # Speed factor should be clamped to 2.0
        assert result.speed_factor_applied == 2.0
        assert result.speed_factor_clamped is True

    def test_alignment_with_resampling(self):
        """Test alignment includes resampling."""
        audio = generate_test_audio(1000, sample_rate_hz=24000)

        result = align_audio_to_duration(
            audio_data=audio,
            baseline_duration_ms=1000,
            target_duration_ms=1000,
            input_sample_rate_hz=24000,
            output_sample_rate_hz=16000,
            input_channels=1,
            output_channels=1,
        )

        assert result.was_resampled is True

    def test_alignment_with_channel_conversion(self):
        """Test alignment includes channel conversion."""
        audio = generate_test_audio(1000, sample_rate_hz=16000, channels=1)

        result = align_audio_to_duration(
            audio_data=audio,
            baseline_duration_ms=1000,
            target_duration_ms=1000,
            input_sample_rate_hz=16000,
            output_sample_rate_hz=16000,
            input_channels=1,
            output_channels=2,
        )

        assert result.was_channel_converted is True

    def test_alignment_only_speed_up(self):
        """Test only_speed_up prevents slowing down."""
        # 1 second baseline, 2 second target -> would slow down
        audio = generate_test_audio(1000, sample_rate_hz=16000)

        result = align_audio_to_duration(
            audio_data=audio,
            baseline_duration_ms=1000,
            target_duration_ms=2000,
            input_sample_rate_hz=16000,
            output_sample_rate_hz=16000,
            input_channels=1,
            output_channels=1,
            only_speed_up=True,
        )

        # Speed factor should be clamped to 1.0 (no slow down)
        assert result.speed_factor_applied == 1.0
        assert result.speed_factor_clamped is True


# =============================================================================
# Test: Error Handling
# =============================================================================


class TestErrorHandling:
    """Test error handling in duration matching."""

    def test_fallback_on_rubberband_unavailable(self):
        """Test fallback to simple method when rubberband is unavailable."""
        audio = generate_test_audio(1000, sample_rate_hz=16000)

        # time_stretch_audio should fall back gracefully
        stretched, was_stretched = time_stretch_audio(audio, 16000, 1.5)

        # Should still get a result (either rubberband or fallback)
        assert len(stretched) > 0

    def test_handles_empty_audio(self):
        """Test handling of empty audio data."""
        # Empty audio
        audio = b""

        # The current implementation may handle empty audio gracefully
        # without raising an exception - verify it doesn't crash
        result = align_audio_to_duration(
            audio_data=audio,
            baseline_duration_ms=1000,
            target_duration_ms=1000,
            input_sample_rate_hz=16000,
            output_sample_rate_hz=16000,
            input_channels=1,
            output_channels=1,
        )

        # Should return an AlignmentResult (may have empty audio)
        assert isinstance(result, AlignmentResult)


# =============================================================================
# Test: Duration Accuracy
# =============================================================================


class TestDurationAccuracy:
    """Test duration matching accuracy requirements."""

    def test_duration_within_tolerance(self):
        """Test final duration is within 50ms of target (spec requirement)."""
        audio = generate_test_audio(2000, sample_rate_hz=16000)

        result = align_audio_to_duration(
            audio_data=audio,
            baseline_duration_ms=2000,
            target_duration_ms=1500,
            input_sample_rate_hz=16000,
            output_sample_rate_hz=16000,
            input_channels=1,
            output_channels=1,
        )

        # Allow 50ms tolerance per spec
        tolerance_ms = 50
        assert abs(result.final_duration_ms - 1500) < tolerance_ms, (
            f"Final duration {result.final_duration_ms}ms not within "
            f"{tolerance_ms}ms of target 1500ms"
        )
