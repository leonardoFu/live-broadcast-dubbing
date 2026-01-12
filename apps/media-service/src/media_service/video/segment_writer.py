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
        """Write video segment with proper MP4 muxing using ffmpeg.

        This method creates a proper MP4 container with:
        - ftyp box (file type)
        - moov box (movie header with timing metadata)
        - mdat box (media data)

        Uses ffmpeg for reliable muxing since concatenated H.264 data
        cannot be properly muxed by GStreamer mp4mux (which expects
        individual frame buffers, not concatenated data).

        Args:
            segment: VideoSegment metadata with file_path
            video_data: Raw H.264 video data (concatenated from multiple frames)

        Returns:
            Updated VideoSegment with file_size populated

        Note:
            Requires ffmpeg to be available. Falls back to raw write
            if ffmpeg is not installed.
        """
        try:
            return await self._ffmpeg_mux_video(segment, video_data)

        except (FileNotFoundError, RuntimeError) as e:
            logger.warning(f"ffmpeg muxing failed, falling back to raw write: {e}")
            return await self.write(segment, video_data)

    async def _ffmpeg_mux_video(
        self,
        segment: VideoSegment,
        video_data: bytes,
    ) -> VideoSegment:
        """Mux video data into MP4 using ffmpeg.

        This is the proper solution for concatenated H.264 data.
        ffmpeg can handle concatenated H.264 byte-stream and properly
        create MP4 container with moov atom.

        Args:
            segment: VideoSegment metadata
            video_data: Concatenated H.264 data

        Returns:
            Updated VideoSegment with file_size populated

        Raises:
            RuntimeError: If muxing fails
            FileNotFoundError: If ffmpeg not available
        """
        import asyncio

        logger.debug(
            f"🎬 Starting ffmpeg MP4 mux for {segment.file_path}, data size={len(video_data)} bytes"
        )

        # Ensure directory exists
        segment.file_path.parent.mkdir(parents=True, exist_ok=True)

        # Write raw H.264 to temporary file
        temp_h264 = segment.file_path.with_suffix(".h264.tmp")
        try:
            temp_h264.write_bytes(video_data)
            logger.debug(f"📝 Wrote temporary H.264 file: {temp_h264}")

            # Use ffmpeg to mux into MP4
            # -f h264: input format is raw H.264
            # -i: input file
            # -c copy: codec copy (no re-encoding)
            # -movflags +faststart: optimize for streaming
            # -y: overwrite output file
            cmd = [
                "ffmpeg",
                "-f",
                "h264",
                "-i",
                str(temp_h264),
                "-c",
                "copy",
                "-movflags",
                "+faststart",
                "-y",
                str(segment.file_path),
            ]

            logger.debug(f"🚀 Running: {' '.join(cmd)}")

            # Run ffmpeg
            proc = await asyncio.create_subprocess_exec(
                *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            )

            stdout, stderr = await proc.communicate()

            if proc.returncode != 0:
                error_msg = stderr.decode("utf-8", errors="replace")
                logger.error(f"❌ ffmpeg muxing failed: {error_msg}")
                raise RuntimeError(f"ffmpeg muxing failed: {error_msg}")

            # Clean up temp file
            temp_h264.unlink()

            # Verify output file
            if not segment.file_path.exists():
                logger.error(f"❌ MP4 file not created: {segment.file_path}")
                raise RuntimeError(f"MP4 file was not created: {segment.file_path}")

            segment.file_size = segment.file_path.stat().st_size

            if segment.file_size == 0:
                logger.error("❌ MP4 file is 0 bytes!")
                raise RuntimeError("MP4 file is empty (0 bytes)")

            logger.info(
                f"✅ Video segment muxed to MP4 with ffmpeg: {segment.file_path}, "
                f"size={segment.file_size} bytes"
            )

            return segment

        except Exception:
            # Clean up temp file on error
            if temp_h264.exists():
                temp_h264.unlink()
            raise

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

        Raises:
            RuntimeError: If muxing fails
        """
        from gi.repository import Gst

        logger.debug(
            f"🎬 Starting MP4 mux for {segment.file_path}, data size={len(video_data)} bytes"
        )

        # Ensure directory exists
        segment.file_path.parent.mkdir(parents=True, exist_ok=True)

        # Create pipeline - let h264parse auto-negotiate format with mp4mux
        # h264parse will convert byte-stream → AVC as needed by mp4mux
        pipeline_str = (
            f"appsrc name=src ! h264parse ! mp4mux ! filesink location={segment.file_path}"
        )
        logger.debug(f"Pipeline: {pipeline_str}")
        pipeline = Gst.parse_launch(pipeline_str)

        # Get appsrc element
        appsrc = pipeline.get_by_name("src")
        # Explicitly specify byte-stream format with AU alignment
        # mp4mux requires alignment=au (access units = complete frames)
        # byte-stream = start codes (0x00000001) + SPS/PPS inline
        appsrc.set_property(
            "caps", Gst.Caps.from_string("video/x-h264,stream-format=byte-stream,alignment=au")
        )
        appsrc.set_property("format", 3)  # GST_FORMAT_TIME
        appsrc.set_property("is-live", False)  # Ensure proper timestamping

        # Start pipeline
        logger.debug("Setting pipeline to PLAYING...")
        ret = pipeline.set_state(Gst.State.PLAYING)
        if ret == Gst.StateChangeReturn.FAILURE:
            raise RuntimeError("Failed to set pipeline to PLAYING state")

        # Create buffer from video data
        # CRITICAL: mp4mux requires buffers to have PTS set
        logger.info(
            f"📦 Creating buffer: input pts={segment.t0_ns}ns, duration={segment.duration_ns}ns"
        )

        # Create buffer and set timestamps BEFORE pushing
        buffer = Gst.Buffer.new_allocate(None, len(video_data), None)
        buffer.fill(0, video_data)

        # Set PTS and duration - mp4mux REQUIRES these for proper muxing
        if segment.t0_ns > 0:
            buffer.pts = segment.t0_ns
        else:
            logger.warning(f"⚠️ Segment has invalid PTS: {segment.t0_ns}, using 0")
            buffer.pts = 0

        if segment.duration_ns > 0:
            buffer.duration = segment.duration_ns
        else:
            logger.warning(f"⚠️ Segment has invalid duration: {segment.duration_ns}")
            buffer.duration = Gst.CLOCK_TIME_NONE

        logger.info(
            f"✅ Buffer created: pts={buffer.pts}, duration={buffer.duration}, size={len(video_data)}"
        )

        # Push buffer (check return value!)
        logger.debug("Pushing buffer to appsrc...")
        ret = appsrc.emit("push-buffer", buffer)
        if ret != Gst.FlowReturn.OK:
            logger.error(f"❌ Failed to push buffer: {ret}")
            pipeline.set_state(Gst.State.NULL)
            raise RuntimeError(f"Failed to push buffer to appsrc: {ret}")

        # Signal end of stream
        logger.debug("Sending EOS to appsrc...")
        ret = appsrc.emit("end-of-stream")
        if ret != Gst.FlowReturn.OK:
            logger.warning(f"⚠️ EOS returned: {ret}")

        # Process ALL messages until EOS (critical for mp4mux finalization!)
        bus = pipeline.get_bus()
        logger.debug("Waiting for pipeline to finalize MP4...")

        error_occurred = False
        while True:
            msg = bus.poll(Gst.MessageType.ANY, Gst.CLOCK_TIME_NONE)

            if not msg:
                break

            if msg.type == Gst.MessageType.EOS:
                logger.debug("✅ Received EOS - mp4mux finalized")
                break
            elif msg.type == Gst.MessageType.ERROR:
                err, debug = msg.parse_error()
                logger.error(f"❌ Pipeline error: {err.message}, debug: {debug}")
                error_occurred = True
                break
            elif msg.type == Gst.MessageType.WARNING:
                warn, debug = msg.parse_warning()
                logger.warning(f"⚠️ Pipeline warning: {warn.message}")
            elif msg.type == Gst.MessageType.STATE_CHANGED:
                if msg.src == pipeline:
                    old, new, pending = msg.parse_state_changed()
                    logger.debug(f"Pipeline state: {old.value_nick} -> {new.value_nick}")

        # Clean shutdown
        pipeline.set_state(Gst.State.NULL)

        if error_occurred:
            raise RuntimeError("GStreamer pipeline error during muxing")

        # Update file size
        if segment.file_path.exists():
            segment.file_size = segment.file_path.stat().st_size
            logger.debug(f"✅ MP4 file created: {segment.file_size} bytes")
        else:
            logger.error(f"❌ MP4 file not created: {segment.file_path}")
            raise RuntimeError(f"MP4 file was not created: {segment.file_path}")

        if segment.file_size == 0:
            logger.error("❌ MP4 file is 0 bytes!")
            raise RuntimeError("MP4 file is empty (0 bytes)")

        logger.info(
            f"Video segment muxed to MP4: {segment.file_path}, size={segment.file_size} bytes"
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
