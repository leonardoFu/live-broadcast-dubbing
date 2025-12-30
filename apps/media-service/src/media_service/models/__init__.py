"""
Data models for media service.

This module provides data models for:
- Segments: VideoSegment, AudioSegment
- State: CircuitBreaker, AvSyncState
- Events: Stream and hook events
"""

from __future__ import annotations

from media_service.models.segments import AudioSegment, VideoSegment
from media_service.models.state import AvSyncState, CircuitBreaker, CircuitState

__all__ = [
    "AudioSegment",
    "VideoSegment",
    "CircuitBreaker",
    "AvSyncState",
    "CircuitState",
]
