"""
Unit tests for artifact logger.

Tests artifact logging functionality including:
- Writing intermediate assets to disk (transcript, translation, audio)
- Writing metadata JSON with timings and status
- Retention policy enforcement
- Enable/disable via configuration
"""

import base64
import json
import os
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict

import pytest

from sts_service.full.models.asset import AssetStatus, AudioAsset, TranscriptAsset, TranslationAsset


# Test fixtures
@pytest.fixture
def temp_artifacts_dir():
    """Create temporary directory for artifact storage."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


@pytest.fixture
def sample_transcript_asset() -> TranscriptAsset:
    """Create sample transcript asset for testing."""
    from sts_service.full.models.asset import TranscriptSegment

    return TranscriptAsset(
        asset_id="transcript-001",
        fragment_id="frag-001",
        stream_id="stream-001",
        status=AssetStatus.SUCCESS,
        transcript="Hello, this is a test transcript.",
        segments=[
            TranscriptSegment(
                text="Hello, this is a test transcript.",
                start_ms=0,
                end_ms=2500,
                confidence=0.95
            )
        ],
        confidence=0.95,
        language="en",
        audio_duration_ms=2500,
        parent_asset_ids=[],
        latency_ms=3500,
        created_at=datetime.utcnow(),
    )


@pytest.fixture
def sample_translation_asset() -> TranslationAsset:
    """Create sample translation asset for testing."""
    return TranslationAsset(
        asset_id="translation-001",
        fragment_id="frag-001",
        stream_id="stream-001",
        status=AssetStatus.SUCCESS,
        translated_text="Hola, esto es una transcripción de prueba.",
        source_text="Hello, this is a test transcript.",
        source_language="en",
        target_language="es",
        character_count=44,
        word_expansion_ratio=1.05,
        parent_asset_ids=["transcript-001"],
        latency_ms=250,
        created_at=datetime.utcnow(),
    )


@pytest.fixture
def sample_audio_asset() -> AudioAsset:
    """Create sample audio asset for testing."""
    from sts_service.full.models.asset import DurationMatchMetadata

    # Create 1 second of silence PCM audio (48kHz, mono)
    sample_rate = 48000
    duration_samples = sample_rate * 1  # 1 second
    silence = b"\x00" * (duration_samples * 2)  # 16-bit PCM

    return AudioAsset(
        asset_id="audio-001",
        fragment_id="frag-001",
        stream_id="stream-001",
        status=AssetStatus.SUCCESS,
        audio_bytes=silence,
        sample_rate_hz=sample_rate,
        channels=1,
        format="pcm_s16le",
        duration_ms=1000,
        duration_metadata=DurationMatchMetadata(
            original_duration_ms=1000,
            raw_duration_ms=1000,
            final_duration_ms=1000,
            duration_variance_percent=0.0,
            speed_ratio=1.0,
        ),
        text_input="Hola, esto es una transcripción de prueba.",
        parent_asset_ids=["translation-001"],
        latency_ms=1500,
        created_at=datetime.utcnow(),
    )


@pytest.fixture
def sample_fragment_data() -> Dict[str, Any]:
    """Create sample fragment data for testing."""
    # 1 second of silence PCM audio (48kHz, mono)
    sample_rate = 48000
    duration_samples = sample_rate * 1
    silence = b"\x00" * (duration_samples * 2)
    audio_base64 = base64.b64encode(silence).decode("utf-8")

    return {
        "fragment_id": "frag-001",
        "stream_id": "stream-001",
        "sequence_number": 0,
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "audio": audio_base64,
        "sample_rate": sample_rate,
        "channels": 1,
        "format": "pcm",
        "duration_ms": 1000,
    }


# T128: Test artifact logger writes transcript
def test_artifact_logger_writes_transcript(
    temp_artifacts_dir, sample_transcript_asset
):
    """
    Test that artifact logger writes transcript to disk.

    Given: Artifact logger configured with temp directory
    When: log_transcript() called with TranscriptAsset
    Then: transcript.txt file created at {artifacts_path}/{stream_id}/{fragment_id}/
    And: File contains transcript text
    """
    from sts_service.full.observability.artifact_logger import ArtifactLogger

    # Initialize logger
    logger = ArtifactLogger(
        artifacts_path=temp_artifacts_dir,
        enable_logging=True,
        retention_hours=24,
        max_count=1000,
    )

    # Log transcript
    logger.log_transcript(sample_transcript_asset)

    # Verify file created
    expected_path = Path(temp_artifacts_dir) / "stream-001" / "frag-001" / "transcript.txt"
    assert expected_path.exists(), f"Transcript file not created at {expected_path}"

    # Verify content
    content = expected_path.read_text()
    assert content == "Hello, this is a test transcript."


# T128: Test artifact logger writes translation
def test_artifact_logger_writes_translation(
    temp_artifacts_dir, sample_translation_asset
):
    """
    Test that artifact logger writes translation to disk.

    Given: Artifact logger configured with temp directory
    When: log_translation() called with TranslationAsset
    Then: translation.txt file created
    And: File contains translated text
    """
    from sts_service.full.observability.artifact_logger import ArtifactLogger

    logger = ArtifactLogger(
        artifacts_path=temp_artifacts_dir,
        enable_logging=True,
        retention_hours=24,
        max_count=1000,
    )

    logger.log_translation(sample_translation_asset)

    expected_path = Path(temp_artifacts_dir) / "stream-001" / "frag-001" / "translation.txt"
    assert expected_path.exists()

    content = expected_path.read_text()
    assert content == "Hola, esto es una transcripción de prueba."


# T128: Test artifact logger writes dubbed audio
def test_artifact_logger_writes_dubbed_audio(temp_artifacts_dir, sample_audio_asset):
    """
    Test that artifact logger writes dubbed audio to disk.

    Given: Artifact logger configured
    When: log_dubbed_audio() called with AudioAsset
    Then: dubbed_audio.m4a file created (PCM encoded as AAC in M4A container)
    And: File contains audio data
    """
    from sts_service.full.observability.artifact_logger import ArtifactLogger

    logger = ArtifactLogger(
        artifacts_path=temp_artifacts_dir,
        enable_logging=True,
        retention_hours=24,
        max_count=1000,
    )

    logger.log_dubbed_audio(sample_audio_asset)

    expected_path = Path(temp_artifacts_dir) / "stream-001" / "frag-001" / "dubbed_audio.m4a"
    assert expected_path.exists()

    # Verify file has content (should be non-empty after encoding)
    file_size = expected_path.stat().st_size
    assert file_size > 0, "Dubbed audio file is empty"


# T128: Test artifact logger writes original audio
def test_artifact_logger_writes_original_audio(temp_artifacts_dir, sample_fragment_data):
    """
    Test that artifact logger writes original audio to disk.

    Given: Artifact logger configured
    When: log_original_audio() called with fragment data
    Then: original_audio.m4a file created
    And: File contains decoded base64 audio
    """
    from sts_service.full.observability.artifact_logger import ArtifactLogger

    logger = ArtifactLogger(
        artifacts_path=temp_artifacts_dir,
        enable_logging=True,
        retention_hours=24,
        max_count=1000,
    )

    logger.log_original_audio(
        fragment_id=sample_fragment_data["fragment_id"],
        stream_id=sample_fragment_data["stream_id"],
        audio_base64=sample_fragment_data["audio"],
        sample_rate=sample_fragment_data["sample_rate"],
        channels=sample_fragment_data["channels"],
    )

    expected_path = Path(temp_artifacts_dir) / "stream-001" / "frag-001" / "original_audio.m4a"
    assert expected_path.exists()

    file_size = expected_path.stat().st_size
    assert file_size > 0


# T129: Test artifact logger writes metadata JSON
def test_artifact_logger_writes_metadata(
    temp_artifacts_dir,
    sample_transcript_asset,
    sample_translation_asset,
    sample_audio_asset,
):
    """
    Test that artifact logger writes metadata JSON with timings and status.

    Given: Artifact logger configured
    When: log_metadata() called with assets and timings
    Then: metadata.json file created
    And: File contains fragment_id, stream_id, status, timings, parent_asset_ids
    """
    from sts_service.full.observability.artifact_logger import ArtifactLogger

    logger = ArtifactLogger(
        artifacts_path=temp_artifacts_dir,
        enable_logging=True,
        retention_hours=24,
        max_count=1000,
    )

    # Log all assets first
    logger.log_transcript(sample_transcript_asset)
    logger.log_translation(sample_translation_asset)
    logger.log_dubbed_audio(sample_audio_asset)

    # Log metadata
    logger.log_metadata(
        fragment_id="frag-001",
        stream_id="stream-001",
        status="success",
        processing_time_ms=5250,
        stage_timings={
            "asr_ms": 3500,
            "translation_ms": 250,
            "tts_ms": 1500,
        },
        transcript_asset_id="transcript-001",
        translation_asset_id="translation-001",
        audio_asset_id="audio-001",
    )

    expected_path = Path(temp_artifacts_dir) / "stream-001" / "frag-001" / "metadata.json"
    assert expected_path.exists()

    # Verify content
    with open(expected_path, "r") as f:
        metadata = json.load(f)

    assert metadata["fragment_id"] == "frag-001"
    assert metadata["stream_id"] == "stream-001"
    assert metadata["status"] == "success"
    assert metadata["processing_time_ms"] == 5250
    assert metadata["stage_timings"]["asr_ms"] == 3500
    assert metadata["stage_timings"]["translation_ms"] == 250
    assert metadata["stage_timings"]["tts_ms"] == 1500
    assert "timestamp" in metadata


# T130: Test artifact logger respects enable flag
def test_artifact_logger_respects_enable_flag(
    temp_artifacts_dir, sample_transcript_asset
):
    """
    Test that artifact logger skips logging when enable_logging=False.

    Given: Artifact logger with enable_logging=False
    When: Any log method called
    Then: No files created
    """
    from sts_service.full.observability.artifact_logger import ArtifactLogger

    logger = ArtifactLogger(
        artifacts_path=temp_artifacts_dir,
        enable_logging=False,  # Disabled
        retention_hours=24,
        max_count=1000,
    )

    # Attempt to log (should be skipped)
    logger.log_transcript(sample_transcript_asset)

    # Verify no files created
    stream_dir = Path(temp_artifacts_dir) / "stream-001"
    assert not stream_dir.exists(), "Files created despite enable_logging=False"


# T130: Test artifact cleanup removes old files
def test_artifact_cleanup_removes_old_files(temp_artifacts_dir):
    """
    Test that artifact cleanup removes files older than retention_hours.

    Given: Artifact logger with retention_hours=24
    And: Artifacts older than 24 hours exist
    When: cleanup_old_artifacts() called
    Then: Old artifacts removed
    And: Recent artifacts retained
    """
    from sts_service.full.observability.artifact_logger import ArtifactLogger

    logger = ArtifactLogger(
        artifacts_path=temp_artifacts_dir,
        enable_logging=True,
        retention_hours=24,
        max_count=1000,
    )

    # Create old artifact (>24 hours old)
    old_dir = Path(temp_artifacts_dir) / "stream-001" / "frag-old"
    old_dir.mkdir(parents=True)
    old_file = old_dir / "transcript.txt"
    old_file.write_text("Old transcript")

    # Modify timestamp to be 25 hours ago
    old_time = (datetime.now() - timedelta(hours=25)).timestamp()
    os.utime(old_file, (old_time, old_time))

    # Create recent artifact (<24 hours old)
    recent_dir = Path(temp_artifacts_dir) / "stream-001" / "frag-recent"
    recent_dir.mkdir(parents=True)
    recent_file = recent_dir / "transcript.txt"
    recent_file.write_text("Recent transcript")

    # Run cleanup
    logger.cleanup_old_artifacts()

    # Verify old artifact removed
    assert not old_file.exists(), "Old artifact not removed"

    # Verify recent artifact retained
    assert recent_file.exists(), "Recent artifact incorrectly removed"


# T130: Test artifact cleanup respects max_count
def test_artifact_cleanup_respects_max_count(temp_artifacts_dir):
    """
    Test that artifact cleanup removes excess artifacts beyond max_count.

    Given: Artifact logger with max_count=3
    And: 5 fragments exist for a stream
    When: cleanup_old_artifacts() called
    Then: Only 3 most recent fragments retained
    And: 2 oldest fragments removed
    """
    from sts_service.full.observability.artifact_logger import ArtifactLogger

    logger = ArtifactLogger(
        artifacts_path=temp_artifacts_dir,
        enable_logging=True,
        retention_hours=24,
        max_count=3,  # Keep only 3 most recent
    )

    # Create 5 fragments with staggered timestamps
    stream_dir = Path(temp_artifacts_dir) / "stream-001"
    for i in range(5):
        frag_dir = stream_dir / f"frag-{i:03d}"
        frag_dir.mkdir(parents=True)
        frag_file = frag_dir / "transcript.txt"
        frag_file.write_text(f"Fragment {i}")

        # Set timestamp (i=0 oldest, i=4 newest)
        file_time = (datetime.now() - timedelta(hours=5 - i)).timestamp()
        os.utime(frag_file, (file_time, file_time))

    # Run cleanup
    logger.cleanup_old_artifacts()

    # Count remaining fragments
    remaining = list(stream_dir.iterdir())
    assert len(remaining) == 3, f"Expected 3 fragments, found {len(remaining)}"

    # Verify newest 3 fragments retained (frag-002, frag-003, frag-004)
    assert (stream_dir / "frag-002").exists()
    assert (stream_dir / "frag-003").exists()
    assert (stream_dir / "frag-004").exists()

    # Verify oldest 2 removed (frag-000, frag-001)
    assert not (stream_dir / "frag-000").exists()
    assert not (stream_dir / "frag-001").exists()


# T128: Test artifact logger creates directories
def test_artifact_logger_creates_directories(temp_artifacts_dir):
    """
    Test that artifact logger creates nested directories as needed.

    Given: Artifact logger with artifacts_path
    When: log_transcript() called for new stream/fragment
    Then: Directory structure {stream_id}/{fragment_id}/ created
    """
    from sts_service.full.observability.artifact_logger import ArtifactLogger

    logger = ArtifactLogger(
        artifacts_path=temp_artifacts_dir,
        enable_logging=True,
        retention_hours=24,
        max_count=1000,
    )

    # Create transcript asset
    transcript = TranscriptAsset(
        asset_id="transcript-001",
        fragment_id="new-frag",
        stream_id="new-stream",
        status=AssetStatus.SUCCESS,
        transcript="Test",
        segments=[],
        confidence=0.9,
        language="en",
        audio_duration_ms=1000,
        parent_asset_ids=[],
        latency_ms=1000,
        created_at=datetime.utcnow(),
    )

    logger.log_transcript(transcript)

    # Verify directory created
    expected_dir = Path(temp_artifacts_dir) / "new-stream" / "new-frag"
    assert expected_dir.exists()
    assert expected_dir.is_dir()


# T129: Test error handling for invalid paths
def test_artifact_logger_handles_invalid_path():
    """
    Test that artifact logger handles invalid artifact path gracefully.

    Given: Artifact logger with invalid path (no write permissions)
    When: log_transcript() called
    Then: Exception logged but not raised (graceful degradation)
    """
    from sts_service.full.observability.artifact_logger import ArtifactLogger

    # Use read-only path
    logger = ArtifactLogger(
        artifacts_path="/invalid/readonly/path",
        enable_logging=True,
        retention_hours=24,
        max_count=1000,
    )

    # Create transcript asset
    transcript = TranscriptAsset(
        asset_id="transcript-001",
        fragment_id="frag-001",
        stream_id="stream-001",
        status=AssetStatus.SUCCESS,
        transcript="Test",
        segments=[],
        confidence=0.9,
        language="en",
        audio_duration_ms=1000,
        parent_asset_ids=[],
        latency_ms=1000,
        created_at=datetime.utcnow(),
    )

    # Should not raise exception (graceful degradation)
    try:
        logger.log_transcript(transcript)
    except Exception as e:
        pytest.fail(f"Artifact logger raised exception: {e}")
