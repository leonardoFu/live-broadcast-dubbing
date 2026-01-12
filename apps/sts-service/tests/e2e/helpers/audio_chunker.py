"""Audio chunking utility for E2E tests.

Chunks audio files into fixed-duration segments for testing fragment processing.
Converts audio to PCM float32 format required by the STS pipeline.

Usage:
    chunker = AudioChunker("tests/fixtures/test-streams/1-min-nfl.m4a")
    chunks = chunker.chunk_audio(chunk_duration_ms=6000)

    for chunk in chunks:
        # Send chunk to STS service
        await client.emit("fragment:data", chunk.to_fragment_data())
"""

from __future__ import annotations

import base64
import logging
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class AudioChunk:
    """Audio chunk for fragment processing.

    Attributes:
        sequence_number: Fragment sequence (0-indexed)
        audio_data: Raw PCM float32 audio data (bytes)
        sample_rate: Sample rate in Hz
        channels: Number of audio channels (1=mono, 2=stereo)
        duration_ms: Duration in milliseconds
        format: Audio format (always "pcm_f32le")
    """

    sequence_number: int
    audio_data: bytes
    sample_rate: int
    channels: int
    duration_ms: int
    format: str = "pcm_f32le"

    def to_fragment_data(
        self,
        stream_id: str = "test-stream",
        fragment_id_prefix: str = "test-fragment",
    ) -> dict[str, Any]:
        """Convert chunk to fragment:data event payload.

        Args:
            stream_id: Stream identifier
            fragment_id_prefix: Prefix for fragment ID

        Returns:
            Fragment data dictionary ready for Socket.IO emission
        """
        fragment_id = f"{fragment_id_prefix}-{self.sequence_number:04d}"

        return {
            "fragment_id": fragment_id,
            "stream_id": stream_id,
            "sequence_number": self.sequence_number,
            "timestamp": self.sequence_number * self.duration_ms,  # Simulated timestamp
            "audio": base64.b64encode(self.audio_data).decode("utf-8"),
            "sample_rate": self.sample_rate,
            "channels": self.channels,
            "format": self.format,
            "duration_ms": self.duration_ms,
        }

    @property
    def size_bytes(self) -> int:
        """Get size of audio data in bytes."""
        return len(self.audio_data)

    @property
    def num_samples(self) -> int:
        """Get number of audio samples (per channel)."""
        bytes_per_sample = 4  # float32
        return len(self.audio_data) // (bytes_per_sample * self.channels)


