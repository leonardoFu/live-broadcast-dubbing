"""
Buffer module for segment accumulation.

This module provides segment buffering capabilities for accumulating
6-second video and audio segments from the GStreamer pipeline.

Components:
- SegmentBuffer: Accumulates video/audio buffers into segments
"""

from __future__ import annotations

from media_service.buffer.segment_buffer import BufferAccumulator, SegmentBuffer

__all__ = [
    "SegmentBuffer",
    "BufferAccumulator",
]
