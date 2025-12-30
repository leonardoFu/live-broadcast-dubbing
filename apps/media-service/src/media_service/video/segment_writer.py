"""
Video segment writer for MP4 file output.

Writes video segments to disk as MP4 files with H.264 codec-copy.
No re-encoding occurs - original video quality is preserved.

Per spec 003:
- MP4 container for video segments
- H.264 codec-copy (no re-encode)
- Segment naming: {stream_id}/{batch_number:06d}_video.mp4
"""

from __future__ import annotations

import logging
from pathlib import Path

from media_service.models.segments import VideoSegment

logger = logging.getLogger(__name__)


class VideoSegmentWriter:
    """Writes video segments to disk as MP4 files.

    For now, writes raw H.264 data directly to files.
    In production, this should use GStreamer to properly mux
    into MP4 container.

    Attributes:
        segment_dir: Base directory for segment storage
    """

    def __init__(self, segment_dir: Path) -> None:
        """Initialize video segment writer.

        Args:
            segment_dir: Base directory for segment storage
        """
        self.segment_dir = segment_dir

    async def write(
        self,
        segment: VideoSegment,
        video_data: bytes,
    ) -> VideoSegment:
        """Write video segment to disk.

        Creates directory structure if needed and writes video data
        to the segment's file_path. Updates segment.file_size after write.

        Args:
            segment: VideoSegment metadata with file_path
            video_data: Raw H.264 video data

        Returns:
            Updated VideoSegment with file_size populated

        Note:
            This is a simplified implementation that writes raw H.264 data.
            For proper MP4 container muxing, use GStreamer pipeline with
            mp4mux element.
        """
        # Ensure directory exists
        segment.file_path.parent.mkdir(parents=True, exist_ok=True)

        # Write video data
        # For production: should mux into proper MP4 container
        # For now: write raw data (works for testing)
        segment.file_path.write_bytes(video_data)

        # Update file size
        segment.file_size = len(video_data)

        logger.info(
            f"Video segment written: {segment.file_path}, "
            f"size={segment.file_size} bytes, "
            f"duration={segment.duration_seconds:.2f}s"
        )

        return segment

    async def write_with_mux(
        self,
        segment: VideoSegment,
        video_data: bytes,
    ) -> VideoSegment:
        """Write video segment with proper MP4 muxing using GStreamer.

        This method creates a proper MP4 container with:
        - ftyp box (file type)
        - moov box (movie header with timing metadata)
        - mdat box (media data)

        Args:
            segment: VideoSegment metadata with file_path
            video_data: Raw H.264 video data

        Returns:
            Updated VideoSegment with file_size populated

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

            return await self._gst_mux_video(segment, video_data)

        except (ImportError, ValueError) as e:
            logger.warning(f"GStreamer not available, falling back to raw write: {e}")
            return await self.write(segment, video_data)

    async def _gst_mux_video(
        self,
        segment: VideoSegment,
        video_data: bytes,
    ) -> VideoSegment:
        """Mux video data into MP4 using GStreamer.

        Creates a minimal GStreamer pipeline:
        appsrc -> h264parse -> mp4mux -> filesink

        Args:
            segment: VideoSegment metadata
            video_data: Raw H.264 data

        Returns:
            Updated VideoSegment with file_size populated
        """
        from gi.repository import Gst

        # Ensure directory exists
        segment.file_path.parent.mkdir(parents=True, exist_ok=True)

        # Create pipeline
        pipeline_str = (
            f"appsrc name=src ! h264parse ! mp4mux ! "
            f"filesink location={segment.file_path}"
        )
        pipeline = Gst.parse_launch(pipeline_str)

        # Get appsrc element
        appsrc = pipeline.get_by_name("src")
        appsrc.set_property("caps", Gst.Caps.from_string(
            "video/x-h264,stream-format=byte-stream"
        ))
        appsrc.set_property("format", 3)  # GST_FORMAT_TIME

        # Push data
        pipeline.set_state(Gst.State.PLAYING)

        buffer = Gst.Buffer.new_allocate(None, len(video_data), None)
        buffer.fill(0, video_data)
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
            f"Video segment muxed to MP4: {segment.file_path}, "
            f"size={segment.file_size} bytes"
        )

        return segment

    def delete(self, segment: VideoSegment) -> bool:
        """Delete video segment file from disk.

        Args:
            segment: VideoSegment to delete

        Returns:
            True if file was deleted, False if it didn't exist
        """
        if segment.file_path.exists():
            segment.file_path.unlink()
            logger.info(f"Video segment deleted: {segment.file_path}")
            return True
        return False
