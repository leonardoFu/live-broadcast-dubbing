"""
Audio segment writer for M4A file output.

Writes audio segments to disk as M4A files with AAC codec-copy.
No re-encoding occurs - original audio quality is preserved.

Per spec 003:
- M4A container for audio segments (AAC in MP4 container)
- AAC codec-copy (no re-encode)
- Segment naming: {stream_id}/{batch_number:06d}_audio.m4a
"""

from __future__ import annotations

import logging
from pathlib import Path

from media_service.models.segments import AudioSegment

logger = logging.getLogger(__name__)


class AudioSegmentWriter:
    """Writes audio segments to disk as M4A files.

    For now, writes raw AAC data directly to files.
    In production, this should use GStreamer to properly mux
    into M4A (MP4) container.

    Attributes:
        segment_dir: Base directory for segment storage
    """

    def __init__(self, segment_dir: Path) -> None:
        """Initialize audio segment writer.

        Args:
            segment_dir: Base directory for segment storage
        """
        self.segment_dir = segment_dir

    async def write(
        self,
        segment: AudioSegment,
        audio_data: bytes,
    ) -> AudioSegment:
        """Write audio segment to disk.

        Creates directory structure if needed and writes audio data
        to the segment's file_path. Updates segment.file_size after write.

        Args:
            segment: AudioSegment metadata with file_path
            audio_data: Raw AAC audio data

        Returns:
            Updated AudioSegment with file_size populated

        Note:
            This is a simplified implementation that writes raw AAC data.
            For proper M4A container muxing, use GStreamer pipeline with
            mp4mux element.
        """
        # Ensure directory exists
        segment.file_path.parent.mkdir(parents=True, exist_ok=True)

        # Write audio data
        # For production: should mux into proper M4A container
        # For now: write raw data (works for testing)
        segment.file_path.write_bytes(audio_data)

        # Update file size
        segment.file_size = len(audio_data)

        logger.info(
            f"Audio segment written: {segment.file_path}, "
            f"size={segment.file_size} bytes, "
            f"duration={segment.duration_seconds:.2f}s"
        )

        return segment

    async def write_with_mux(
        self,
        segment: AudioSegment,
        audio_data: bytes,
    ) -> AudioSegment:
        """Write audio segment with proper M4A muxing using GStreamer.

        This method creates a proper M4A container (AAC in MP4) with:
        - ftyp box (file type)
        - moov box (movie header with timing metadata)
        - mdat box (media data)

        Args:
            segment: AudioSegment metadata with file_path
            audio_data: Raw AAC audio data

        Returns:
            Updated AudioSegment with file_size populated

        Note:
            Requires GStreamer to be available. Falls back to raw write
            if GStreamer is not installed.
        """
        try:
            import gi

            gi.require_version("Gst", "1.0")
            from gi.repository import Gst

            if not Gst.is_initialized():
                Gst.init(None)

            return await self._gst_mux_audio(segment, audio_data)

        except (ImportError, ValueError) as e:
            logger.warning(f"GStreamer not available, falling back to raw write: {e}")
            return await self.write(segment, audio_data)

    async def _gst_mux_audio(
        self,
        segment: AudioSegment,
        audio_data: bytes,
    ) -> AudioSegment:
        """Mux audio data into M4A using GStreamer.

        Creates a minimal GStreamer pipeline:
        appsrc -> aacparse -> mp4mux -> filesink

        Args:
            segment: AudioSegment metadata
            audio_data: Raw AAC data

        Returns:
            Updated AudioSegment with file_size populated
        """
        from gi.repository import Gst

        # Ensure directory exists
        segment.file_path.parent.mkdir(parents=True, exist_ok=True)

        # Create pipeline
        pipeline_str = (
            f"appsrc name=src ! aacparse ! mp4mux ! "
            f"filesink location={segment.file_path}"
        )
        pipeline = Gst.parse_launch(pipeline_str)

        # Get appsrc element
        appsrc = pipeline.get_by_name("src")
        appsrc.set_property("caps", Gst.Caps.from_string(
            "audio/mpeg,mpegversion=4,stream-format=raw"
        ))
        appsrc.set_property("format", 3)  # GST_FORMAT_TIME

        # Push data
        pipeline.set_state(Gst.State.PLAYING)

        buffer = Gst.Buffer.new_allocate(None, len(audio_data), None)
        buffer.fill(0, audio_data)
        buffer.pts = segment.t0_ns
        buffer.duration = segment.duration_ns

        appsrc.emit("push-buffer", buffer)
        appsrc.emit("end-of-stream")

        # Wait for EOS
        bus = pipeline.get_bus()
        bus.timed_pop_filtered(
            Gst.CLOCK_TIME_NONE,
            Gst.MessageType.EOS | Gst.MessageType.ERROR
        )

        pipeline.set_state(Gst.State.NULL)

        # Update file size
        if segment.file_path.exists():
            segment.file_size = segment.file_path.stat().st_size

        logger.info(
            f"Audio segment muxed to M4A: {segment.file_path}, "
            f"size={segment.file_size} bytes"
        )

        return segment

    async def write_dubbed(
        self,
        segment: AudioSegment,
        dubbed_data: bytes,
        dubbed_suffix: str = "_dubbed",
    ) -> AudioSegment:
        """Write dubbed audio and update segment with dubbed path.

        Args:
            segment: Original AudioSegment
            dubbed_data: Dubbed audio data (M4A format)
            dubbed_suffix: Suffix to add before extension

        Returns:
            Updated AudioSegment with dubbed_file_path set
        """
        # Generate dubbed file path
        original_name = segment.file_path.stem
        dubbed_name = f"{original_name}{dubbed_suffix}.m4a"
        dubbed_path = segment.file_path.parent / dubbed_name

        # Write dubbed audio
        dubbed_path.parent.mkdir(parents=True, exist_ok=True)
        dubbed_path.write_bytes(dubbed_data)

        # Update segment
        segment.set_dubbed(dubbed_path)

        logger.info(
            f"Dubbed audio written: {dubbed_path}, "
            f"size={len(dubbed_data)} bytes"
        )

        return segment

    def delete(self, segment: AudioSegment) -> bool:
        """Delete audio segment files from disk.

        Deletes both original and dubbed files if they exist.

        Args:
            segment: AudioSegment to delete

        Returns:
            True if any file was deleted
        """
        deleted = False

        if segment.file_path.exists():
            segment.file_path.unlink()
            logger.info(f"Audio segment deleted: {segment.file_path}")
            deleted = True

        if segment.dubbed_file_path and segment.dubbed_file_path.exists():
            segment.dubbed_file_path.unlink()
            logger.info(f"Dubbed audio deleted: {segment.dubbed_file_path}")
            deleted = True

        return deleted
