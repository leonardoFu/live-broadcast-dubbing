"""
Duration Matching for TTS Audio.

Provides time-stretching functionality to align synthesized speech duration
with target duration for A/V synchronization in live streams.

Features:
- Speed factor calculation from baseline and target durations
- Clamping to prevent extreme speed factors (artifacts)
- Time-stretch via rubberband (falls back to simple method if unavailable)
- Sample rate conversion
- Channel alignment (mono/stereo)

Based on specs/008-tts-module/plan.md Phase 0 research.
"""

import logging
import struct
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class AlignmentResult:
    """Result of audio alignment operation."""

    audio_data: bytes
    final_duration_ms: int
    speed_factor_applied: float
    speed_factor_clamped: bool
    alignment_time_ms: int
    was_resampled: bool
    was_channel_converted: bool


def calculate_speed_factor(
    baseline_duration_ms: int,
    target_duration_ms: int,
) -> float:
    """Calculate speed factor needed to match target duration.

    The speed factor represents how much to speed up (>1.0) or slow down (<1.0)
    the audio to match the target duration.

    Args:
        baseline_duration_ms: Original audio duration in milliseconds
        target_duration_ms: Target duration in milliseconds

    Returns:
        Speed factor (baseline / target)

    Raises:
        ValueError: If target_duration_ms is <= 0
    """
    if target_duration_ms <= 0:
        raise ValueError(f"target_duration_ms must be positive, got {target_duration_ms}")

    if baseline_duration_ms <= 0:
        raise ValueError(f"baseline_duration_ms must be positive, got {baseline_duration_ms}")

    return baseline_duration_ms / target_duration_ms


def apply_clamping(
    speed_factor: float,
    clamp_min: float = 0.5,
    clamp_max: float = 2.0,
    only_speed_up: bool = False,
) -> tuple[float, bool]:
    """Apply clamping to speed factor to prevent extreme artifacts.

    Args:
        speed_factor: Raw speed factor from calculation
        clamp_min: Minimum allowed speed factor (default 0.5x)
        clamp_max: Maximum allowed speed factor (default 2.0x)
        only_speed_up: If True, never slow down (clamp min to 1.0)

    Returns:
        Tuple of (clamped_factor, was_clamped)
    """
    effective_min = max(clamp_min, 1.0) if only_speed_up else clamp_min

    if speed_factor < effective_min:
        return effective_min, True
    elif speed_factor > clamp_max:
        return clamp_max, True
    else:
        return speed_factor, False


def time_stretch_audio(
    audio_data: bytes,
    sample_rate_hz: int,
    speed_factor: float,
    preserve_pitch: bool = True,
) -> tuple[bytes, bool]:
    """Apply time-stretch to audio using rubberband or fallback method.

    Args:
        audio_data: PCM float32 audio bytes
        sample_rate_hz: Sample rate in Hz
        speed_factor: Speed factor to apply (>1.0 = faster, <1.0 = slower)
        preserve_pitch: Whether to preserve pitch (default True)

    Returns:
        Tuple of (stretched_audio_data, was_stretched)
    """
    # Skip if no change needed
    if abs(speed_factor - 1.0) < 0.01:
        return audio_data, False

    # Try rubberband first
    try:
        return _time_stretch_rubberband(audio_data, sample_rate_hz, speed_factor)
    except Exception as e:
        logger.warning(f"Rubberband time-stretch failed: {e}. Using fallback method.")
        return _time_stretch_simple(audio_data, sample_rate_hz, speed_factor)


