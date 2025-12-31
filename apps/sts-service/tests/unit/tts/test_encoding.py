"""
Unit tests for TTS Audio Encoding Module.

Tests PCM to M4A/AAC encoding functionality.
"""

import math
import struct
import subprocess
from unittest.mock import MagicMock, patch

import pytest

from sts_service.tts.encoding import (
    EncodingError,
    EncodingResult,
    _check_ffmpeg_available,
    encode_pcm_to_m4a,
    encode_pcm_to_m4a_with_metadata,
    get_m4a_duration_ms,
)
from sts_service.tts.models import AudioFormat


def generate_sine_wave_pcm(
    duration_ms: int,
    sample_rate_hz: int = 16000,
    channels: int = 1,
    frequency_hz: float = 440.0,
    amplitude: float = 0.5,
    format: AudioFormat = AudioFormat.PCM_F32LE,
) -> bytes:
    """Generate a sine wave PCM audio buffer for testing."""
    num_samples = int(sample_rate_hz * duration_ms / 1000)
    samples = []

    for i in range(num_samples):
        t = i / sample_rate_hz
        value = amplitude * math.sin(2 * math.pi * frequency_hz * t)
        for _ in range(channels):
            samples.append(value)

    if format == AudioFormat.PCM_F32LE:
        return struct.pack(f"<{len(samples)}f", *samples)
    elif format == AudioFormat.PCM_S16LE:
        int16_samples = [int(s * 32767) for s in samples]
        return struct.pack(f"<{len(int16_samples)}h", *int16_samples)
    else:
        raise ValueError(f"Unsupported format: {format}")


