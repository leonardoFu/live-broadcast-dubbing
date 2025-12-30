"""
GStreamer pipeline module for stream processing.

This module provides input (RTSP) and output (RTMP) pipelines
for the stream worker, along with shared element builders.

Components:
- InputPipeline: RTSP input with video/audio appsinks
- OutputPipeline: RTMP output with video/audio appsrcs
- Element builders: Shared GStreamer element constructors
"""

from __future__ import annotations

from media_service.pipeline.elements import (
    build_aacparse_element,
    build_appsink_element,
    build_appsrc_element,
    build_filesink_element,
    build_flvdemux_element,
    build_flvmux_element,
    build_h264parse_element,
    build_mp4mux_element,
    build_queue_element,
    build_rtmpsink_element,
    build_rtspsrc_element,
)
from media_service.pipeline.input import InputPipeline
from media_service.pipeline.output import OutputPipeline

__all__ = [
    "InputPipeline",
    "OutputPipeline",
    "build_rtspsrc_element",
    "build_appsink_element",
    "build_appsrc_element",
    "build_flvmux_element",
    "build_rtmpsink_element",
    "build_flvdemux_element",
    "build_queue_element",
    "build_h264parse_element",
    "build_aacparse_element",
    "build_mp4mux_element",
    "build_filesink_element",
]