def _time_stretch_rubberband(
    audio_data: bytes,
    sample_rate_hz: int,
    speed_factor: float,
) -> tuple[bytes, bool]:
    """Time-stretch using rubberband CLI tool.

    Args:
        audio_data: PCM float32 audio bytes
        sample_rate_hz: Sample rate in Hz
        speed_factor: Speed factor to apply

    Returns:
        Tuple of (stretched_audio_data, was_stretched)

    Raises:
        RuntimeError: If rubberband fails
    """
    import wave

    # Check if rubberband is available
    try:
        result = subprocess.run(
            ["rubberband", "--version"],
            capture_output=True,
            timeout=5,
        )
        if result.returncode != 0:
            raise RuntimeError("rubberband not available")
    except FileNotFoundError as err:
        raise RuntimeError("rubberband not installed") from err

    # Convert float32 PCM to int16 for WAV
    num_samples = len(audio_data) // 4  # 4 bytes per float32
    float_samples = struct.unpack(f"<{num_samples}f", audio_data)
    # Clamp and convert to int16
    int16_samples = []
    for s in float_samples:
        clamped = max(-1.0, min(1.0, s))
        int16_samples.append(int(clamped * 32767))
    int16_data = struct.pack(f"<{num_samples}h", *int16_samples)

    # Write input WAV file
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as input_file:
        input_path = input_file.name

    with wave.open(input_path, "wb") as wav:
        wav.setnchannels(1)  # Mono
        wav.setsampwidth(2)  # 16-bit
        wav.setframerate(sample_rate_hz)
        wav.writeframes(int16_data)

    output_path = input_path.replace(".wav", "_stretched.wav")

    try:
        # Run rubberband with tempo ratio
        # -T is tempo multiplier: >1 speeds up, <1 slows down
        cmd = [
            "rubberband",
            "-T",
            str(speed_factor),
            "-q",  # Quiet mode
            input_path,
            output_path,
        ]

        result = subprocess.run(
            cmd,
            capture_output=True,
            timeout=30,
        )

        if result.returncode != 0:
            raise RuntimeError(f"rubberband failed: {result.stderr.decode()}")

        # Read output WAV and convert back to float32 PCM
        with wave.open(output_path, "rb") as wav:
            out_channels = wav.getnchannels()
            out_sampwidth = wav.getsampwidth()
            out_frames = wav.readframes(wav.getnframes())

        # Convert to float32
        if out_sampwidth == 2:
            out_num_samples = len(out_frames) // (2 * out_channels)
            if out_channels == 1:
                int16_out = struct.unpack(f"<{out_num_samples}h", out_frames)
            else:
                # Stereo: take left channel only
                all_samples = struct.unpack(f"<{out_num_samples * out_channels}h", out_frames)
                int16_out = all_samples[::out_channels]
            float_out = [s / 32767.0 for s in int16_out]
            stretched_data = struct.pack(f"<{len(float_out)}f", *float_out)
        else:
            raise RuntimeError(f"Unexpected sample width from rubberband: {out_sampwidth}")

        return stretched_data, True

    finally:
        # Clean up temp files
        Path(input_path).unlink(missing_ok=True)
        Path(output_path).unlink(missing_ok=True)


def _time_stretch_simple(
    audio_data: bytes,
    sample_rate_hz: int,
    speed_factor: float,
) -> tuple[bytes, bool]:
    """Simple time-stretch by resampling (affects pitch).

    This is a fallback method when rubberband is not available.
    Note: This method changes pitch, so it's not ideal for speech.

    Args:
        audio_data: PCM float32 audio bytes
        sample_rate_hz: Sample rate in Hz
        speed_factor: Speed factor to apply

    Returns:
        Tuple of (stretched_audio_data, was_stretched)
    """
    # Unpack audio
    num_samples = len(audio_data) // 4  # 4 bytes per float32
    samples = list(struct.unpack(f"<{num_samples}f", audio_data))

    # Calculate new number of samples
    new_num_samples = int(num_samples / speed_factor)

    if new_num_samples == 0:
        return audio_data, False

    # Linear interpolation for resampling
    new_samples = []
    for i in range(new_num_samples):
        src_idx = i * speed_factor
        src_idx_int = int(src_idx)
        src_idx_frac = src_idx - src_idx_int

        if src_idx_int >= num_samples - 1:
            new_samples.append(samples[-1])
        else:
            # Linear interpolation
            sample = (
                samples[src_idx_int] * (1 - src_idx_frac) + samples[src_idx_int + 1] * src_idx_frac
            )
            new_samples.append(sample)

    return struct.pack(f"<{len(new_samples)}f", *new_samples), True


def resample_audio(
    audio_data: bytes,
    input_sample_rate_hz: int,
    output_sample_rate_hz: int,
) -> bytes:
    """Resample audio to different sample rate.

    Args:
        audio_data: PCM float32 audio bytes
        input_sample_rate_hz: Input sample rate in Hz
        output_sample_rate_hz: Output sample rate in Hz

    Returns:
        Resampled audio data
    """
    if input_sample_rate_hz == output_sample_rate_hz:
        return audio_data

    # Unpack audio
    num_samples = len(audio_data) // 4  # 4 bytes per float32
    samples = list(struct.unpack(f"<{num_samples}f", audio_data))

    # Calculate ratio
    ratio = output_sample_rate_hz / input_sample_rate_hz
    new_num_samples = int(num_samples * ratio)

    if new_num_samples == 0:
        return audio_data

    # Linear interpolation for resampling
    new_samples = []
    for i in range(new_num_samples):
        src_idx = i / ratio
        src_idx_int = int(src_idx)
        src_idx_frac = src_idx - src_idx_int

        if src_idx_int >= num_samples - 1:
            new_samples.append(samples[-1])
        else:
            # Linear interpolation
            sample = (
                samples[src_idx_int] * (1 - src_idx_frac) + samples[src_idx_int + 1] * src_idx_frac
            )
            new_samples.append(sample)

    return struct.pack(f"<{len(new_samples)}f", *new_samples)


