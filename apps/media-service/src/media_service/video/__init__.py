"""
Video processing module.

This module provides video segment writing capabilities for storing
MP4 files (H.264 codec-copy) to disk.

Components:
- VideoSegmentWriter: Writes video segments as MP4 files
"""

from __future__ import annotations

from media_service.video.segment_writer import VideoSegmentWriter

__all__ = [
    "VideoSegmentWriter",
]
