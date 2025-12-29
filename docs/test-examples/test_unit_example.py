"""
Example unit test for TDD workflow.

This demonstrates:
- Test naming conventions
- Fixture usage
- Mock patterns
- Coverage best practices
"""

import pytest


# Example function to test (would be in apps/*/src/)
def chunk_audio(pcm_data: bytes, chunk_duration_ms: int, sample_rate: int) -> list[bytes]:
    """
    Chunk PCM audio into fixed-duration segments.

    Args:
        pcm_data: PCM S16LE audio bytes
        chunk_duration_ms: Chunk duration in milliseconds
        sample_rate: Sample rate in Hz

    Returns:
        List of PCM chunks

    Raises:
        ValueError: If sample_rate < 8000 or chunk_duration_ms <= 0
    """
    if sample_rate < 8000:
        raise ValueError("Sample rate must be >= 8000 Hz")
    if chunk_duration_ms <= 0:
        raise ValueError("Chunk duration must be > 0")

    # Calculate bytes per chunk (S16LE = 2 bytes per sample)
    samples_per_chunk = (sample_rate * chunk_duration_ms) // 1000
    bytes_per_chunk = samples_per_chunk * 2

    chunks = []
    for i in range(0, len(pcm_data), bytes_per_chunk):
        chunk = pcm_data[i : i + bytes_per_chunk]
        if len(chunk) > 0:
            chunks.append(chunk)

    return chunks


# Fixtures
@pytest.fixture
def sample_pcm_audio():
    """Provide 1 second of silence at 16kHz, S16LE."""
    return b"\x00\x00" * 16000


# Happy path test
def test_chunk_audio_happy_path(sample_pcm_audio):
    """Test chunking 1s audio into 500ms chunks."""
    chunks = chunk_audio(sample_pcm_audio, chunk_duration_ms=500, sample_rate=16000)

    assert len(chunks) == 2
    assert len(chunks[0]) == 16000  # 500ms at 16kHz = 8000 samples * 2 bytes
    assert len(chunks[1]) == 16000


# Error case: invalid sample rate
def test_chunk_audio_error_invalid_sample_rate(sample_pcm_audio):
    """Test chunking raises ValueError for sample_rate < 8000."""
    with pytest.raises(ValueError, match="Sample rate must be >= 8000"):
        chunk_audio(sample_pcm_audio, chunk_duration_ms=1000, sample_rate=4000)


# Error case: invalid duration
def test_chunk_audio_error_invalid_duration(sample_pcm_audio):
    """Test chunking raises ValueError for duration <= 0."""
    with pytest.raises(ValueError, match="Chunk duration must be > 0"):
        chunk_audio(sample_pcm_audio, chunk_duration_ms=0, sample_rate=16000)


# Edge case: zero-length input
def test_chunk_audio_edge_empty_input():
    """Test chunking empty audio returns empty list."""
    chunks = chunk_audio(b"", chunk_duration_ms=1000, sample_rate=16000)
    assert chunks == []


# Edge case: partial chunk
def test_chunk_audio_edge_partial_chunk():
    """Test chunking handles partial final chunk."""
    # 1.5 seconds of audio
    pcm_data = b"\x00\x00" * 24000
    chunks = chunk_audio(pcm_data, chunk_duration_ms=1000, sample_rate=16000)

    assert len(chunks) == 2
    assert len(chunks[0]) == 32000  # Full chunk
    assert len(chunks[1]) == 16000  # Partial chunk
