"""
A/V synchronization module.

This module provides audio/video synchronization capabilities
to maintain sync despite asynchronous STS processing latency.

Components:
- AvSyncManager: PTS management with offset and drift correction
- SyncPair: Paired video and audio segments for output
"""

from __future__ import annotations

from media_service.sync.av_sync import AvSyncManager, SyncPair

__all__ = [
    "AvSyncManager",
    "SyncPair",
]
