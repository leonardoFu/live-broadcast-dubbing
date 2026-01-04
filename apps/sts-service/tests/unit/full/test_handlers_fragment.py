"""Unit tests for fragment handlers in Full STS Service.

Tests fragment:data handler and fragment:processed emission as defined in spec 021.

These tests MUST FAIL until implementation is complete (TDD approach).
"""

import base64
from unittest.mock import AsyncMock, MagicMock

import pytest

# These imports will fail until implementation exists - this is expected (TDD)
# from sts_service.full.handlers.fragment import (
#     handle_fragment_data,
#     emit_fragment_processed,
# )
# from sts_service.full.models.fragment import FragmentData, FragmentResult
# from sts_service.full.models.asset import AssetStatus
# from sts_service.full.session import SessionStore


@pytest.fixture
def mock_sio():
    """Create a mock Socket.IO server."""
    sio = MagicMock()
    sio.emit = AsyncMock()
    return sio


@pytest.fixture
def session_store():
    """Create a fresh session store."""
    pytest.skip("SessionStore not yet implemented (T106)")


@pytest.fixture
def sample_audio_data():
    """Generate sample base64-encoded audio data."""
    # 6 seconds of silence at 48kHz, 1 channel, 16-bit PCM
    sample_rate = 48000
    duration_s = 6
    num_samples = sample_rate * duration_s
    # Each sample is 2 bytes (16-bit)
    audio_bytes = b"\x00\x00" * num_samples
    return base64.b64encode(audio_bytes).decode("utf-8")


@pytest.fixture
def mock_pipeline_coordinator():
    """Mock PipelineCoordinator for testing."""
    coordinator = MagicMock()
    coordinator.process_fragment = AsyncMock()
    return coordinator


class TestHandleFragmentData:
    """Tests for fragment:data handler (T095-T096)."""

    @pytest.mark.asyncio
    async def test_fragment_data_emits_immediate_ack(
        self, mock_sio, session_store, sample_audio_data
    ):
        """T095: fragment:data emits fragment:ack within <50ms with status='queued'."""
        pytest.skip("Handler not implemented yet - TDD failing test")
        # from sts_service.full.handlers.fragment import handle_fragment_data

        # Create active session
        session = await session_store.create("sid-1", "stream-1", "worker-1")
        session.state = "ready"

        payload = {
            "fragment_id": "frag-001",
            "stream_id": "stream-1",
            "sequence_number": 1,
            "audio_data": sample_audio_data,
            "duration_ms": 6000,
            "original_duration_ms": 6000,
            "timestamp_ms": 0,
            "format": "pcm_s16le",
            "sample_rate_hz": 48000,
            "channels": 1,
        }

        import time

        start_time = time.perf_counter()

        await handle_fragment_data(
            sio=mock_sio,
            sid="sid-1",
            data=payload,
            session_store=session_store,
        )

        latency_ms = (time.perf_counter() - start_time) * 1000

        # Should emit fragment:ack immediately
        ack_calls = [call for call in mock_sio.emit.call_args_list if call[0][0] == "fragment:ack"]
        assert len(ack_calls) == 1
        assert latency_ms < 50, f"fragment:ack took {latency_ms:.2f}ms (should be <50ms)"

        ack_payload = ack_calls[0][0][1]
        assert ack_payload["fragment_id"] == "frag-001"
        assert ack_payload["status"] == "queued"

    @pytest.mark.asyncio
    async def test_fragment_data_calls_pipeline(
        self, mock_sio, session_store, sample_audio_data, mock_pipeline_coordinator
    ):
        """T096: fragment:data calls PipelineCoordinator.process_fragment() with FragmentData."""
        pytest.skip("Handler not implemented yet - TDD failing test")
        # from sts_service.full.handlers.fragment import handle_fragment_data

        # Create active session with pipeline
        session = await session_store.create("sid-1", "stream-1", "worker-1")
        session.state = "ready"
        session.pipeline_coordinator = mock_pipeline_coordinator

        payload = {
            "fragment_id": "frag-001",
            "stream_id": "stream-1",
            "sequence_number": 1,
            "audio_data": sample_audio_data,
            "duration_ms": 6000,
            "original_duration_ms": 6000,
            "timestamp_ms": 0,
            "format": "pcm_s16le",
            "sample_rate_hz": 48000,
            "channels": 1,
        }

        await handle_fragment_data(
            sio=mock_sio,
            sid="sid-1",
            data=payload,
            session_store=session_store,
        )

        # Verify pipeline was called
        mock_pipeline_coordinator.process_fragment.assert_called_once()
        call_args = mock_pipeline_coordinator.process_fragment.call_args
        fragment_data = call_args[0][0]
        assert fragment_data.fragment_id == "frag-001"


