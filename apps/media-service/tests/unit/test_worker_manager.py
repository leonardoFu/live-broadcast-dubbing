"""
Unit tests for WorkerManager.

Tests worker lifecycle orchestration, idempotency, and registry management.
"""

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from media_service.orchestrator.worker_manager import WorkerManager
from media_service.worker.worker_runner import WorkerConfig


@pytest.fixture
def worker_config():
    """Create a test worker configuration."""
    return WorkerConfig(
        stream_id="test-stream",
        rtsp_url="rtsp://localhost:8554/live/test/in",
        rtmp_url="rtmp://localhost:1935/live/test/out",
        sts_url="http://localhost:8080",
        segment_dir=Path("/tmp/segments/test-stream"),
    )


@pytest.fixture
def manager():
    """Create a WorkerManager instance."""
    return WorkerManager()


class TestWorkerManagerInitialization:
    """Test WorkerManager initialization."""

    def test_manager_initializes_empty_registry(self, manager):
        """Manager starts with empty worker registry."""
        assert len(manager._workers) == 0
        assert len(manager._locks) == 0

    def test_manager_has_required_methods(self, manager):
        """Manager has required public methods."""
        assert hasattr(manager, "start_worker")
        assert hasattr(manager, "stop_worker")
        assert hasattr(manager, "get_worker")
        assert hasattr(manager, "cleanup_all")


class TestStartWorker:
    """Test worker creation and lifecycle."""

    @pytest.mark.asyncio
    async def test_start_worker_creates_new_worker(self, manager, worker_config):
        """Starting worker creates new WorkerRunner instance."""
        with patch("media_service.orchestrator.worker_manager.WorkerRunner") as mock_runner_class:
            mock_runner = AsyncMock()
            mock_runner_class.return_value = mock_runner

            await manager.start_worker("test-stream", worker_config)

            # Verify worker created with correct config
            mock_runner_class.assert_called_once_with(worker_config)
            mock_runner.start.assert_called_once()

            # Verify worker added to registry
            assert "test-stream" in manager._workers
            assert manager._workers["test-stream"] == mock_runner

    @pytest.mark.asyncio
    async def test_start_worker_is_idempotent(self, manager, worker_config):
        """Calling start_worker multiple times for same stream is idempotent."""
        with patch("media_service.orchestrator.worker_manager.WorkerRunner") as mock_runner_class:
            mock_runner = AsyncMock()
            mock_runner_class.return_value = mock_runner

            # Start same worker twice
            await manager.start_worker("test-stream", worker_config)
            await manager.start_worker("test-stream", worker_config)

            # Should only create worker once
            assert mock_runner_class.call_count == 1
            mock_runner.start.assert_called_once()

    @pytest.mark.asyncio
    async def test_start_worker_different_streams_creates_multiple(self, manager):
        """Starting workers for different streams creates multiple instances."""
        with patch("media_service.orchestrator.worker_manager.WorkerRunner") as mock_runner_class:
            mock_runner1 = AsyncMock()
            mock_runner2 = AsyncMock()
            mock_runner_class.side_effect = [mock_runner1, mock_runner2]

            config1 = WorkerConfig(
                stream_id="stream-1",
                rtsp_url="rtsp://localhost:8554/live/stream-1/in",
                rtmp_url="rtmp://localhost:1935/live/stream-1/out",
                sts_url="http://localhost:8080",
                segment_dir=Path("/tmp/segments/stream-1"),
            )
            config2 = WorkerConfig(
                stream_id="stream-2",
                rtsp_url="rtsp://localhost:8554/live/stream-2/in",
                rtmp_url="rtmp://localhost:1935/live/stream-2/out",
                sts_url="http://localhost:8080",
                segment_dir=Path("/tmp/segments/stream-2"),
            )

            await manager.start_worker("stream-1", config1)
            await manager.start_worker("stream-2", config2)

            # Both workers created
            assert len(manager._workers) == 2
            assert "stream-1" in manager._workers
            assert "stream-2" in manager._workers

    @pytest.mark.asyncio
    async def test_start_worker_handles_startup_failure(self, manager, worker_config):
        """Starting worker handles startup failures gracefully."""
        with patch("media_service.orchestrator.worker_manager.WorkerRunner") as mock_runner_class:
            mock_runner = AsyncMock()
            mock_runner.start.side_effect = RuntimeError("Connection failed")
            mock_runner_class.return_value = mock_runner

            with pytest.raises(RuntimeError, match="Connection failed"):
                await manager.start_worker("test-stream", worker_config)

            # Worker should NOT be in registry if startup failed
            assert "test-stream" not in manager._workers

    @pytest.mark.asyncio
    async def test_start_worker_thread_safe(self, manager, worker_config):
        """Concurrent start_worker calls are thread-safe (no race conditions)."""
        with patch("media_service.orchestrator.worker_manager.WorkerRunner") as mock_runner_class:
            mock_runner = AsyncMock()
            mock_runner_class.return_value = mock_runner

            # Simulate delay in worker startup
            async def delayed_start():
                await asyncio.sleep(0.01)

            mock_runner.start.side_effect = delayed_start

            # Start same worker concurrently
            results = await asyncio.gather(
                manager.start_worker("test-stream", worker_config),
                manager.start_worker("test-stream", worker_config),
                manager.start_worker("test-stream", worker_config),
            )

            # Should only create one worker despite concurrent calls
            assert mock_runner_class.call_count == 1
            assert len(manager._workers) == 1


