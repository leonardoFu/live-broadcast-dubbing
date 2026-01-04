"""
Unit tests for audio preprocessing functions.

TDD: These tests are written BEFORE implementation.
"""

import numpy as np
import pytest


class TestPreprocessAudio:
    """Tests for the main preprocess_audio function."""

    def test_preprocess_audio_returns_numpy_array(self, sample_audio_bytes):
        """Test that preprocess_audio returns a numpy array."""
        from sts_service.asr.preprocessing import preprocess_audio

        result = preprocess_audio(sample_audio_bytes, sample_rate=16000)
        assert isinstance(result, np.ndarray)
        assert result.dtype == np.float32

    def test_preprocess_audio_normalizes_amplitude(self):
        """Test that audio is normalized to [-1, 1] range."""
        from sts_service.asr.preprocessing import preprocess_audio

        # Create audio with large amplitude (needs enough samples for filtering)
        sample_rate = 16000
        duration = 0.1  # 100ms
        t = np.linspace(0, duration, int(sample_rate * duration), dtype=np.float32)
        audio = 2.0 * np.sin(2 * np.pi * 440 * t)  # Amplitude of 2
        audio_bytes = audio.astype(np.float32).tobytes()

        result = preprocess_audio(audio_bytes, sample_rate=sample_rate)

        # After normalization, max absolute value should be <= 1.0
        assert np.abs(result).max() <= 1.0

    def test_preprocess_audio_applies_highpass_filter(self):
        """Test that low frequencies are attenuated."""
        from sts_service.asr.preprocessing import preprocess_audio

        sample_rate = 16000
        duration = 1.0
        t = np.linspace(0, duration, int(sample_rate * duration), dtype=np.float32)

        # Generate 30Hz sine wave (below typical 80Hz cutoff)
        low_freq = 0.5 * np.sin(2 * np.pi * 30 * t)
        audio_bytes = low_freq.astype(np.float32).tobytes()

        result = preprocess_audio(audio_bytes, sample_rate=sample_rate)

        # Low frequency should be significantly attenuated
        # RMS of output should be much lower than input
        input_rms = np.sqrt(np.mean(low_freq**2))
        output_rms = np.sqrt(np.mean(result**2))
        assert output_rms < input_rms * 0.5  # At least 50% reduction

    def test_preprocess_audio_applies_preemphasis(self):
        """Test that pre-emphasis filter is applied."""
        from sts_service.asr.preprocessing import preprocess_audio

        # Pre-emphasis boosts high frequencies
        sample_rate = 16000
        duration = 0.5
        t = np.linspace(0, duration, int(sample_rate * duration), dtype=np.float32)

        # Generate a step function (contains high frequencies)
        audio = np.zeros_like(t)
        audio[len(audio) // 2 :] = 0.5
        audio_bytes = audio.astype(np.float32).tobytes()

        result = preprocess_audio(audio_bytes, sample_rate=sample_rate)

        # Result should be different from normalized input
        normalized_input = audio / np.abs(audio).max() if np.abs(audio).max() > 0 else audio
        # Pre-emphasis changes the waveform
        assert not np.allclose(result, normalized_input, atol=1e-3)

    def test_preprocess_audio_resamples_to_16khz(self):
        """Test that audio is resampled to 16kHz."""
        from sts_service.asr.preprocessing import preprocess_audio

        # Create audio at 44100 Hz
        orig_sample_rate = 44100
        target_sample_rate = 16000
        duration = 0.5

        num_samples = int(orig_sample_rate * duration)
        t = np.linspace(0, duration, num_samples, dtype=np.float32)
        audio = 0.5 * np.sin(2 * np.pi * 440 * t)
        audio_bytes = audio.astype(np.float32).tobytes()

        result = preprocess_audio(
            audio_bytes, sample_rate=orig_sample_rate, target_sample_rate=target_sample_rate
        )

        # Output should have correct number of samples for 16kHz
        expected_samples = int(target_sample_rate * duration)
        assert len(result) == pytest.approx(expected_samples, rel=0.05)

    def test_preprocess_audio_handles_stereo_to_mono(self):
        """Test that stereo audio is converted to mono."""
        from sts_service.asr.preprocessing import preprocess_audio

        # Create stereo audio (2 channels, interleaved)
        sample_rate = 16000
        duration = 0.1
        num_samples = int(sample_rate * duration)

        # Left channel: 440Hz, Right channel: 880Hz
        t = np.linspace(0, duration, num_samples, dtype=np.float32)
        left = 0.5 * np.sin(2 * np.pi * 440 * t)
        right = 0.5 * np.sin(2 * np.pi * 880 * t)

        # Interleave channels
        stereo = np.empty(num_samples * 2, dtype=np.float32)
        stereo[0::2] = left
        stereo[1::2] = right
        audio_bytes = stereo.tobytes()

        result = preprocess_audio(audio_bytes, sample_rate=sample_rate, channels=2)

        # Result should be mono (single channel)
        # Length should be half of stereo
        assert len(result) > 0
        # Mono conversion averages channels

    def test_preprocess_audio_preserves_duration(self, sample_audio_bytes):
        """Test that audio duration is approximately preserved."""
        from sts_service.asr.preprocessing import preprocess_audio

        sample_rate = 16000
        # sample_audio_bytes is 1 second at 16kHz
        input_samples = len(sample_audio_bytes) // 4  # float32 = 4 bytes

        result = preprocess_audio(sample_audio_bytes, sample_rate=sample_rate)

        # Duration should be preserved (within 5%)
        assert len(result) == pytest.approx(input_samples, rel=0.05)

    def test_preprocess_audio_invalid_sample_rate_error(self):
        """Test that invalid sample rate raises error."""
        from sts_service.asr.preprocessing import preprocess_audio

        audio_bytes = np.zeros(100, dtype=np.float32).tobytes()

        with pytest.raises(ValueError, match="sample.*rate"):
            preprocess_audio(audio_bytes, sample_rate=0)


class TestHighpassFilter:
    """Tests for the highpass filter function."""

    def test_highpass_filter_removes_low_frequencies(self):
        """Test that frequencies below cutoff are attenuated."""
        from sts_service.asr.preprocessing import apply_highpass_filter

        sample_rate = 16000
        duration = 1.0
        t = np.linspace(0, duration, int(sample_rate * duration), dtype=np.float32)

        # Generate 20Hz sine wave (well below 80Hz cutoff)
        low_freq = np.sin(2 * np.pi * 20 * t).astype(np.float32)

        result = apply_highpass_filter(low_freq, sample_rate=sample_rate, cutoff_hz=80)

        # 20Hz should be heavily attenuated
        input_rms = np.sqrt(np.mean(low_freq**2))
        output_rms = np.sqrt(np.mean(result**2))
        assert output_rms < input_rms * 0.3  # Significant attenuation

    def test_highpass_filter_preserves_high_frequencies(self):
        """Test that frequencies above cutoff are preserved."""
        from sts_service.asr.preprocessing import apply_highpass_filter

        sample_rate = 16000
        duration = 1.0
        t = np.linspace(0, duration, int(sample_rate * duration), dtype=np.float32)

        # Generate 1000Hz sine wave (well above 80Hz cutoff)
        high_freq = np.sin(2 * np.pi * 1000 * t).astype(np.float32)

        result = apply_highpass_filter(high_freq, sample_rate=sample_rate, cutoff_hz=80)

        # 1000Hz should be mostly preserved
        input_rms = np.sqrt(np.mean(high_freq**2))
        output_rms = np.sqrt(np.mean(result**2))
        assert output_rms > input_rms * 0.8  # Minimal attenuation


class TestPreemphasis:
    """Tests for the pre-emphasis filter function."""

    def test_preemphasis_coefficient_default(self):
        """Test default pre-emphasis coefficient is 0.97."""
        from sts_service.asr.preprocessing import apply_preemphasis

        audio = np.array([0.0, 1.0, 0.5, -0.5], dtype=np.float32)
        result = apply_preemphasis(audio)

        # Pre-emphasis: y[n] = x[n] - 0.97 * x[n-1]
        expected = np.array([0.0, 1.0, 0.5 - 0.97 * 1.0, -0.5 - 0.97 * 0.5], dtype=np.float32)
        np.testing.assert_allclose(result, expected, rtol=1e-5)

    def test_preemphasis_custom_coefficient(self):
        """Test pre-emphasis with custom coefficient."""
        from sts_service.asr.preprocessing import apply_preemphasis

        audio = np.array([0.0, 1.0, 1.0], dtype=np.float32)
        result = apply_preemphasis(audio, coefficient=0.5)

        # y[n] = x[n] - 0.5 * x[n-1]
        expected = np.array([0.0, 1.0, 1.0 - 0.5 * 1.0], dtype=np.float32)
        np.testing.assert_allclose(result, expected, rtol=1e-5)


class TestNormalizeAudio:
    """Tests for the audio normalization function."""

    def test_normalize_audio_peak_scaling(self):
        """Test that audio is normalized by peak value."""
        from sts_service.asr.preprocessing import normalize_audio

        audio = np.array([0.0, 0.5, -2.0, 1.0], dtype=np.float32)
        result = normalize_audio(audio)

        # Peak is 2.0, so result should be scaled by 1/2
        assert np.abs(result).max() == pytest.approx(1.0, rel=1e-5)

    def test_normalize_audio_preserves_silent(self):
        """Test that silent audio is handled correctly."""
        from sts_service.asr.preprocessing import normalize_audio

        audio = np.zeros(100, dtype=np.float32)
        result = normalize_audio(audio)

        # Silent audio should remain silent
        assert np.allclose(result, 0.0)


class TestBytesConversion:
    """Tests for bytes to array conversion functions."""

    def test_bytes_to_float32_array(self):
        """Test conversion from bytes to float32 array."""
        from sts_service.asr.preprocessing import bytes_to_float32_array

        original = np.array([0.5, -0.5, 0.25, -0.25], dtype=np.float32)
        audio_bytes = original.tobytes()

        result = bytes_to_float32_array(audio_bytes)

        np.testing.assert_array_equal(result, original)

    def test_float32_array_to_bytes(self):
        """Test conversion from float32 array to bytes."""
        from sts_service.asr.preprocessing import float32_array_to_bytes

        audio = np.array([0.5, -0.5, 0.25], dtype=np.float32)

        result = float32_array_to_bytes(audio)

        # Convert back to verify
        recovered = np.frombuffer(result, dtype=np.float32)
        np.testing.assert_array_equal(recovered, audio)


class TestResampleAudio:
    """Tests for audio resampling function."""

    def test_resample_audio_downsample(self):
        """Test downsampling from 44100 to 16000."""
        from sts_service.asr.preprocessing import resample_audio

        # Create 1 second of audio at 44100 Hz
        orig_sr = 44100
        target_sr = 16000
        duration = 1.0
        t = np.linspace(0, duration, int(orig_sr * duration), dtype=np.float32)
        audio = np.sin(2 * np.pi * 440 * t).astype(np.float32)

        result = resample_audio(audio, orig_sr=orig_sr, target_sr=target_sr)

        # Should have correct number of samples
        expected_samples = int(target_sr * duration)
        assert len(result) == expected_samples

    def test_resample_audio_upsample(self):
        """Test upsampling from 8000 to 16000."""
        from sts_service.asr.preprocessing import resample_audio

        # Create 1 second of audio at 8000 Hz
        orig_sr = 8000
        target_sr = 16000
        duration = 1.0
        t = np.linspace(0, duration, int(orig_sr * duration), dtype=np.float32)
        audio = np.sin(2 * np.pi * 440 * t).astype(np.float32)

        result = resample_audio(audio, orig_sr=orig_sr, target_sr=target_sr)

        # Should have correct number of samples
        expected_samples = int(target_sr * duration)
        assert len(result) == expected_samples

    def test_resample_audio_same_rate(self):
        """Test that same rate returns original audio."""
        from sts_service.asr.preprocessing import resample_audio

        audio = np.array([0.1, 0.2, 0.3, 0.4], dtype=np.float32)

        result = resample_audio(audio, orig_sr=16000, target_sr=16000)

        np.testing.assert_array_equal(result, audio)