class TestCheckFfmpegAvailable:
    """Tests for ffmpeg availability check."""

    def test_ffmpeg_available_returns_true_when_installed(self):
        """Test that check returns True when ffmpeg is installed."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            assert _check_ffmpeg_available() is True

    def test_ffmpeg_not_found_returns_false(self):
        """Test that check returns False when ffmpeg not installed."""
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = FileNotFoundError()
            assert _check_ffmpeg_available() is False

    def test_ffmpeg_timeout_returns_false(self):
        """Test that check returns False on timeout."""
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.TimeoutExpired(cmd="ffmpeg", timeout=5)
            assert _check_ffmpeg_available() is False


class TestEncodePcmToM4a:
    """Tests for PCM to M4A encoding."""

    def test_encode_empty_data_raises_error(self):
        """Test that empty PCM data raises EncodingError."""
        with pytest.raises(EncodingError) as exc_info:
            encode_pcm_to_m4a(
                pcm_data=b"",
                sample_rate_hz=16000,
                channels=1,
            )
        assert "Empty PCM data" in str(exc_info.value)

    def test_encode_invalid_sample_rate_raises_error(self):
        """Test that invalid sample rate raises EncodingError."""
        pcm_data = generate_sine_wave_pcm(100)
        with pytest.raises(EncodingError) as exc_info:
            encode_pcm_to_m4a(
                pcm_data=pcm_data,
                sample_rate_hz=0,
                channels=1,
            )
        assert "Invalid sample rate" in str(exc_info.value)

    def test_encode_invalid_channels_raises_error(self):
        """Test that invalid channel count raises EncodingError."""
        pcm_data = generate_sine_wave_pcm(100)
        with pytest.raises(EncodingError) as exc_info:
            encode_pcm_to_m4a(
                pcm_data=pcm_data,
                sample_rate_hz=16000,
                channels=5,
            )
        assert "Invalid channel count" in str(exc_info.value)

    def test_encode_unsupported_format_raises_error(self):
        """Test that unsupported input format raises EncodingError."""
        pcm_data = generate_sine_wave_pcm(100)
        with pytest.raises(EncodingError) as exc_info:
            encode_pcm_to_m4a(
                pcm_data=pcm_data,
                sample_rate_hz=16000,
                channels=1,
                input_format=AudioFormat.M4A_AAC,  # Invalid input format
            )
        assert "Unsupported input format" in str(exc_info.value)

    def test_encode_ffmpeg_not_available_raises_error(self):
        """Test that missing ffmpeg raises EncodingError with hint."""
        pcm_data = generate_sine_wave_pcm(100)
        with patch(
            "sts_service.tts.encoding._check_ffmpeg_available", return_value=False
        ):
            with pytest.raises(EncodingError) as exc_info:
                encode_pcm_to_m4a(
                    pcm_data=pcm_data,
                    sample_rate_hz=16000,
                    channels=1,
                )
            assert "ffmpeg not available" in str(exc_info.value)
            assert "hint" in exc_info.value.details

    @pytest.mark.skipif(
        not _check_ffmpeg_available(),
        reason="ffmpeg not installed",
    )
    def test_encode_mono_f32le_success(self):
        """Test encoding mono PCM_F32LE audio to M4A."""
        pcm_data = generate_sine_wave_pcm(
            duration_ms=500,
            sample_rate_hz=16000,
            channels=1,
            format=AudioFormat.PCM_F32LE,
        )

        result = encode_pcm_to_m4a(
            pcm_data=pcm_data,
            sample_rate_hz=16000,
            channels=1,
            input_format=AudioFormat.PCM_F32LE,
            bitrate_kbps=64,
        )

        # Verify output is valid M4A (starts with ftyp box)
        assert len(result) > 0
        # M4A files typically have 'ftyp' marker within first 12 bytes
        assert b"ftyp" in result[:32] or b"moov" in result

    @pytest.mark.skipif(
        not _check_ffmpeg_available(),
        reason="ffmpeg not installed",
    )
    def test_encode_stereo_s16le_success(self):
        """Test encoding stereo PCM_S16LE audio to M4A."""
        pcm_data = generate_sine_wave_pcm(
            duration_ms=500,
            sample_rate_hz=44100,
            channels=2,
            format=AudioFormat.PCM_S16LE,
        )

        result = encode_pcm_to_m4a(
            pcm_data=pcm_data,
            sample_rate_hz=44100,
            channels=2,
            input_format=AudioFormat.PCM_S16LE,
            bitrate_kbps=128,
        )

        assert len(result) > 0

    @pytest.mark.skipif(
        not _check_ffmpeg_available(),
        reason="ffmpeg not installed",
    )
    def test_encode_with_high_bitrate(self):
        """Test encoding with high bitrate produces larger file."""
        pcm_data = generate_sine_wave_pcm(
            duration_ms=1000,
            sample_rate_hz=44100,
            channels=2,
        )

        low_bitrate = encode_pcm_to_m4a(
            pcm_data=pcm_data,
            sample_rate_hz=44100,
            channels=2,
            bitrate_kbps=64,
        )

        high_bitrate = encode_pcm_to_m4a(
            pcm_data=pcm_data,
            sample_rate_hz=44100,
            channels=2,
            bitrate_kbps=256,
        )

        # Higher bitrate should generally produce larger file
        # (for very short audio this may not always hold)
        assert len(high_bitrate) >= len(low_bitrate) * 0.8


class TestEncodePcmToM4aWithMetadata:
    """Tests for encoding with metadata result."""

    @pytest.mark.skipif(
        not _check_ffmpeg_available(),
        reason="ffmpeg not installed",
    )
    def test_returns_encoding_result(self):
        """Test that encoding returns EncodingResult with metadata."""
        pcm_data = generate_sine_wave_pcm(
            duration_ms=500,
            sample_rate_hz=16000,
            channels=1,
        )

        result = encode_pcm_to_m4a_with_metadata(
            pcm_data=pcm_data,
            sample_rate_hz=16000,
            channels=1,
            bitrate_kbps=64,
        )

        assert isinstance(result, EncodingResult)
        assert len(result.audio_data) > 0
        assert result.format == AudioFormat.M4A_AAC
        assert result.duration_ms == 500
        assert result.encoding_time_ms >= 0
        assert result.bitrate_kbps == 64

    @pytest.mark.skipif(
        not _check_ffmpeg_available(),
        reason="ffmpeg not installed",
    )
    def test_duration_calculated_correctly(self):
        """Test that duration is calculated from PCM data."""
        duration_ms = 1500
        pcm_data = generate_sine_wave_pcm(
            duration_ms=duration_ms,
            sample_rate_hz=22050,
            channels=2,
        )

        result = encode_pcm_to_m4a_with_metadata(
            pcm_data=pcm_data,
            sample_rate_hz=22050,
            channels=2,
        )

        assert result.duration_ms == duration_ms


class TestGetM4aDurationMs:
    """Tests for M4A duration detection."""

    @pytest.mark.skipif(
        not _check_ffmpeg_available(),
        reason="ffmpeg not installed",
    )
    def test_get_duration_from_encoded_m4a(self):
        """Test that duration can be extracted from M4A data."""
        pcm_data = generate_sine_wave_pcm(
            duration_ms=1000,
            sample_rate_hz=16000,
            channels=1,
        )

        m4a_data = encode_pcm_to_m4a(
            pcm_data=pcm_data,
            sample_rate_hz=16000,
            channels=1,
        )

        duration = get_m4a_duration_ms(m4a_data)

        # Allow some tolerance due to codec frame alignment
        assert duration is not None
        assert 900 <= duration <= 1100  # 1000ms +/- 100ms tolerance

    def test_get_duration_invalid_data_returns_none(self):
        """Test that invalid M4A data returns None."""
        duration = get_m4a_duration_ms(b"not valid m4a data")
        assert duration is None

    def test_get_duration_empty_data_returns_none(self):
        """Test that empty data returns None."""
        duration = get_m4a_duration_ms(b"")
        assert duration is None


class TestEncodingError:
    """Tests for EncodingError exception."""

    def test_encoding_error_with_message(self):
        """Test EncodingError stores message."""
        error = EncodingError("Test error")
        assert error.message == "Test error"
        assert str(error) == "Test error"
        assert error.details == {}

    def test_encoding_error_with_details(self):
        """Test EncodingError stores details dict."""
        error = EncodingError("Test error", {"key": "value"})
        assert error.message == "Test error"
        assert error.details == {"key": "value"}