class TestStopWorker:
    """Test worker shutdown and cleanup."""

    @pytest.mark.asyncio
    async def test_stop_worker_stops_and_removes(self, manager, worker_config):
        """Stopping worker calls stop() and removes from registry."""
        with patch("media_service.orchestrator.worker_manager.WorkerRunner") as mock_runner_class:
            mock_runner = AsyncMock()
            mock_runner_class.return_value = mock_runner

            # Start then stop
            await manager.start_worker("test-stream", worker_config)
            await manager.stop_worker("test-stream")

            # Verify worker stopped and removed
            mock_runner.stop.assert_called_once()
            assert "test-stream" not in manager._workers

    @pytest.mark.asyncio
    async def test_stop_worker_nonexistent_is_noop(self, manager):
        """Stopping nonexistent worker is a no-op (doesn't raise error)."""
        # Should not raise
        await manager.stop_worker("nonexistent-stream")

    @pytest.mark.asyncio
    async def test_stop_worker_handles_stop_failure(self, manager, worker_config):
        """Stopping worker handles stop failures gracefully."""
        with patch("media_service.orchestrator.worker_manager.WorkerRunner") as mock_runner_class:
            mock_runner = AsyncMock()
            mock_runner.stop.side_effect = RuntimeError("Cleanup failed")
            mock_runner_class.return_value = mock_runner

            await manager.start_worker("test-stream", worker_config)

            # Stop should not raise even if worker.stop() fails
            await manager.stop_worker("test-stream")

            # Worker should still be removed from registry
            assert "test-stream" not in manager._workers


class TestGetWorker:
    """Test worker retrieval."""

    @pytest.mark.asyncio
    async def test_get_worker_returns_existing(self, manager, worker_config):
        """Getting worker returns existing instance."""
        with patch("media_service.orchestrator.worker_manager.WorkerRunner") as mock_runner_class:
            mock_runner = AsyncMock()
            mock_runner_class.return_value = mock_runner

            await manager.start_worker("test-stream", worker_config)
            result = manager.get_worker("test-stream")

            assert result == mock_runner

    def test_get_worker_returns_none_if_not_exists(self, manager):
        """Getting nonexistent worker returns None."""
        result = manager.get_worker("nonexistent-stream")
        assert result is None


class TestCleanupAll:
    """Test cleanup of all workers."""

    @pytest.mark.asyncio
    async def test_cleanup_all_stops_all_workers(self, manager):
        """Cleanup all stops all active workers."""
        with patch("media_service.orchestrator.worker_manager.WorkerRunner") as mock_runner_class:
            mock_runner1 = AsyncMock()
            mock_runner2 = AsyncMock()
            mock_runner_class.side_effect = [mock_runner1, mock_runner2]

            config1 = WorkerConfig(
                stream_id="stream-1",
                rtsp_url="rtsp://localhost:8554/live/stream-1/in",
                rtmp_url="rtmp://localhost:1935/live/stream-1/out",
                sts_url="http://localhost:8080",
                segment_dir=Path("/tmp/segments/stream-1"),
            )
            config2 = WorkerConfig(
                stream_id="stream-2",
                rtsp_url="rtsp://localhost:8554/live/stream-2/in",
                rtmp_url="rtmp://localhost:1935/live/stream-2/out",
                sts_url="http://localhost:8080",
                segment_dir=Path("/tmp/segments/stream-2"),
            )

            await manager.start_worker("stream-1", config1)
            await manager.start_worker("stream-2", config2)

            # Cleanup all
            await manager.cleanup_all()

            # Both workers stopped
            mock_runner1.stop.assert_called_once()
            mock_runner2.stop.assert_called_once()

            # Registry cleared
            assert len(manager._workers) == 0

    @pytest.mark.asyncio
    async def test_cleanup_all_handles_failures(self, manager):
        """Cleanup all continues even if some workers fail to stop."""
        with patch("media_service.orchestrator.worker_manager.WorkerRunner") as mock_runner_class:
            mock_runner1 = AsyncMock()
            mock_runner2 = AsyncMock()
            mock_runner1.stop.side_effect = RuntimeError("Stop failed")
            mock_runner_class.side_effect = [mock_runner1, mock_runner2]

            config1 = WorkerConfig(
                stream_id="stream-1",
                rtsp_url="rtsp://localhost:8554/live/stream-1/in",
                rtmp_url="rtmp://localhost:1935/live/stream-1/out",
                sts_url="http://localhost:8080",
                segment_dir=Path("/tmp/segments/stream-1"),
            )
            config2 = WorkerConfig(
                stream_id="stream-2",
                rtsp_url="rtsp://localhost:8554/live/stream-2/in",
                rtmp_url="rtmp://localhost:1935/live/stream-2/out",
                sts_url="http://localhost:8080",
                segment_dir=Path("/tmp/segments/stream-2"),
            )

            await manager.start_worker("stream-1", config1)
            await manager.start_worker("stream-2", config2)

            # Should not raise even if one worker fails
            await manager.cleanup_all()

            # Both stop() called
            mock_runner1.stop.assert_called_once()
            mock_runner2.stop.assert_called_once()

            # Registry still cleared
            assert len(manager._workers) == 0

    @pytest.mark.asyncio
    async def test_cleanup_all_empty_registry_is_noop(self, manager):
        """Cleanup all with empty registry is a no-op."""
        # Should not raise
        await manager.cleanup_all()
        assert len(manager._workers) == 0