class AudioChunker:
    """Chunk audio files into fixed-duration segments.

    Converts audio to PCM float32 mono at 16000 Hz for STS processing.

    Target format:
    - Format: PCM float32 little-endian
    - Sample rate: 16000 Hz
    - Channels: 1 (mono)
    - Encoding: Base64 for Socket.IO transmission
    """

    TARGET_SAMPLE_RATE = 16000
    TARGET_CHANNELS = 1
    TARGET_FORMAT = "pcm_f32le"

    def __init__(self, audio_file: str | Path) -> None:
        """Initialize audio chunker.

        Args:
            audio_file: Path to audio file (mp4, m4a, wav, etc.)

        Raises:
            FileNotFoundError: If audio file doesn't exist
        """
        self.audio_file = Path(audio_file)
        if not self.audio_file.exists():
            raise FileNotFoundError(f"Audio file not found: {self.audio_file}")

        logger.info(f"Initialized AudioChunker for {self.audio_file.name}")

    def chunk_audio(
        self,
        chunk_duration_ms: int = 6000,
        start_offset_ms: int = 0,
        max_chunks: int | None = None,
    ) -> list[AudioChunk]:
        """Chunk audio file into fixed-duration segments.

        Args:
            chunk_duration_ms: Duration of each chunk in milliseconds (default 6000ms = 6s)
            start_offset_ms: Start offset in milliseconds (default 0)
            max_chunks: Maximum number of chunks to return (None = all)

        Returns:
            List of AudioChunk objects

        Raises:
            RuntimeError: If ffmpeg conversion fails
        """
        logger.info(
            f"Chunking audio: {chunk_duration_ms}ms chunks, "
            f"offset={start_offset_ms}ms, max_chunks={max_chunks}"
        )

        # Convert audio to PCM float32 using ffmpeg
        pcm_data = self._convert_to_pcm()

        # Chunk the PCM data
        chunks = self._chunk_pcm_data(
            pcm_data=pcm_data,
            chunk_duration_ms=chunk_duration_ms,
            start_offset_ms=start_offset_ms,
            max_chunks=max_chunks,
        )

        logger.info(f"Created {len(chunks)} audio chunks")
        return chunks

    def _convert_to_pcm(self) -> bytes:
        """Convert audio file to PCM float32 mono 16kHz.

        Returns:
            Raw PCM float32 data

        Raises:
            RuntimeError: If ffmpeg conversion fails
        """
        # Use ffmpeg to convert to PCM float32
        cmd = [
            "ffmpeg",
            "-i",
            str(self.audio_file),
            "-f",
            "f32le",  # float32 little-endian
            "-acodec",
            "pcm_f32le",
            "-ar",
            str(self.TARGET_SAMPLE_RATE),  # 16000 Hz
            "-ac",
            str(self.TARGET_CHANNELS),  # mono
            "-",  # Output to stdout
        ]

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                check=True,
            )
            pcm_data = result.stdout
            logger.debug(
                f"Converted audio to PCM: {len(pcm_data)} bytes "
                f"({len(pcm_data) / 4 / self.TARGET_SAMPLE_RATE:.2f}s)"
            )
            return pcm_data
        except subprocess.CalledProcessError as e:
            logger.error(f"ffmpeg conversion failed: {e.stderr.decode()}")
            raise RuntimeError(f"Failed to convert audio to PCM: {e.stderr.decode()}")

    def _chunk_pcm_data(
        self,
        pcm_data: bytes,
        chunk_duration_ms: int,
        start_offset_ms: int,
        max_chunks: int | None,
    ) -> list[AudioChunk]:
        """Chunk PCM data into fixed-duration segments.

        Args:
            pcm_data: Raw PCM float32 data
            chunk_duration_ms: Duration of each chunk in milliseconds
            start_offset_ms: Start offset in milliseconds
            max_chunks: Maximum number of chunks to return

        Returns:
            List of AudioChunk objects
        """
        # Calculate chunk size in bytes
        bytes_per_sample = 4  # float32
        samples_per_chunk = int((chunk_duration_ms / 1000.0) * self.TARGET_SAMPLE_RATE)
        bytes_per_chunk = samples_per_chunk * bytes_per_sample * self.TARGET_CHANNELS

        # Calculate start offset in bytes
        samples_offset = int((start_offset_ms / 1000.0) * self.TARGET_SAMPLE_RATE)
        bytes_offset = samples_offset * bytes_per_sample * self.TARGET_CHANNELS

        # Extract chunks
        chunks = []
        sequence_number = 0
        offset = bytes_offset

        while offset < len(pcm_data):
            # Stop if max_chunks reached
            if max_chunks is not None and len(chunks) >= max_chunks:
                break

            # Extract chunk data (handle last chunk which may be shorter)
            chunk_end = min(offset + bytes_per_chunk, len(pcm_data))
            chunk_data = pcm_data[offset:chunk_end]

            # Calculate actual duration (may be shorter for last chunk)
            actual_samples = len(chunk_data) // (bytes_per_sample * self.TARGET_CHANNELS)
            actual_duration_ms = int((actual_samples / self.TARGET_SAMPLE_RATE) * 1000)

            # Create chunk
            chunk = AudioChunk(
                sequence_number=sequence_number,
                audio_data=chunk_data,
                sample_rate=self.TARGET_SAMPLE_RATE,
                channels=self.TARGET_CHANNELS,
                duration_ms=actual_duration_ms,
                format=self.TARGET_FORMAT,
            )

            chunks.append(chunk)
            sequence_number += 1
            offset = chunk_end

        return chunks

    def get_audio_info(self) -> dict[str, Any]:
        """Get audio file information using ffprobe.

        Returns:
            Dictionary with audio metadata (duration, sample_rate, channels, etc.)

        Raises:
            RuntimeError: If ffprobe fails
        """
        cmd = [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration:stream=sample_rate,channels",
            "-of",
            "json",
            str(self.audio_file),
        ]

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                check=True,
                text=True,
            )
            import json

            data = json.loads(result.stdout)
            return {
                "duration_seconds": float(data["format"]["duration"]),
                "sample_rate": int(data["streams"][0]["sample_rate"]),
                "channels": int(data["streams"][0]["channels"]),
            }
        except (subprocess.CalledProcessError, KeyError, IndexError) as e:
            logger.error(f"ffprobe failed: {e}")
            raise RuntimeError(f"Failed to get audio info: {e}")
