"""
Stream Worker package.

This package contains the StreamWorker class for processing streams via MediaMTX.
Implements User Story 3: Stream Worker Input/Output via MediaMTX.
"""

from media_service.worker.stream_worker import (
    InvalidStreamIdError,
    StreamWorker,
    create_worker_from_event,
)

__all__ = ["StreamWorker", "InvalidStreamIdError", "create_worker_from_event"]
