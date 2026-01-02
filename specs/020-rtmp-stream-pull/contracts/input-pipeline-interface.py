"""
Input Pipeline Interface Contract - RTMP Migration

This contract defines the InputPipeline interface after RTMP migration.
Key changes from RTSP version:
- rtsp_url -> rtmp_url parameter
- latency -> max_buffers parameter
- Simplified pad handling (no dynamic RTP depayloader creation)
"""

from typing import Protocol, Callable

# Type alias for buffer callbacks
BufferCallback = Callable[[bytes, int, int], None]  # (data, pts_ns, duration_ns)


class InputPipelineProtocol(Protocol):
    """
    Protocol defining the InputPipeline interface for RTMP stream pulling.

    Implementations must support:
    1. RTMP URL validation and stream pulling via rtmpsrc
    2. FLV demuxing into H.264 video and AAC audio via flvdemux
    3. Audio track validation (reject video-only streams)
    4. Buffer callbacks for video and audio processing
    5. GStreamer pipeline state management
    """

    def __init__(
        self,
        rtmp_url: str,
        on_video_buffer: BufferCallback,
        on_audio_buffer: BufferCallback,
        max_buffers: int = 10,
    ) -> None:
        """
        Initialize RTMP input pipeline.

        Args:
            rtmp_url: RTMP stream URL (must start with "rtmp://")
            on_video_buffer: Callback for video buffers (data, pts_ns, duration_ns)
            on_audio_buffer: Callback for audio buffers (data, pts_ns, duration_ns)
            max_buffers: flvdemux max-buffers property for buffering control (default 10)

        Raises:
            ValueError: If rtmp_url is empty or doesn't start with "rtmp://"

        Contract:
            - MUST validate rtmp_url starts with "rtmp://"
            - MUST store callbacks for later invocation
            - MUST NOT create GStreamer pipeline (deferred to build())
            - MUST initialize state to "NULL"
        """
        ...

    def build(self) -> None:
        """
        Build the GStreamer pipeline with RTMP elements.

        Pipeline structure:
            rtmpsrc -> flvdemux -> h264parse -> queue -> appsink (video)
                                -> aacparse -> queue -> appsink (audio)

        Raises:
            RuntimeError: If GStreamer not available or element creation fails

        Contract:
            - MUST create all 8 GStreamer elements (rtmpsrc, flvdemux, parsers, queues, appsinks)
            - MUST configure rtmpsrc.location = rtmp_url
            - MUST configure flvdemux.max-buffers = max_buffers
            - MUST link elements in correct order
            - MUST connect appsink signals to callback methods
            - MUST set state to "READY" after successful build
            - MUST configure video_appsink caps to "video/x-h264"
            - MUST configure audio_appsink caps to "audio/mpeg"
        """
        ...

    def start(self) -> bool:
        """
        Start the pipeline (transition to PLAYING with audio validation).

        Returns:
            True if pipeline started successfully, False otherwise

        Raises:
            RuntimeError: If pipeline not built or audio track missing

        Contract:
            - MUST call build() before start() (raise RuntimeError if not)
            - MUST transition pipeline to PAUSED first
            - MUST validate audio track presence after PAUSED state
            - MUST raise RuntimeError if audio track missing (with descriptive message)
            - MUST transition to PLAYING only if audio track validated
            - MUST set state to "PLAYING" on success
            - MUST return False if state transition fails
            - MUST complete audio validation within 2 seconds or timeout
        """
        ...

    def stop(self) -> None:
        """
        Stop the pipeline (transition to NULL).

        Contract:
            - MUST transition pipeline to NULL state
            - MUST set internal state to "NULL"
            - MUST handle gracefully if pipeline already stopped
            - MUST NOT raise exceptions on normal shutdown
        """
        ...

    def get_state(self) -> str:
        """
        Get current pipeline state.

        Returns:
            State string: "NULL", "READY", "PAUSED", "PLAYING", "ERROR", or "EOS"

        Contract:
            - MUST return one of the valid state strings
            - MUST reflect actual GStreamer pipeline state
            - MUST be callable at any time (even if pipeline not built)
        """
        ...

    def cleanup(self) -> None:
        """
        Clean up pipeline resources.

        Contract:
            - MUST call stop() to ensure pipeline is NULL
            - MUST remove bus signal watchers
            - MUST release all GStreamer element references
            - MUST be idempotent (safe to call multiple times)
        """
        ...


class RTMPStreamConfigProtocol(Protocol):
    """
    Protocol for RTMP stream configuration data.

    Used by WorkerRunner to construct RTMP URLs and initialize InputPipeline.
    """

    rtmp_url: str  # Full RTMP URL (e.g., "rtmp://mediamtx:1935/live/stream123/in")
    host: str  # MediaMTX server host
    port: int  # RTMP server port (default 1935)
    app_path: str  # Application path (e.g., "live")
    stream_id: str  # Unique stream identifier
    max_buffers: int  # flvdemux max-buffers property
    latency_ms: int  # Target total pipeline latency


class BufferCallbackProtocol(Protocol):
    """
    Protocol for buffer callback functions.

    Callbacks receive buffer data and timing information from appsinks.
    """

    def __call__(self, data: bytes, pts_ns: int, duration_ns: int) -> None:
        """
        Process buffer from appsink.

        Args:
            data: Raw buffer data (H.264 NAL units or AAC frames)
            pts_ns: Presentation timestamp in nanoseconds
            duration_ns: Buffer duration in nanoseconds

        Contract:
            - MUST NOT block for extended periods (< 10ms processing time)
            - MUST handle exceptions internally (errors should not propagate to GStreamer)
            - MUST preserve thread safety (called from GStreamer thread)
            - SHOULD maintain buffer ordering (process in PTS order)
        """
        ...


# Validation functions (module-level)

def validate_rtmp_url(url: str) -> bool:
    """
    Validate RTMP URL format.

    Args:
        url: URL string to validate

    Returns:
        True if valid RTMP URL, False otherwise

    Contract:
        - MUST return False if url is empty or None
        - MUST return False if url doesn't start with "rtmp://"
        - MUST return True if url starts with "rtmp://" and is non-empty
        - SHOULD validate URL structure (host:port/app/stream) but not required
    """
    if not url:
        return False
    return url.startswith("rtmp://")


def construct_rtmp_url(host: str, port: int, app_path: str, stream_id: str) -> str:
    """
    Construct RTMP URL from components.

    Args:
        host: MediaMTX server host
        port: RTMP server port
        app_path: Application path
        stream_id: Stream identifier

    Returns:
        Full RTMP URL

    Contract:
        - MUST return URL in format: rtmp://<host>:<port>/<app_path>/<stream_id>/in
        - MUST NOT include authentication credentials in URL
        - MUST use "/in" suffix for MediaMTX input streams
        - MUST validate all components are non-empty (raise ValueError if empty)
    """
    if not all([host, app_path, stream_id]):
        raise ValueError("host, app_path, and stream_id must be non-empty")
    if port < 1 or port > 65535:
        raise ValueError("port must be in range 1-65535")

    return f"rtmp://{host}:{port}/{app_path}/{stream_id}/in"
