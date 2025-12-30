"""
Audio processing module.

This module provides audio segment writing capabilities for storing
M4A files (AAC codec-copy) to disk.

Components:
- AudioSegmentWriter: Writes audio segments as M4A files
"""

from __future__ import annotations

from media_service.audio.segment_writer import AudioSegmentWriter

__all__ = [
    "AudioSegmentWriter",
]
