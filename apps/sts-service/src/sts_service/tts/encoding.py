"""
Audio Encoding Module for TTS Output.

Provides functionality to encode PCM audio data to compressed formats (M4A/AAC)
using ffmpeg. Returns encoded bytes as buffer for downstream consumption.

Based on specs/008-tts-module requirements for M4A output.
"""

import logging
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

from .models import AudioFormat

logger = logging.getLogger(__name__)


@dataclass
class EncodingResult:
    """Result of audio encoding operation."""

    audio_data: bytes
    format: AudioFormat
    duration_ms: int
    encoding_time_ms: int
    bitrate_kbps: int | None


class EncodingError(Exception):
    """Raised when audio encoding fails."""

    def __init__(self, message: str, details: dict | None = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}


def encode_pcm_to_m4a(
    pcm_data: bytes,
    sample_rate_hz: int,
    channels: int,
    input_format: AudioFormat = AudioFormat.PCM_F32LE,
    bitrate_kbps: int = 128,
) -> bytes:
    """Encode PCM audio data to M4A/AAC format.

    Uses ffmpeg to convert raw PCM audio to M4A container with AAC codec.
    Returns the encoded audio as bytes buffer.

    Args:
        pcm_data: Raw PCM audio bytes
        sample_rate_hz: Sample rate in Hz (e.g., 16000, 44100)
        channels: Number of audio channels (1=mono, 2=stereo)
        input_format: PCM format of input data (PCM_F32LE or PCM_S16LE)
        bitrate_kbps: Target bitrate in kbps (default 128)

    Returns:
        M4A/AAC encoded audio bytes

    Raises:
        EncodingError: If ffmpeg is not available or encoding fails
    """
    # Validate inputs
    if not pcm_data:
        raise EncodingError("Empty PCM data provided")

    if sample_rate_hz <= 0:
        raise EncodingError(f"Invalid sample rate: {sample_rate_hz}")

    if channels not in (1, 2):
        raise EncodingError(f"Invalid channel count: {channels}")

    # Check ffmpeg availability
    if not _check_ffmpeg_available():
        raise EncodingError(
            "ffmpeg not available",
            {"hint": "Install ffmpeg: brew install ffmpeg (macOS) or apt install ffmpeg (Linux)"},
        )

    # Determine ffmpeg input format
    if input_format == AudioFormat.PCM_F32LE:
        ffmpeg_format = "f32le"
    elif input_format == AudioFormat.PCM_S16LE:
        ffmpeg_format = "s16le"
    else:
        raise EncodingError(f"Unsupported input format: {input_format}")

    # Use temp files for ffmpeg I/O
    with tempfile.NamedTemporaryFile(suffix=".raw", delete=False) as input_file:
        input_file.write(pcm_data)
        input_path = Path(input_file.name)

    output_path = input_path.with_suffix(".m4a")

    try:
        # Build ffmpeg command
        cmd = [
            "ffmpeg",
            "-y",  # Overwrite output
            "-f",
            ffmpeg_format,  # Input format
            "-ar",
            str(sample_rate_hz),  # Sample rate
            "-ac",
            str(channels),  # Channels
            "-i",
            str(input_path),  # Input file
            "-c:a",
            "aac",  # AAC codec
            "-b:a",
            f"{bitrate_kbps}k",  # Bitrate
            "-movflags",
            "+faststart",  # Optimize for streaming
            str(output_path),
        ]

        # Run ffmpeg
        result = subprocess.run(
            cmd,
            capture_output=True,
            timeout=30,
        )

        if result.returncode != 0:
            stderr = result.stderr.decode("utf-8", errors="replace")
            raise EncodingError(
                f"ffmpeg encoding failed (exit code {result.returncode})",
                {"stderr": stderr[:500]},
            )

        # Read encoded output
        with open(output_path, "rb") as f:
            encoded_data = f.read()

        logger.debug(
            f"Encoded PCM to M4A: {len(pcm_data)} bytes -> {len(encoded_data)} bytes "
            f"({sample_rate_hz}Hz, {channels}ch, {bitrate_kbps}kbps)"
        )

        return encoded_data

    finally:
        # Cleanup temp files
        input_path.unlink(missing_ok=True)
        output_path.unlink(missing_ok=True)


def encode_pcm_to_m4a_with_metadata(
    pcm_data: bytes,
    sample_rate_hz: int,
    channels: int,
    input_format: AudioFormat = AudioFormat.PCM_F32LE,
    bitrate_kbps: int = 128,
) -> EncodingResult:
    """Encode PCM to M4A with full metadata in result.

    Wrapper around encode_pcm_to_m4a that returns detailed encoding result.

    Args:
        pcm_data: Raw PCM audio bytes
        sample_rate_hz: Sample rate in Hz
        channels: Number of audio channels
        input_format: PCM format of input data
        bitrate_kbps: Target bitrate in kbps

    Returns:
        EncodingResult with encoded data and metadata
    """
    import time

    start_time = time.time()

    encoded_data = encode_pcm_to_m4a(
        pcm_data=pcm_data,
        sample_rate_hz=sample_rate_hz,
        channels=channels,
        input_format=input_format,
        bitrate_kbps=bitrate_kbps,
    )

    encoding_time_ms = int((time.time() - start_time) * 1000)

    # Calculate duration from input PCM data
    bytes_per_sample = 4 if input_format == AudioFormat.PCM_F32LE else 2
    num_samples = len(pcm_data) // (bytes_per_sample * channels)
    duration_ms = int((num_samples / sample_rate_hz) * 1000)

    return EncodingResult(
        audio_data=encoded_data,
        format=AudioFormat.M4A_AAC,
        duration_ms=duration_ms,
        encoding_time_ms=encoding_time_ms,
        bitrate_kbps=bitrate_kbps,
    )


def _check_ffmpeg_available() -> bool:
    """Check if ffmpeg is available in PATH."""
    try:
        result = subprocess.run(
            ["ffmpeg", "-version"],
            capture_output=True,
            timeout=5,
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def get_m4a_duration_ms(m4a_data: bytes) -> int | None:
    """Get duration of M4A audio in milliseconds using ffprobe.

    Args:
        m4a_data: M4A audio bytes

    Returns:
        Duration in milliseconds, or None if unable to determine
    """
    with tempfile.NamedTemporaryFile(suffix=".m4a", delete=False) as f:
        f.write(m4a_data)
        temp_path = Path(f.name)

    try:
        cmd = [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(temp_path),
        ]

        result = subprocess.run(
            cmd,
            capture_output=True,
            timeout=10,
        )

        if result.returncode == 0:
            duration_sec = float(result.stdout.decode().strip())
            return int(duration_sec * 1000)
        return None

    except (subprocess.TimeoutExpired, ValueError, FileNotFoundError):
        return None

    finally:
        temp_path.unlink(missing_ok=True)