def align_channels(
    audio_data: bytes,
    input_channels: int,
    output_channels: int,
) -> bytes:
    """Convert between mono and stereo.

    Args:
        audio_data: PCM float32 audio bytes
        input_channels: Number of input channels
        output_channels: Number of output channels

    Returns:
        Channel-aligned audio data
    """
    if input_channels == output_channels:
        return audio_data

    # Unpack audio
    num_samples = len(audio_data) // 4  # 4 bytes per float32
    samples = list(struct.unpack(f"<{num_samples}f", audio_data))

    if input_channels == 1 and output_channels == 2:
        # Mono to stereo: duplicate each sample
        new_samples = []
        for sample in samples:
            new_samples.extend([sample, sample])
        return struct.pack(f"<{len(new_samples)}f", *new_samples)

    elif input_channels == 2 and output_channels == 1:
        # Stereo to mono: average pairs
        new_samples = []
        for i in range(0, num_samples, 2):
            avg = (samples[i] + samples[i + 1]) / 2 if i + 1 < num_samples else samples[i]
            new_samples.append(avg)
        return struct.pack(f"<{len(new_samples)}f", *new_samples)

    else:
        logger.warning(f"Unsupported channel conversion: {input_channels} -> {output_channels}")
        return audio_data


def align_audio_to_duration(
    audio_data: bytes,
    baseline_duration_ms: int,
    target_duration_ms: int,
    input_sample_rate_hz: int,
    output_sample_rate_hz: int,
    input_channels: int,
    output_channels: int,
    clamp_min: float = 0.5,
    clamp_max: float = 2.0,
    only_speed_up: bool = False,
) -> AlignmentResult:
    """Complete audio alignment pipeline.

    Applies time-stretch, resampling, and channel conversion in the correct order.

    Args:
        audio_data: PCM float32 audio bytes
        baseline_duration_ms: Original audio duration
        target_duration_ms: Target duration
        input_sample_rate_hz: Input sample rate
        output_sample_rate_hz: Output sample rate
        input_channels: Input channel count
        output_channels: Output channel count
        clamp_min: Minimum speed factor
        clamp_max: Maximum speed factor
        only_speed_up: Only speed up, never slow down

    Returns:
        AlignmentResult with processed audio and metadata
    """
    import time

    start_time = time.time()

    # Calculate speed factor
    speed_factor = calculate_speed_factor(baseline_duration_ms, target_duration_ms)

    # Apply clamping
    clamped_factor, was_clamped = apply_clamping(speed_factor, clamp_min, clamp_max, only_speed_up)

    # Apply time-stretch
    stretched_data, was_stretched = time_stretch_audio(
        audio_data, input_sample_rate_hz, clamped_factor
    )

    # Resample if needed
    if input_sample_rate_hz != output_sample_rate_hz:
        resampled_data = resample_audio(stretched_data, input_sample_rate_hz, output_sample_rate_hz)
        was_resampled = True
    else:
        resampled_data = stretched_data
        was_resampled = False

    # Align channels if needed
    if input_channels != output_channels:
        aligned_data = align_channels(resampled_data, input_channels, output_channels)
        was_channel_converted = True
    else:
        aligned_data = resampled_data
        was_channel_converted = False

    # Calculate final duration
    num_samples = len(aligned_data) // (4 * output_channels)  # 4 bytes per float32
    final_duration_ms = int((num_samples / output_sample_rate_hz) * 1000)

    alignment_time_ms = int((time.time() - start_time) * 1000)

    return AlignmentResult(
        audio_data=aligned_data,
        final_duration_ms=final_duration_ms,
        speed_factor_applied=clamped_factor,
        speed_factor_clamped=was_clamped,
        alignment_time_ms=alignment_time_ms,
        was_resampled=was_resampled,
        was_channel_converted=was_channel_converted,
    )
