"""
Stream Worker package.

This package contains the StreamWorker class for processing streams via MediaMTX.
Implements User Story 3: Stream Worker Input/Output via MediaMTX.

Also includes the WorkerRunner for full dubbing pipeline orchestration.
"""

from media_service.worker.stream_worker import (
    InvalidStreamIdError,
    StreamWorker,
    create_worker_from_event,
)
from media_service.worker.worker_runner import WorkerConfig, WorkerRunner

__all__ = [
    "StreamWorker",
    "InvalidStreamIdError",
    "create_worker_from_event",
    "WorkerRunner",
    "WorkerConfig",
]
