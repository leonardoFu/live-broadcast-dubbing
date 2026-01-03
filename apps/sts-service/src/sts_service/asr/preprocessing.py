"""
Audio preprocessing functions for ASR.

Provides audio normalization, filtering, and format conversion.
Uses scipy/numpy only (no librosa dependency).
"""

from __future__ import annotations

from typing import cast

import numpy as np
from numpy.typing import NDArray
from scipy import signal


def preprocess_audio(
    audio_bytes: bytes,
    sample_rate: int,
    target_sample_rate: int = 16000,
    channels: int = 1,
    apply_filters: bool = True,
) -> NDArray[np.float32]:
    """Preprocess audio for ASR transcription.

    Applies:
    1. Byte to float32 conversion
    2. Stereo to mono conversion (if applicable)
    3. Resampling to target sample rate
    4. High-pass filter (removes rumble below 80Hz)
    5. Pre-emphasis filter (boosts high frequencies)
    6. Amplitude normalization

    Args:
        audio_bytes: Raw PCM audio bytes (float32 little-endian)
        sample_rate: Input sample rate in Hz
        target_sample_rate: Output sample rate (default 16000 for Whisper)
        channels: Number of input channels (1=mono, 2=stereo)
        apply_filters: Whether to apply highpass and preemphasis filters

    Returns:
        Preprocessed audio as float32 numpy array

    Raises:
        ValueError: If sample_rate is invalid
    """
    if sample_rate <= 0:
        raise ValueError(f"Invalid sample rate: {sample_rate}")

    # Convert bytes to float32 array
    audio = bytes_to_float32_array(audio_bytes)
    import logging
    logger = logging.getLogger(__name__)
    logger.info(f"DEBUG preprocess: After bytes_to_float32: {len(audio)} samples")

    # Convert stereo to mono if needed
    if channels == 2:
        audio = stereo_to_mono(audio)
        logger.info(f"DEBUG preprocess: After stereo_to_mono: {len(audio)} samples")

    # Resample if needed
    if sample_rate != target_sample_rate:
        logger.info(f"DEBUG preprocess: Resampling {len(audio)} samples from {sample_rate}Hz to {target_sample_rate}Hz")
        audio = resample_audio(audio, orig_sr=sample_rate, target_sr=target_sample_rate)
        logger.info(f"DEBUG preprocess: After resample: {len(audio)} samples")

    # Apply filters if requested
    if apply_filters:
        # High-pass filter to remove low-frequency rumble
        audio = apply_highpass_filter(audio, sample_rate=target_sample_rate, cutoff_hz=80)
        logger.info(f"DEBUG preprocess: After highpass: {len(audio)} samples")

        # Pre-emphasis to boost high frequencies
        audio = apply_preemphasis(audio, coefficient=0.97)
        logger.info(f"DEBUG preprocess: After preemphasis: {len(audio)} samples")

    # Normalize amplitude
    audio = normalize_audio(audio)
    logger.info(f"DEBUG preprocess: After normalize: {len(audio)} samples")

    return audio.astype(np.float32)


def bytes_to_float32_array(audio_bytes: bytes) -> NDArray[np.float32]:
    """Convert PCM bytes to float32 numpy array.

    Args:
        audio_bytes: Raw PCM bytes (float32 little-endian)

    Returns:
        Float32 numpy array
    """
    return np.frombuffer(audio_bytes, dtype=np.float32).copy()


def float32_array_to_bytes(audio: NDArray[np.float32]) -> bytes:
    """Convert float32 numpy array to PCM bytes.

    Args:
        audio: Float32 numpy array

    Returns:
        Raw PCM bytes (float32 little-endian)
    """
    return audio.astype(np.float32).tobytes()


def stereo_to_mono(audio: NDArray[np.float32]) -> NDArray[np.float32]:
    """Convert interleaved stereo audio to mono.

    Args:
        audio: Interleaved stereo audio [L0, R0, L1, R1, ...]

    Returns:
        Mono audio as average of channels
    """
    # Reshape to (samples, 2) and average
    stereo = audio.reshape(-1, 2)
    return cast(NDArray[np.float32], np.mean(stereo, axis=1).astype(np.float32))


def resample_audio(
    audio: NDArray[np.float32], orig_sr: int, target_sr: int = 16000
) -> NDArray[np.float32]:
    """Resample audio to target sample rate.

    Uses scipy's resample function for high-quality resampling.

    Args:
        audio: Input audio array
        orig_sr: Original sample rate
        target_sr: Target sample rate (default 16000)

    Returns:
        Resampled audio array
    """
    if orig_sr == target_sr:
        return audio

    # Calculate number of output samples
    duration = len(audio) / orig_sr
    num_samples = int(duration * target_sr)

    # Use scipy resample for high quality
    resampled = signal.resample(audio, num_samples)

    return cast(NDArray[np.float32], resampled.astype(np.float32))


def apply_highpass_filter(
    audio: NDArray[np.float32],
    sample_rate: int,
    cutoff_hz: int = 80,
    order: int = 5,
) -> NDArray[np.float32]:
    """Apply high-pass Butterworth filter to remove low frequencies.

    Args:
        audio: Input audio array
        sample_rate: Sample rate in Hz
        cutoff_hz: Cutoff frequency in Hz (default 80)
        order: Filter order (default 5)

    Returns:
        Filtered audio array
    """
    # Nyquist frequency
    nyquist = sample_rate / 2

    # Normalized cutoff frequency
    normalized_cutoff = cutoff_hz / nyquist

    # Clamp to valid range
    normalized_cutoff = min(max(normalized_cutoff, 0.001), 0.999)

    # Design Butterworth high-pass filter
    b, a = signal.butter(order, normalized_cutoff, btype="high")

    # Apply filter
    filtered = signal.filtfilt(b, a, audio)

    return cast(NDArray[np.float32], filtered.astype(np.float32))


def apply_preemphasis(audio: NDArray[np.float32], coefficient: float = 0.97) -> NDArray[np.float32]:
    """Apply pre-emphasis filter to boost high frequencies.

    Pre-emphasis formula: y[n] = x[n] - coefficient * x[n-1]

    Args:
        audio: Input audio array
        coefficient: Pre-emphasis coefficient (default 0.97)

    Returns:
        Pre-emphasized audio array
    """
    # Pre-emphasis: y[n] = x[n] - coef * x[n-1]
    emphasized = np.append(audio[0], audio[1:] - coefficient * audio[:-1])

    return emphasized.astype(np.float32)


def normalize_audio(audio: NDArray[np.float32], target_peak: float = 1.0) -> NDArray[np.float32]:
    """Normalize audio amplitude to target peak level.

    Args:
        audio: Input audio array
        target_peak: Target peak amplitude (default 1.0)

    Returns:
        Normalized audio array
    """
    peak = np.abs(audio).max()

    if peak < 1e-10:
        # Audio is silent, return as-is
        return audio

    # Scale to target peak
    normalized = audio * (target_peak / peak)

    return cast(NDArray[np.float32], normalized.astype(np.float32))
