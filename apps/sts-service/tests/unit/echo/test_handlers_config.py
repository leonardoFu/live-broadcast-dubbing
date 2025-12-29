"""Unit tests for config handlers in Echo STS Service.

Tests config:error_simulation handler.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest
from sts_service.echo.handlers.config import handle_config_error_simulation
from sts_service.echo.session import SessionStore


@pytest.fixture
def mock_sio():
    """Create a mock Socket.IO server."""
    sio = MagicMock()
    sio.emit = AsyncMock()
    return sio


@pytest.fixture
def session_store():
    """Create a fresh session store."""
    return SessionStore()


class TestConfigErrorSimulation:
    """Tests for config:error_simulation handler."""

    @pytest.mark.asyncio
    async def test_config_error_simulation_enable(self, mock_sio, session_store):
        """Simulation enabled via event."""
        session = await session_store.create("sid-1", "stream-1", "worker-1")
        session.transition_to("active")

        payload = {
            "enabled": True,
            "rules": [
                {
                    "trigger": "sequence_number",
                    "value": 5,
                    "error_code": "TIMEOUT",
                    "error_message": "Test timeout",
                    "retryable": True,
                }
            ],
        }

        await handle_config_error_simulation(mock_sio, "sid-1", payload, session_store)

        # Error simulation should be configured
        assert session.error_simulation is not None
        assert session.error_simulation.enabled is True
        assert len(session.error_simulation.rules) == 1

    @pytest.mark.asyncio
    async def test_config_error_simulation_ack(self, mock_sio, session_store):
        """Ack response with rules_count."""
        session = await session_store.create("sid-1", "stream-1", "worker-1")
        session.transition_to("active")

        payload = {
            "enabled": True,
            "rules": [
                {"trigger": "sequence_number", "value": 1, "error_code": "TIMEOUT"},
                {"trigger": "sequence_number", "value": 2, "error_code": "MODEL_ERROR"},
            ],
        }

        await handle_config_error_simulation(mock_sio, "sid-1", payload, session_store)

        # Should emit ack
        mock_sio.emit.assert_called_once()
        call = mock_sio.emit.call_args
        assert call[0][0] == "config:error_simulation:ack"

        ack = call[0][1]
        assert ack["status"] == "accepted"
        assert ack["rules_count"] == 2

    @pytest.mark.asyncio
    async def test_config_error_simulation_invalid(self, mock_sio, session_store):
        """Invalid config returns error status."""
        session = await session_store.create("sid-1", "stream-1", "worker-1")
        session.transition_to("active")

        # Invalid payload - missing required fields
        payload = {
            "enabled": True,
            "rules": [
                {
                    # Missing trigger and value
                    "error_code": "TIMEOUT",
                }
            ],
        }

        await handle_config_error_simulation(mock_sio, "sid-1", payload, session_store)

        # Should emit ack with rejected status
        mock_sio.emit.assert_called_once()
        call = mock_sio.emit.call_args
        ack = call[0][1]
        assert ack["status"] == "rejected"

    @pytest.mark.asyncio
    async def test_config_error_simulation_no_session(self, mock_sio, session_store):
        """Config for non-existent session returns error."""
        payload = {
            "enabled": True,
            "rules": [],
        }

        await handle_config_error_simulation(mock_sio, "sid-nonexistent", payload, session_store)

        # Should emit error
        mock_sio.emit.assert_called_once()
        call = mock_sio.emit.call_args
        assert call[0][0] == "error"
        assert call[0][1]["code"] == "STREAM_NOT_FOUND"

    @pytest.mark.asyncio
    async def test_config_error_simulation_disable(self, mock_sio, session_store):
        """Simulation can be disabled."""
        session = await session_store.create("sid-1", "stream-1", "worker-1")
        session.transition_to("active")

        # First enable
        await handle_config_error_simulation(
            mock_sio,
            "sid-1",
            {
                "enabled": True,
                "rules": [{"trigger": "sequence_number", "value": 0, "error_code": "TIMEOUT"}],
            },
            session_store,
        )

        # Then disable
        await handle_config_error_simulation(
            mock_sio,
            "sid-1",
            {"enabled": False, "rules": []},
            session_store,
        )

        assert session.error_simulation.enabled is False
