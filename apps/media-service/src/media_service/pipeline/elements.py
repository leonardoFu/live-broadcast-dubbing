"""
GStreamer element builder functions.

Provides factory functions for creating configured GStreamer elements
for RTSP input, FLV demux, and RTMP output pipelines.

Per spec 003:
- rtspsrc with protocols=tcp and configurable latency
- appsink for video (H.264) and audio (AAC)
- appsrc for output with is-live=true, format=time
- flvmux with streamable=true for RTMP
"""

from __future__ import annotations

# GStreamer imports - gracefully handle when not installed (for mocking in tests)
try:
    import gi

    gi.require_version("Gst", "1.0")
    gi.require_version("GstApp", "1.0")
    from gi.repository import Gst, GstApp

    GST_AVAILABLE = True
except (ImportError, ValueError):
    GST_AVAILABLE = False
    Gst = None  # type: ignore
    GstApp = None  # type: ignore


def _ensure_gst_initialized() -> None:
    """Ensure GStreamer is initialized."""
    if GST_AVAILABLE and Gst is not None:
        if not Gst.is_initialized():
            Gst.init(None)


def build_rtspsrc_element(url: str, latency: int = 200) -> Gst.Element:
    """Build a configured rtspsrc element.

    Args:
        url: RTSP URL (e.g., "rtsp://mediamtx:8554/live/stream/in")
        latency: Jitter buffer latency in milliseconds (default 200ms)

    Returns:
        Configured rtspsrc GStreamer element.

    Properties set:
        - location: RTSP URL
        - protocols: tcp (reliable transport)
        - latency: Jitter buffer latency in ms
    """
    _ensure_gst_initialized()

    if Gst is None:
        raise RuntimeError("GStreamer not available")

    element = Gst.ElementFactory.make("rtspsrc", "rtspsrc0")
    if element is None:
        raise RuntimeError("Failed to create rtspsrc element")

    element.set_property("location", url)
    element.set_property("protocols", "tcp")
    element.set_property("latency", latency)

    return element


def build_appsink_element(name: str, caps_string: str) -> Gst.Element:
    """Build a configured appsink element.

    Args:
        name: Element name for identification
        caps_string: GStreamer caps string (e.g., "video/x-h264", "audio/mpeg")

    Returns:
        Configured appsink GStreamer element.

    Properties set:
        - name: Element identifier
        - caps: Media type filter
        - emit-signals: True (for new-sample callback)
        - sync: False (for live streams)
    """
    _ensure_gst_initialized()

    if Gst is None:
        raise RuntimeError("GStreamer not available")

    element = Gst.ElementFactory.make("appsink", name)
    if element is None:
        raise RuntimeError(f"Failed to create appsink element: {name}")

    element.set_property("name", name)
    element.set_property("emit-signals", True)
    element.set_property("sync", False)

    caps = Gst.Caps.from_string(caps_string)
    element.set_property("caps", caps)

    return element


def build_appsrc_element(
    name: str,
    caps_string: str,
    is_live: bool = True,
) -> Gst.Element:
    """Build a configured appsrc element.

    Args:
        name: Element name for identification
        caps_string: GStreamer caps string (e.g., "video/x-h264", "audio/mpeg")
        is_live: Whether source is live (default True)

    Returns:
        Configured appsrc GStreamer element.

    Properties set:
        - name: Element identifier
        - caps: Media type
        - is-live: True for live sources
        - format: time (3) for timestamped buffers
    """
    _ensure_gst_initialized()

    if Gst is None:
        raise RuntimeError("GStreamer not available")

    element = Gst.ElementFactory.make("appsrc", name)
    if element is None:
        raise RuntimeError(f"Failed to create appsrc element: {name}")

    element.set_property("name", name)
    element.set_property("is-live", is_live)
    element.set_property("format", 3)  # GST_FORMAT_TIME = 3

    caps = Gst.Caps.from_string(caps_string)
    element.set_property("caps", caps)

    return element


