"""
Worker orchestration module.

Manages worker lifecycle in response to MediaMTX hook events.
"""

from media_service.orchestrator.worker_manager import WorkerManager

__all__ = ["WorkerManager"]
