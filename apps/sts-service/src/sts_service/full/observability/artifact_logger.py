"""Artifact Logger for Full STS Service.

Logs intermediate assets to disk for troubleshooting and observability:
- Original audio (base64 decoded input)
- Transcript (ASR output text)
- Translation (Translation output text)
- Dubbed audio (TTS output audio)
- Metadata JSON (asset lineage, timings, status)

Tasks: T128-T130
"""

import base64
import json
import logging
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Optional

from sts_service.full.models.asset import AudioAsset, TranscriptAsset, TranslationAsset

logger = logging.getLogger(__name__)


class ArtifactLogger:
    """Logger for saving intermediate pipeline assets to disk.

    Configuration:
    - artifacts_path: Base directory for artifact storage
    - enable_logging: Enable/disable artifact logging
    - retention_hours: Keep artifacts for N hours (default: 24)
    - max_count: Keep last N fragments per stream (default: 1000)

    Directory structure:
        {artifacts_path}/{stream_id}/{fragment_id}/
        ├── original_audio.m4a       # Base64 decoded input audio
        ├── transcript.txt           # ASR output text
        ├── translation.txt          # Translation output text
        ├── dubbed_audio.m4a         # TTS output audio
        └── metadata.json            # Asset lineage, timings, parent_asset_ids
    """

    def __init__(
        self,
        artifacts_path: str = "/tmp/sts-artifacts",
        enable_logging: bool = True,
        retention_hours: int = 24,
        max_count: int = 1000,
    ):
        """Initialize artifact logger.

        Args:
            artifacts_path: Base directory for artifact storage
            enable_logging: Enable/disable artifact logging
            retention_hours: Keep artifacts for N hours
            max_count: Keep last N fragments per stream
        """
        self.artifacts_path = Path(artifacts_path)
        self.enable_logging = enable_logging
        self.retention_hours = retention_hours
        self.max_count = max_count

        if self.enable_logging:
            logger.info(
                f"Artifact logging enabled: path={self.artifacts_path}, "
                f"retention_hours={self.retention_hours}, max_count={self.max_count}"
            )
        else:
            logger.info("Artifact logging disabled")

    def _get_fragment_dir(self, stream_id: str, fragment_id: str) -> Path:
        """Get directory path for a fragment's artifacts.

        Args:
            stream_id: Stream identifier
            fragment_id: Fragment identifier

        Returns:
            Path to fragment artifacts directory
        """
        return self.artifacts_path / stream_id / fragment_id

    def _ensure_directory(self, dir_path: Path) -> None:
        """Ensure directory exists, creating it if necessary.

        Args:
            dir_path: Directory path to create
        """
        try:
            dir_path.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            logger.error(f"Failed to create directory {dir_path}: {e}")
            # Don't raise exception - graceful degradation

    def _write_file(self, file_path: Path, content: bytes | str, mode: str = "w") -> None:
        """Write content to file.

        Args:
            file_path: File path to write
            content: Content to write (str or bytes)
            mode: File open mode ('w' for text, 'wb' for binary)
        """
        try:
            if isinstance(content, str):
                with open(file_path, mode, encoding="utf-8") as f:
                    f.write(content)
            else:
                with open(file_path, "wb") as f:
                    f.write(content)
            logger.debug(f"Wrote artifact: {file_path}")
        except Exception as e:
            logger.error(f"Failed to write file {file_path}: {e}")
            # Don't raise exception - graceful degradation

    def _pcm_to_m4a(self, pcm_audio: bytes, sample_rate: int, channels: int) -> bytes:
        """Convert PCM audio to M4A format.

        Args:
            pcm_audio: Raw PCM audio bytes
            sample_rate: Sample rate in Hz
            channels: Number of audio channels

        Returns:
            M4A encoded audio bytes

        Note:
            Uses pydub and ffmpeg for encoding. If encoding fails, returns
            raw PCM audio as fallback.
        """
        try:
            from pydub import AudioSegment

            # Create AudioSegment from raw PCM
            audio = AudioSegment(
                data=pcm_audio,
                sample_width=2,  # 16-bit PCM
                frame_rate=sample_rate,
                channels=channels,
            )

            # Export as M4A (AAC codec)
            from io import BytesIO
            buffer = BytesIO()
            audio.export(buffer, format="ipod", codec="aac")
            return buffer.getvalue()
        except Exception as e:
            logger.warning(f"Failed to encode PCM to M4A: {e}. Saving raw PCM.")
            return pcm_audio

    def log_transcript(self, transcript_asset: TranscriptAsset) -> None:
        """Log transcript to disk.

        Args:
            transcript_asset: Transcript asset from ASR module
        """
        if not self.enable_logging:
            return

        try:
            # Get fragment directory
            fragment_dir = self._get_fragment_dir(
                transcript_asset.stream_id, transcript_asset.fragment_id
            )
            self._ensure_directory(fragment_dir)

            # Write transcript text
            transcript_path = fragment_dir / "transcript.txt"
            self._write_file(transcript_path, transcript_asset.transcript)

        except Exception as e:
            logger.error(f"Failed to log transcript: {e}")

    def log_translation(self, translation_asset: TranslationAsset) -> None:
        """Log translation to disk.

        Args:
            translation_asset: Translation asset from Translation module
        """
        if not self.enable_logging:
            return

        try:
            fragment_dir = self._get_fragment_dir(
                translation_asset.stream_id, translation_asset.fragment_id
            )
            self._ensure_directory(fragment_dir)

            # Write translation text
            translation_path = fragment_dir / "translation.txt"
            self._write_file(translation_path, translation_asset.translated_text)

        except Exception as e:
            logger.error(f"Failed to log translation: {e}")

    def log_dubbed_audio(self, audio_asset: AudioAsset) -> None:
        """Log dubbed audio to disk.

        Args:
            audio_asset: Audio asset from TTS module
        """
        if not self.enable_logging:
            return

        try:
            fragment_dir = self._get_fragment_dir(
                audio_asset.stream_id, audio_asset.fragment_id
            )
            self._ensure_directory(fragment_dir)

            # Convert PCM to M4A
            m4a_audio = self._pcm_to_m4a(
                audio_asset.audio_bytes,
                audio_asset.sample_rate_hz,
                audio_asset.channels,
            )

            # Write dubbed audio
            dubbed_audio_path = fragment_dir / "dubbed_audio.m4a"
            self._write_file(dubbed_audio_path, m4a_audio, mode="wb")

        except Exception as e:
            logger.error(f"Failed to log dubbed audio: {e}")

    def log_original_audio(
        self,
        fragment_id: str,
        stream_id: str,
        audio_base64: str,
        sample_rate: int,
        channels: int,
    ) -> None:
        """Log original audio to disk.

        Args:
            fragment_id: Fragment identifier
            stream_id: Stream identifier
            audio_base64: Base64 encoded audio
            sample_rate: Sample rate in Hz
            channels: Number of audio channels
        """
        if not self.enable_logging:
            return

        try:
            fragment_dir = self._get_fragment_dir(stream_id, fragment_id)
            self._ensure_directory(fragment_dir)

            # Decode base64 audio
            pcm_audio = base64.b64decode(audio_base64)

            # Convert PCM to M4A
            m4a_audio = self._pcm_to_m4a(pcm_audio, sample_rate, channels)

            # Write original audio
            original_audio_path = fragment_dir / "original_audio.m4a"
            self._write_file(original_audio_path, m4a_audio, mode="wb")

        except Exception as e:
            logger.error(f"Failed to log original audio: {e}")

    def log_metadata(
        self,
        fragment_id: str,
        stream_id: str,
        status: str,
        processing_time_ms: int,
        stage_timings: Dict[str, int],
        transcript_asset_id: Optional[str] = None,
        translation_asset_id: Optional[str] = None,
        audio_asset_id: Optional[str] = None,
        error: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Log metadata JSON with timings and asset lineage.

        Args:
            fragment_id: Fragment identifier
            stream_id: Stream identifier
            status: Fragment processing status (success, partial, failed)
            processing_time_ms: Total processing time in milliseconds
            stage_timings: Stage-level timings (asr_ms, translation_ms, tts_ms)
            transcript_asset_id: Asset ID for transcript
            translation_asset_id: Asset ID for translation
            audio_asset_id: Asset ID for dubbed audio
            error: Error details if status is failed
        """
        if not self.enable_logging:
            return

        try:
            fragment_dir = self._get_fragment_dir(stream_id, fragment_id)
            self._ensure_directory(fragment_dir)

            # Build metadata
            metadata = {
                "fragment_id": fragment_id,
                "stream_id": stream_id,
                "status": status,
                "processing_time_ms": processing_time_ms,
                "stage_timings": stage_timings,
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "asset_lineage": {
                    "transcript_asset_id": transcript_asset_id,
                    "translation_asset_id": translation_asset_id,
                    "audio_asset_id": audio_asset_id,
                },
            }

            if error:
                metadata["error"] = error

            # Write metadata JSON
            metadata_path = fragment_dir / "metadata.json"
            self._write_file(metadata_path, json.dumps(metadata, indent=2))

        except Exception as e:
            logger.error(f"Failed to log metadata: {e}")

    def cleanup_old_artifacts(self) -> None:
        """Remove artifacts older than retention_hours or exceeding max_count.

        Cleanup strategy:
        1. Remove artifacts older than retention_hours
        2. Per stream, keep only max_count most recent fragments
        """
        if not self.enable_logging:
            return

        try:
            cutoff_time = datetime.now() - timedelta(hours=self.retention_hours)

            # Iterate through streams
            for stream_dir in self.artifacts_path.iterdir():
                if not stream_dir.is_dir():
                    continue

                # Get all fragment directories with their modification times
                fragments = []
                for fragment_dir in stream_dir.iterdir():
                    if not fragment_dir.is_dir():
                        continue

                    # Get oldest file modification time in fragment
                    oldest_time = None
                    for file_path in fragment_dir.iterdir():
                        if file_path.is_file():
                            mtime = datetime.fromtimestamp(file_path.stat().st_mtime)
                            if oldest_time is None or mtime < oldest_time:
                                oldest_time = mtime

                    if oldest_time:
                        fragments.append((fragment_dir, oldest_time))

                # Sort by modification time (oldest first)
                fragments.sort(key=lambda x: x[1])

                # Remove old fragments (retention policy)
                removed_count = 0
                for fragment_dir, mtime in fragments:
                    if mtime < cutoff_time:
                        self._remove_directory(fragment_dir)
                        removed_count += 1

                # Remove excess fragments (max_count policy)
                remaining_fragments = fragments[removed_count:]
                if len(remaining_fragments) > self.max_count:
                    excess_count = len(remaining_fragments) - self.max_count
                    for fragment_dir, _ in remaining_fragments[:excess_count]:
                        self._remove_directory(fragment_dir)
                        removed_count += 1

                if removed_count > 0:
                    logger.info(
                        f"Cleaned up {removed_count} fragments from stream {stream_dir.name}"
                    )

        except Exception as e:
            logger.error(f"Failed to cleanup artifacts: {e}")

    def _remove_directory(self, dir_path: Path) -> None:
        """Remove directory and all its contents.

        Args:
            dir_path: Directory to remove
        """
        try:
            import shutil
            shutil.rmtree(dir_path)
            logger.debug(f"Removed artifact directory: {dir_path}")
        except Exception as e:
            logger.error(f"Failed to remove directory {dir_path}: {e}")
