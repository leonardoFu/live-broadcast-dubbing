"""
Worker Manager for stream lifecycle orchestration.

Bridges MediaMTX hook events to WorkerRunner instances. Manages:
- Worker registry (stream_id -> WorkerRunner mapping)
- Lifecycle management (start/stop workers on demand)
- Idempotency (prevents duplicate workers for same stream)
- Graceful cleanup

Per spec 003 and E2E requirements:
- At-most-one worker per stream
- Thread-safe with locks per stream
- Graceful error handling
"""

from __future__ import annotations

import asyncio
import logging

from media_service.worker.worker_runner import WorkerConfig, WorkerRunner

logger = logging.getLogger(__name__)


class WorkerManager:
    """Manages worker lifecycle in response to MediaMTX events.

    Provides idempotent worker creation and cleanup:
    - start_worker(): Creates worker if not exists, safe to call multiple times
    - stop_worker(): Stops and removes worker, handles nonexistent gracefully
    - get_worker(): Retrieves active worker or None
    - cleanup_all(): Stops all workers on shutdown

    Thread-safety: Uses per-stream locks to prevent race conditions.
    """

    def __init__(self) -> None:
        """Initialize worker manager with empty registry."""
        self._workers: dict[str, WorkerRunner] = {}
        self._locks: dict[str, asyncio.Lock] = {}
        logger.info("WorkerManager initialized")

    async def start_worker(self, stream_id: str, config: WorkerConfig) -> None:
        """Start worker for stream (idempotent - safe to call multiple times).

        If worker already exists for this stream, this is a no-op.
        Uses per-stream lock to prevent concurrent creation.

        Args:
            stream_id: Stream identifier
            config: Worker configuration

        Raises:
            RuntimeError: If worker startup fails
        """
        # Get or create lock for this stream
        if stream_id not in self._locks:
            self._locks[stream_id] = asyncio.Lock()

        async with self._locks[stream_id]:
            # Check if worker already exists (idempotency)
            if stream_id in self._workers:
                logger.debug(
                    f"Worker for stream {stream_id} already exists, skipping creation",
                    extra={"stream_id": stream_id}
                )
                return

            # Create and start worker
            logger.info(
                f"Starting worker for stream {stream_id}",
                extra={
                    "stream_id": stream_id,
                    "rtmp_input_url": config.rtmp_input_url,
                    "rtmp_url": config.rtmp_url,
                    "sts_url": config.sts_url,
                }
            )

            try:
                worker = WorkerRunner(config)
                await worker.start()

                # Add to registry only after successful start
                self._workers[stream_id] = worker

                logger.info(
                    f"Worker started successfully for stream {stream_id}",
                    extra={
                        "stream_id": stream_id,
                        "active_workers": len(self._workers),
                    }
                )

            except Exception as e:
                logger.error(
                    f"Failed to start worker for stream {stream_id}: {e}",
                    extra={"stream_id": stream_id, "error": str(e)},
                    exc_info=True,
                )
                # Do NOT add to registry if startup failed
                raise

    async def stop_worker(self, stream_id: str) -> None:
        """Stop and cleanup worker.

        If worker doesn't exist, this is a no-op (doesn't raise error).
        Handles worker.stop() failures gracefully - worker is removed
        from registry even if stop fails.

        Args:
            stream_id: Stream identifier
        """
        # Get lock if exists
        if stream_id not in self._locks:
            logger.debug(
                f"No lock for stream {stream_id}, worker likely doesn't exist",
                extra={"stream_id": stream_id}
            )
            return

        async with self._locks[stream_id]:
            worker = self._workers.get(stream_id)

            if worker is None:
                logger.debug(
                    f"Worker for stream {stream_id} not found, nothing to stop",
                    extra={"stream_id": stream_id}
                )
                return

            logger.info(
                f"Stopping worker for stream {stream_id}",
                extra={"stream_id": stream_id}
            )

            try:
                await worker.stop()
                logger.info(
                    f"Worker stopped successfully for stream {stream_id}",
                    extra={"stream_id": stream_id}
                )

            except Exception as e:
                logger.error(
                    f"Error stopping worker for stream {stream_id}: {e}",
                    extra={"stream_id": stream_id, "error": str(e)},
                    exc_info=True,
                )
                # Continue to remove from registry even if stop failed

            finally:
                # Always remove from registry
                del self._workers[stream_id]
                logger.debug(
                    f"Worker removed from registry for stream {stream_id}",
                    extra={
                        "stream_id": stream_id,
                        "active_workers": len(self._workers),
                    }
                )

    def get_worker(self, stream_id: str) -> WorkerRunner | None:
        """Get active worker if exists.

        Args:
            stream_id: Stream identifier

        Returns:
            WorkerRunner instance or None if not found
        """
        return self._workers.get(stream_id)

    async def cleanup_all(self) -> None:
        """Stop and cleanup all active workers.

        Called during service shutdown. Stops all workers in parallel
        and handles failures gracefully (continues even if some fail).
        """
        if not self._workers:
            logger.info("No active workers to cleanup")
            return

        logger.info(
            f"Cleaning up {len(self._workers)} active workers",
            extra={"active_workers": len(self._workers)}
        )

        # Get list of stream IDs (copy to avoid modification during iteration)
        stream_ids = list(self._workers.keys())

        # Stop all workers in parallel
        tasks = [self.stop_worker(stream_id) for stream_id in stream_ids]

        # Wait for all to complete, collecting exceptions
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Log any failures
        failures = [r for r in results if isinstance(r, Exception)]
        if failures:
            logger.warning(
                f"Some workers failed to stop cleanly: {len(failures)} failures",
                extra={"failure_count": len(failures)}
            )

        logger.info(
            "Worker cleanup complete",
            extra={
                "total_stopped": len(stream_ids),
                "failures": len(failures),
            }
        )
