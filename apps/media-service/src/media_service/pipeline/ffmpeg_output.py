"""
FFmpeg-based output pipeline for RTMP stream publishing.

Publishes video (H.264) and audio (AAC) to MediaMTX via RTMP using ffmpeg
with the -re flag for real-time rate-limited output.

Approach:
1. Mux video + audio segments into a temporary FLV file
2. Read the muxed file and push to ffmpeg stdin
3. ffmpeg uses -re flag for real-time pacing to RTMP
"""

from __future__ import annotations

import logging
import os
import subprocess
import tempfile
import threading
import time
from pathlib import Path
from queue import Empty, Queue

logger = logging.getLogger(__name__)


class FFmpegOutputPipeline:
    """RTMP output pipeline using ffmpeg with -re flag.

    Muxes video and audio segments, then streams to RTMP with real-time pacing.

    Attributes:
        _rtmp_url: RTMP destination URL
        _state: Current pipeline state string
        _process: ffmpeg subprocess for RTMP output
    """

    def __init__(self, rtmp_url: str) -> None:
        """Initialize output pipeline.

        Args:
            rtmp_url: RTMP URL (e.g., "rtmp://mediamtx:1935/live/stream/out")

        Raises:
            ValueError: If RTMP URL is empty or invalid format
        """
        if not rtmp_url:
            raise ValueError("RTMP URL cannot be empty")

        if not rtmp_url.startswith("rtmp://"):
            raise ValueError(f"Invalid RTMP URL: must start with 'rtmp://' - got '{rtmp_url}'")

        self._rtmp_url = rtmp_url
        self._state = "NULL"
        self._process: subprocess.Popen | None = None

        # Queue for muxed segments to publish
        self._segment_queue: Queue = Queue(maxsize=10)

        # Publisher thread
        self._publisher_thread: threading.Thread | None = None
        self._publisher_running = False

        # Stderr reader thread for monitoring FFmpeg errors
        self._stderr_thread: threading.Thread | None = None

        # Stats for debugging
        self._segments_pushed = 0
        self._bytes_pushed = 0
        self._last_push_time: float = 0.0

        # Store codec parameters
        self._sps_pps_data: bytes | None = None

        # Temp directory for muxing
        self._temp_dir: tempfile.TemporaryDirectory | None = None

        # Track if first segment has been sent (for FLV header handling)
        self._first_segment_sent = False

    def build(self) -> None:
        """Build the ffmpeg output pipeline.

        Creates temp directory for muxing operations.
        """
        try:
            self._temp_dir = tempfile.TemporaryDirectory(prefix="ffmpeg_output_")
            self._state = "READY"
            logger.info(
                f"🎬 FFmpeg output pipeline built for {self._rtmp_url}\n"
                f"   Flow: mux segments → read → ffmpeg -re → RTMP"
            )
        except Exception as e:
            logger.error(f"Failed to build pipeline: {e}")
            raise RuntimeError(f"Failed to build pipeline: {e}")

    def _mux_segment(
        self,
        video_data: bytes,
        audio_data: bytes,
        pts_ns: int,
        video_duration_ns: int,
        audio_duration_ns: int,
    ) -> bytes | None:
        """Mux video and audio into FLV container.

        Video input is MPEG-TS format (contains H.264 with proper timestamps).
        Audio input is AAC ADTS format.

        If audio duration doesn't match video duration, audio is time-stretched
        using ffmpeg's atempo filter to maintain A/V sync. This prevents YouTube
        disconnections due to accumulated A/V desync.

        Args:
            video_data: MPEG-TS video data (contains H.264 with timestamps)
            audio_data: AAC audio data (ADTS format)
            pts_ns: Presentation timestamp in nanoseconds (for logging)
            video_duration_ns: Video duration in nanoseconds
            audio_duration_ns: Audio duration in nanoseconds

        Returns:
            Muxed FLV data, or None if muxing fails
        """
        if self._temp_dir is None:
            logger.error("Temp directory not available")
            return None

        temp_path = Path(self._temp_dir.name)
        video_path = temp_path / f"video_{pts_ns}.ts"  # MPEG-TS format
        audio_path = temp_path / f"audio_{pts_ns}.aac"
        output_path = temp_path / f"muxed_{pts_ns}.flv"

        try:
            # Write data to temp files
            video_path.write_bytes(video_data)
            audio_path.write_bytes(audio_data)

            # Calculate tempo factor for audio time-stretch if durations don't match
            video_duration_s = video_duration_ns / 1e9
            audio_duration_s = audio_duration_ns / 1e9
            pts_seconds = pts_ns / 1e9

            # Determine if we need audio time-stretching
            duration_diff = abs(video_duration_s - audio_duration_s)
            needs_timestretch = duration_diff > 0.1  # More than 100ms difference

            if needs_timestretch and audio_duration_s > 0:
                # Calculate tempo factor: audio needs to be stretched to match video
                # atempo = original_duration / target_duration
                tempo = audio_duration_s / video_duration_s

                # atempo filter only supports range [0.5, 2.0]
                tempo = max(0.5, min(2.0, tempo))

                logger.info(
                    f"⏱️ Time-stretching audio: {audio_duration_s:.2f}s -> "
                    f"{video_duration_s:.2f}s (tempo={tempo:.4f})"
                )

                cmd = [
                    "ffmpeg",
                    "-y",
                    "-f", "mpegts",
                    "-i", str(video_path),
                    "-f", "aac",
                    "-i", str(audio_path),
                    "-c:v", "copy",
                    "-af", f"atempo={tempo}",  # Time-stretch audio
                    "-c:a", "aac",  # Re-encode audio after tempo change
                    "-b:a", "128k",  # Audio bitrate
                    "-output_ts_offset", str(pts_seconds),
                    "-f", "flv",
                    str(output_path),
                ]
            else:
                # No time-stretching needed, just copy streams
                cmd = [
                    "ffmpeg",
                    "-y",
                    "-f", "mpegts",
                    "-i", str(video_path),
                    "-f", "aac",
                    "-i", str(audio_path),
                    "-c:v", "copy",
                    "-c:a", "copy",
                    "-output_ts_offset", str(pts_seconds),
                    "-f", "flv",
                    str(output_path),
                ]

            result = subprocess.run(
                cmd,
                capture_output=True,
                timeout=60,  # Increased timeout for time-stretching
            )

            if result.returncode != 0:
                logger.error(f"Muxing failed: {result.stderr.decode()}")
                return None

            # Read muxed data
            muxed_data = output_path.read_bytes()
            logger.info(f"📦 Muxed segment: {len(muxed_data)} bytes (pts={pts_ns / 1e9:.2f}s)")

            return muxed_data

        except subprocess.TimeoutExpired:
            logger.error("Muxing timeout")
            return None
        except Exception as e:
            logger.error(f"Muxing error: {e}")
            return None
        finally:
            # Cleanup temp files
            for path in [video_path, audio_path, output_path]:
                try:
                    path.unlink(missing_ok=True)
                except Exception:
                    pass

    def _start_ffmpeg_publisher(self) -> bool:
        """Start ffmpeg process for RTMP publishing.

        Returns:
            True if started successfully
        """
        # ffmpeg reads from stdin and outputs to RTMP
        # -fflags +genpts: Regenerate timestamps based on arrival time
        #   This prevents issues with offset timestamps causing -re to wait
        # -re: Output at real-time rate (prevents bursting)
        # -f flv: Input is FLV format
        # -i pipe:0: Read from stdin
        cmd = [
            "ffmpeg",
            "-y",
            "-fflags", "+genpts",
            "-re",
            "-f", "flv",
            "-i", "pipe:0",
            "-c", "copy",
            "-f", "flv",
            "-flvflags", "no_duration_filesize",
            self._rtmp_url,
        ]

        logger.info(f"🚀 Starting ffmpeg publisher: {' '.join(cmd)}")

        try:
            self._process = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            logger.info(f"✅ ffmpeg publisher started with PID {self._process.pid}")
            return True

        except FileNotFoundError:
            logger.error("ffmpeg not found in PATH")
            return False
        except Exception as e:
            logger.error(f"Failed to start ffmpeg: {e}")
            return False

    def _strip_flv_header(self, data: bytes) -> bytes:
        """Strip FLV header from segment data.

        FLV format: 9-byte header + 4-byte previous tag size (0) = 13 bytes to skip.
        Only strip from subsequent segments (not the first one).

        Args:
            data: FLV data possibly containing header

        Returns:
            FLV data with header stripped if applicable
        """
        # FLV header is 13 bytes: 9-byte header + 4-byte first previous tag size
        flv_header_size = 13

        if len(data) < flv_header_size:
            return data

        # Verify this is actually FLV data (starts with "FLV")
        if data[:3] != b"FLV":
            return data

        # Strip header from subsequent segments
        return data[flv_header_size:]

    def _restart_ffmpeg(self) -> bool:
        """Restart FFmpeg process after a crash.

        Clears queued segments since they have stale timestamps that won't work
        with the new RTMP connection. Fresh segments will be generated.

        Returns:
            True if restart succeeded
        """
        logger.info("🔄 Attempting to restart FFmpeg...")

        # Clean up old process
        if self._process:
            try:
                if self._process.stdin:
                    self._process.stdin.close()
                self._process.terminate()
                self._process.wait(timeout=2)
            except Exception:
                try:
                    self._process.kill()
                    self._process.wait(timeout=1)
                except Exception:
                    pass
            self._process = None

        # Clear queued segments - they have stale timestamps
        # New connection needs fresh segments starting from current time
        dropped_count = 0
        while not self._segment_queue.empty():
            try:
                self._segment_queue.get_nowait()
                dropped_count += 1
            except Empty:
                break
        if dropped_count > 0:
            logger.warning(f"🗑️ Dropped {dropped_count} stale segments from queue")

        # Reset state for new stream
        self._first_segment_sent = False

        # Start new FFmpeg process
        if self._start_ffmpeg_publisher():
            logger.info("✅ FFmpeg restarted successfully - waiting for fresh segments")
            return True
        else:
            logger.error("❌ Failed to restart FFmpeg")
            return False

    def _publisher_loop(self) -> None:
        """Publisher thread loop - reads muxed segments and pushes to ffmpeg."""
        logger.info("📡 Publisher thread started")
        restart_attempts = 0
        max_restart_attempts = 3

        while self._publisher_running:
            # Check if FFmpeg process is still alive
            if self._process and self._process.poll() is not None:
                exit_code = self._process.returncode
                logger.error(f"🔴 FFmpeg process died with exit code {exit_code}")
                self._check_ffmpeg_error()

                # Try to restart FFmpeg
                restart_attempts += 1
                if restart_attempts <= max_restart_attempts:
                    logger.info(
                        f"🔄 Restart attempt {restart_attempts}/{max_restart_attempts}"
                    )
                    if self._restart_ffmpeg():
                        restart_attempts = 0  # Reset on success
                        continue
                    else:
                        logger.error("Failed to restart FFmpeg, will retry...")
                        time.sleep(1)
                        continue
                else:
                    logger.error(
                        f"❌ FFmpeg restart failed after {max_restart_attempts} attempts"
                    )
                    break

            try:
                segment_data = self._segment_queue.get(timeout=0.5)
                if segment_data is None:  # Poison pill
                    break

                if self._process and self._process.stdin:
                    try:
                        # Strip FLV header from subsequent segments
                        if self._first_segment_sent:
                            segment_data = self._strip_flv_header(segment_data)
                            logger.debug(f"📦 Stripped FLV header, now {len(segment_data)} bytes")
                        else:
                            self._first_segment_sent = True
                            logger.info("📦 First segment (keeping FLV header)")

                        self._process.stdin.write(segment_data)
                        self._process.stdin.flush()
                        self._segments_pushed += 1
                        self._bytes_pushed += len(segment_data)
                        self._last_push_time = time.time()
                        total_mb = self._bytes_pushed / 1024 / 1024
                        logger.info(
                            f"📤 Pushed segment #{self._segments_pushed}: "
                            f"{len(segment_data)} bytes (total: {total_mb:.1f}MB)"
                        )
                        # Reset restart counter on successful push
                        restart_attempts = 0
                    except BrokenPipeError:
                        logger.error("ffmpeg stdin broken pipe - restarting...")
                        self._check_ffmpeg_error()
                        # Don't break, let the loop detect dead process and restart
                        continue
                    except Exception as e:
                        logger.error(f"Error writing to ffmpeg: {e}")

            except Empty:
                continue
            except Exception as e:
                logger.error(f"Publisher error: {e}")

        logger.info("📡 Publisher thread stopped")

    def _check_ffmpeg_error(self) -> None:
        """Check and log ffmpeg stderr if process failed."""
        if self._process:
            try:
                # Non-blocking read of stderr
                if self._process.stderr:
                    stderr = self._process.stderr.read()
                    if stderr:
                        logger.error(f"ffmpeg stderr: {stderr.decode()}")
            except Exception:
                pass

    def _stderr_reader_loop(self) -> None:
        """Continuously read FFmpeg stderr for error monitoring."""
        logger.info("🔍 FFmpeg stderr monitor started")

        while self._publisher_running and self._process:
            try:
                if self._process.stderr:
                    line = self._process.stderr.readline()
                    if line:
                        decoded = line.decode(errors="replace").strip()
                        # Log warnings/errors at appropriate levels
                        if "error" in decoded.lower() or "failed" in decoded.lower():
                            logger.error(f"🔴 FFmpeg: {decoded}")
                        elif "warning" in decoded.lower():
                            logger.warning(f"🟡 FFmpeg: {decoded}")
                        elif decoded:  # Other output at debug level
                            logger.debug(f"FFmpeg: {decoded}")
                    else:
                        # Empty line might mean process ended, check status
                        if self._process.poll() is not None:
                            exit_code = self._process.returncode
                            logger.error(f"🔴 FFmpeg process exited with code {exit_code}")
                            break
            except Exception as e:
                logger.warning(f"Stderr reader error: {e}")
                break

        logger.info("🔍 FFmpeg stderr monitor stopped")

    def _extract_sps_pps(self, data: bytes) -> bytes | None:
        """Extract SPS and PPS NAL units from H.264 byte-stream data.

        Args:
            data: H.264 byte-stream data

        Returns:
            Bytes containing SPS and PPS NAL units, or None if not found
        """
        sps_data = None
        pps_data = None

        i = 0
        while i < len(data) - 4:
            # Look for 4-byte start code
            if data[i : i + 4] == b"\x00\x00\x00\x01":
                nal_type = data[i + 4] & 0x1F
                next_start = len(data)
                for j in range(i + 4, min(len(data) - 3, i + 10000)):
                    if (
                        data[j : j + 4] == b"\x00\x00\x00\x01"
                        or data[j : j + 3] == b"\x00\x00\x01"
                    ):
                        next_start = j
                        break

                if nal_type == 7 and sps_data is None:
                    sps_data = data[i:next_start]
                elif nal_type == 8 and pps_data is None:
                    pps_data = data[i:next_start]

                if sps_data and pps_data:
                    break
                i = next_start
            elif data[i : i + 3] == b"\x00\x00\x01":
                nal_type = data[i + 3] & 0x1F
                next_start = len(data)
                for j in range(i + 3, min(len(data) - 3, i + 10000)):
                    if (
                        data[j : j + 4] == b"\x00\x00\x00\x01"
                        or data[j : j + 3] == b"\x00\x00\x01"
                    ):
                        next_start = j
                        break

                if nal_type == 7 and sps_data is None:
                    sps_data = b"\x00\x00\x00\x01" + data[i + 3 : next_start]
                elif nal_type == 8 and pps_data is None:
                    pps_data = b"\x00\x00\x00\x01" + data[i + 3 : next_start]

                if sps_data and pps_data:
                    break
                i = next_start
            else:
                i += 1

        if sps_data and pps_data:
            return sps_data + pps_data
        return None

    def convert_m4a_bytes_to_adts(self, m4a_data: bytes) -> bytes:
        """Convert M4A container bytes to raw ADTS AAC frames using ffmpeg.

        Args:
            m4a_data: M4A container data

        Returns:
            AAC audio data in ADTS format
        """
        with tempfile.NamedTemporaryFile(suffix=".m4a", delete=False) as tmp_in:
            tmp_in.write(m4a_data)
            tmp_in_path = tmp_in.name

        tmp_out_path = tmp_in_path.replace(".m4a", ".aac")

        try:
            cmd = [
                "ffmpeg",
                "-y",
                "-i",
                tmp_in_path,
                "-c:a",
                "copy",
                "-f",
                "adts",
                tmp_out_path,
            ]

            result = subprocess.run(
                cmd,
                capture_output=True,
                timeout=30,
            )

            if result.returncode != 0:
                logger.error(f"ffmpeg M4A->ADTS conversion failed: {result.stderr.decode()}")
                raise RuntimeError(f"M4A conversion failed: {result.stderr.decode()}")

            with open(tmp_out_path, "rb") as f:
                adts_data = f.read()

            logger.debug(f"✅ Converted M4A to {len(adts_data)} bytes of ADTS")
            return adts_data

        finally:
            try:
                os.unlink(tmp_in_path)
            except OSError:
                pass
            try:
                os.unlink(tmp_out_path)
            except OSError:
                pass

    def push_video(self, data: bytes, pts_ns: int, duration_ns: int = 0) -> bool:
        """Push video buffer to output pipeline.

        Note: This method stores video data. Call push_audio() to trigger muxing.
        Video data is expected to be MPEG-TS format (contains H.264 with timestamps).

        Args:
            data: MPEG-TS video data (contains H.264 with proper timestamps)
            pts_ns: Presentation timestamp in nanoseconds
            duration_ns: Buffer duration in nanoseconds (optional)

        Returns:
            True if stored successfully
        """
        if self._state != "PLAYING":
            logger.warning(f"Cannot push video - pipeline state: {self._state}")
            return False

        # Validate MPEG-TS format (sync byte 0x47)
        if len(data) >= 188 and data[0] == 0x47:
            logger.debug("📼 Valid MPEG-TS data detected")
        else:
            logger.warning(f"Video data may not be valid MPEG-TS (first byte: 0x{data[0]:02x})")

        # Store for muxing (will be used when push_audio is called)
        self._pending_video = (data, pts_ns, duration_ns)

        logger.info(
            f"📹 VIDEO STORED: pts={pts_ns / 1e9:.2f}s, "
            f"size={len(data)}, duration={duration_ns / 1e9:.3f}s"
        )
        return True

    def push_audio(self, data: bytes, pts_ns: int, duration_ns: int = 0) -> bool:
        """Push audio buffer and trigger muxing with pending video.

        Args:
            data: AAC encoded audio data (ADTS format)
            pts_ns: Presentation timestamp in nanoseconds
            duration_ns: Buffer duration in nanoseconds (optional)

        Returns:
            True if muxing and queueing succeeded
        """
        if self._state != "PLAYING":
            logger.warning(f"Cannot push audio - pipeline state: {self._state}")
            return False

        if not hasattr(self, "_pending_video") or self._pending_video is None:
            logger.warning("No pending video data for muxing")
            return False

        video_data, video_pts, video_duration = self._pending_video
        self._pending_video = None

        logger.info(
            f"🔊 AUDIO RECEIVED: pts={pts_ns / 1e9:.2f}s, "
            f"size={len(data)}, duration={duration_ns / 1e9:.3f}s"
        )

        # Mux video + audio
        muxed_data = self._mux_segment(
            video_data=video_data,
            audio_data=data,
            pts_ns=video_pts,
            video_duration_ns=video_duration,
            audio_duration_ns=duration_ns,
        )

        if muxed_data is None:
            logger.error("Failed to mux segment")
            return False

        # Queue for publishing
        try:
            self._segment_queue.put_nowait(muxed_data)
            logger.info(f"📥 Segment queued for publishing: {len(muxed_data)} bytes")
            return True
        except Exception as e:
            logger.error(f"Failed to queue segment: {e}")
            return False

    def start(self) -> bool:
        """Start the pipeline.

        Starts ffmpeg publisher subprocess and publisher thread.

        Returns:
            True if start succeeded
        """
        if self._state != "READY":
            logger.warning(f"Cannot start - pipeline state: {self._state}")
            return False

        try:
            # Start ffmpeg publisher
            if not self._start_ffmpeg_publisher():
                self._state = "ERROR"
                return False

            # Start publisher thread
            self._publisher_running = True
            self._publisher_thread = threading.Thread(
                target=self._publisher_loop,
                name="FFmpegPublisher",
                daemon=True,
            )
            self._publisher_thread.start()

            # Start stderr reader thread for monitoring
            self._stderr_thread = threading.Thread(
                target=self._stderr_reader_loop,
                name="FFmpegStderrReader",
                daemon=True,
            )
            self._stderr_thread.start()

            self._state = "PLAYING"
            logger.info(f"🚀 FFmpeg output pipeline started -> {self._rtmp_url}")
            return True

        except Exception as e:
            logger.error(f"Failed to start pipeline: {e}")
            self._state = "ERROR"
            return False

    def stop(self) -> None:
        """Stop the pipeline."""
        if self._state == "NULL":
            return

        logger.info("🛑 Stopping FFmpeg output pipeline...")

        # Stop publisher thread
        self._publisher_running = False

        # Send poison pill
        try:
            self._segment_queue.put_nowait(None)
        except Exception:
            pass

        # Wait for threads
        if self._publisher_thread and self._publisher_thread.is_alive():
            self._publisher_thread.join(timeout=2)

        if self._stderr_thread and self._stderr_thread.is_alive():
            self._stderr_thread.join(timeout=1)

        # Stop ffmpeg
        if self._process:
            try:
                if self._process.stdin:
                    self._process.stdin.close()
                self._process.terminate()
                self._process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._process.kill()
                self._process.wait()
            except Exception as e:
                logger.warning(f"Error stopping ffmpeg: {e}")
            finally:
                self._process = None

        self._state = "NULL"
        logger.info("✅ FFmpeg output pipeline stopped")

    def get_state(self) -> str:
        """Get current pipeline state.

        Returns:
            State string: "NULL", "READY", "PLAYING", or "ERROR"
        """
        return self._state

    def cleanup(self) -> None:
        """Clean up all resources."""
        self.stop()

        if self._temp_dir:
            try:
                self._temp_dir.cleanup()
            except Exception as e:
                logger.warning(f"Error cleaning up temp dir: {e}")
            self._temp_dir = None

        logger.info("FFmpeg output pipeline cleaned up")