class TestEmitFragmentProcessed:
    """Tests for fragment:processed emission (T097-T098)."""

    @pytest.mark.asyncio
    async def test_fragment_processed_emitted_on_success(self, mock_sio, session_store):
        """T097: On success, emit fragment:processed with status='success', dubbed_audio, transcript, translated_text."""
        pytest.skip("Handler not implemented yet - TDD failing test")
        # from sts_service.full.handlers.fragment import emit_fragment_processed
        # from sts_service.full.models.fragment import FragmentResult
        # from sts_service.full.models.asset import AssetStatus

        # Create session
        session = await session_store.create("sid-1", "stream-1", "worker-1")

        # Mock successful result
        fragment_result = MagicMock()
        fragment_result.fragment_id = "frag-001"
        fragment_result.stream_id = "stream-1"
        fragment_result.sequence_number = 1
        fragment_result.status = AssetStatus.SUCCESS
        fragment_result.dubbed_audio = base64.b64encode(b"fake_audio_data").decode("utf-8")
        fragment_result.transcript = MagicMock()
        fragment_result.transcript.text = "Hello, world!"
        fragment_result.translated_text = MagicMock()
        fragment_result.translated_text.text = "Hola, mundo!"
        fragment_result.processing_time_ms = 7200
        fragment_result.error = None

        await emit_fragment_processed(
            sio=mock_sio,
            sid="sid-1",
            fragment_result=fragment_result,
            session=session,
        )

        # Should emit fragment:processed
        processed_calls = [
            call for call in mock_sio.emit.call_args_list if call[0][0] == "fragment:processed"
        ]
        assert len(processed_calls) == 1

        processed_payload = processed_calls[0][0][1]
        assert processed_payload["fragment_id"] == "frag-001"
        assert processed_payload["status"] == "success"
        assert "dubbed_audio" in processed_payload
        assert "transcript" in processed_payload
        assert processed_payload["transcript"]["text"] == "Hello, world!"
        assert "translated_text" in processed_payload
        assert processed_payload["translated_text"]["text"] == "Hola, mundo!"

    @pytest.mark.asyncio
    async def test_fragment_processed_emitted_on_failure(self, mock_sio, session_store):
        """T098: On failure, emit fragment:processed with status='failed', error.stage='asr', error.code='TIMEOUT'."""
        pytest.skip("Handler not implemented yet - TDD failing test")
        # from sts_service.full.handlers.fragment import emit_fragment_processed
        # from sts_service.full.models.fragment import FragmentResult
        # from sts_service.full.models.asset import AssetStatus
        # from sts_service.full.models.error import ProcessingError

        # Create session
        session = await session_store.create("sid-1", "stream-1", "worker-1")

        # Mock failed result (ASR timeout)
        fragment_result = MagicMock()
        fragment_result.fragment_id = "frag-002"
        fragment_result.stream_id = "stream-1"
        fragment_result.sequence_number = 2
        fragment_result.status = AssetStatus.FAILED
        fragment_result.error = MagicMock()
        fragment_result.error.stage = "asr"
        fragment_result.error.code = "TIMEOUT"
        fragment_result.error.message = "ASR processing timed out after 5000ms"
        fragment_result.error.retryable = True
        fragment_result.processing_time_ms = 5100

        await emit_fragment_processed(
            sio=mock_sio,
            sid="sid-1",
            fragment_result=fragment_result,
            session=session,
        )

        # Should emit fragment:processed with error
        processed_calls = [
            call for call in mock_sio.emit.call_args_list if call[0][0] == "fragment:processed"
        ]
        assert len(processed_calls) == 1

        processed_payload = processed_calls[0][0][1]
        assert processed_payload["fragment_id"] == "frag-002"
        assert processed_payload["status"] == "failed"
        assert "error" in processed_payload
        assert processed_payload["error"]["stage"] == "asr"
        assert processed_payload["error"]["code"] == "TIMEOUT"
        assert processed_payload["error"]["retryable"] is True