def build_flvmux_element() -> Gst.Element:
    """Build a configured flvmux element for RTMP output.

    Returns:
        Configured flvmux GStreamer element.

    Properties set:
        - streamable: True (required for RTMP live streaming)
    """
    _ensure_gst_initialized()

    if Gst is None:
        raise RuntimeError("GStreamer not available")

    element = Gst.ElementFactory.make("flvmux", "flvmux0")
    if element is None:
        raise RuntimeError("Failed to create flvmux element")

    element.set_property("streamable", True)

    return element


def build_rtmpsink_element(url: str) -> Gst.Element:
    """Build a configured rtmpsink element.

    Args:
        url: RTMP URL (e.g., "rtmp://mediamtx:1935/live/stream/out")

    Returns:
        Configured rtmpsink GStreamer element.

    Properties set:
        - location: RTMP URL
    """
    _ensure_gst_initialized()

    if Gst is None:
        raise RuntimeError("GStreamer not available")

    element = Gst.ElementFactory.make("rtmpsink", "rtmpsink0")
    if element is None:
        raise RuntimeError("Failed to create rtmpsink element")

    element.set_property("location", url)

    return element


def build_flvdemux_element() -> Gst.Element:
    """Build an flvdemux element for demuxing FLV streams.

    Returns:
        Configured flvdemux GStreamer element.
    """
    _ensure_gst_initialized()

    if Gst is None:
        raise RuntimeError("GStreamer not available")

    element = Gst.ElementFactory.make("flvdemux", "flvdemux0")
    if element is None:
        raise RuntimeError("Failed to create flvdemux element")

    return element


def build_queue_element(name: str, max_buffers: int = 200) -> Gst.Element:
    """Build a queue element for buffering.

    Args:
        name: Element name
        max_buffers: Maximum number of buffers to queue

    Returns:
        Configured queue GStreamer element.
    """
    _ensure_gst_initialized()

    if Gst is None:
        raise RuntimeError("GStreamer not available")

    element = Gst.ElementFactory.make("queue", name)
    if element is None:
        raise RuntimeError(f"Failed to create queue element: {name}")

    element.set_property("max-size-buffers", max_buffers)
    element.set_property("max-size-bytes", 0)
    element.set_property("max-size-time", 0)

    return element


def build_h264parse_element() -> Gst.Element:
    """Build an h264parse element for H.264 stream parsing.

    Returns:
        Configured h264parse GStreamer element.
    """
    _ensure_gst_initialized()

    if Gst is None:
        raise RuntimeError("GStreamer not available")

    element = Gst.ElementFactory.make("h264parse", "h264parse0")
    if element is None:
        raise RuntimeError("Failed to create h264parse element")

    return element


def build_aacparse_element() -> Gst.Element:
    """Build an aacparse element for AAC audio parsing.

    Returns:
        Configured aacparse GStreamer element.
    """
    _ensure_gst_initialized()

    if Gst is None:
        raise RuntimeError("GStreamer not available")

    element = Gst.ElementFactory.make("aacparse", "aacparse0")
    if element is None:
        raise RuntimeError("Failed to create aacparse element")

    return element


def build_mp4mux_element(fragment_duration: int = 0) -> Gst.Element:
    """Build an mp4mux element for MP4/M4A container muxing.

    Args:
        fragment_duration: Fragment duration in nanoseconds (0 for non-fragmented)

    Returns:
        Configured mp4mux GStreamer element.
    """
    _ensure_gst_initialized()

    if Gst is None:
        raise RuntimeError("GStreamer not available")

    element = Gst.ElementFactory.make("mp4mux", "mp4mux0")
    if element is None:
        raise RuntimeError("Failed to create mp4mux element")

    if fragment_duration > 0:
        element.set_property("fragment-duration", fragment_duration)

    return element


def build_filesink_element(location: str) -> Gst.Element:
    """Build a filesink element for writing to disk.

    Args:
        location: File path to write

    Returns:
        Configured filesink GStreamer element.
    """
    _ensure_gst_initialized()

    if Gst is None:
        raise RuntimeError("GStreamer not available")

    element = Gst.ElementFactory.make("filesink", "filesink0")
    if element is None:
        raise RuntimeError("Failed to create filesink element")

    element.set_property("location", location)

    return element
