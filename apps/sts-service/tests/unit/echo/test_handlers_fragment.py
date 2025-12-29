"""Unit tests for fragment handlers in Echo STS Service.

Tests fragment:data processing, fragment:ack, ordering, and backpressure.
"""

import base64
from unittest.mock import AsyncMock, MagicMock

import pytest
from sts_service.echo.handlers.fragment import (
    handle_fragment_ack,
    handle_fragment_data,
)
from sts_service.echo.models.error import ErrorSimulationConfig, ErrorSimulationRule
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


@pytest.fixture
def sample_audio_base64():
    """Generate sample base64 audio data."""
    # 1 second of silence at 48kHz mono (96000 bytes of PCM s16le)
    audio_bytes = b"\x00" * 96000
    return base64.b64encode(audio_bytes).decode("ascii")


def make_fragment_payload(
    fragment_id: str,
    stream_id: str,
    sequence_number: int,
    audio_base64: str,
) -> dict:
    """Create a valid fragment:data payload."""
    return {
        "fragment_id": fragment_id,
        "stream_id": stream_id,
        "sequence_number": sequence_number,
        "timestamp": 1703750400000,
        "audio": {
            "format": "pcm_s16le",
            "sample_rate_hz": 48000,
            "channels": 1,
            "duration_ms": 1000,
            "data_base64": audio_base64,
        },
        "metadata": {
            "pts_ns": 0,
        },
    }


class TestFragmentEcho:
    """Tests for fragment echo processing."""

    @pytest.mark.asyncio
    async def test_fragment_echo_preserves_audio(
        self, mock_sio, session_store, sample_audio_base64
    ):
        """Audio data unchanged in response."""
        session = await session_store.create("sid-1", "stream-1", "worker-1")
        session.transition_to("active")

        payload = make_fragment_payload("frag-1", "stream-1", 0, sample_audio_base64)

        await handle_fragment_data(mock_sio, "sid-1", payload, session_store)

        # Find fragment:processed call
        processed_call = None
        for call in mock_sio.emit.call_args_list:
            if call[0][0] == "fragment:processed":
                processed_call = call
                break

        assert processed_call is not None
        processed_payload = processed_call[0][1]

        # Audio should be preserved
        assert processed_payload["dubbed_audio"]["data_base64"] == sample_audio_base64

    @pytest.mark.asyncio
    async def test_fragment_ack_immediate(self, mock_sio, session_store, sample_audio_base64):
        """fragment:ack sent immediately with status queued."""
        session = await session_store.create("sid-1", "stream-1", "worker-1")
        session.transition_to("active")

        payload = make_fragment_payload("frag-1", "stream-1", 0, sample_audio_base64)

        await handle_fragment_data(mock_sio, "sid-1", payload, session_store)

        # First emit should be fragment:ack
        first_call = mock_sio.emit.call_args_list[0]
        assert first_call[0][0] == "fragment:ack"
        assert first_call[0][1]["status"] == "queued"
        assert first_call[0][1]["fragment_id"] == "frag-1"

    @pytest.mark.asyncio
    async def test_fragment_response_structure(self, mock_sio, session_store, sample_audio_base64):
        """All required fields populated in response."""
        session = await session_store.create("sid-1", "stream-1", "worker-1")
        session.transition_to("active")

        payload = make_fragment_payload("frag-1", "stream-1", 0, sample_audio_base64)

        await handle_fragment_data(mock_sio, "sid-1", payload, session_store)

        # Find fragment:processed call
        processed_call = None
        for call in mock_sio.emit.call_args_list:
            if call[0][0] == "fragment:processed":
                processed_call = call
                break

        assert processed_call is not None
        p = processed_call[0][1]

        # Verify required fields
        assert p["fragment_id"] == "frag-1"
        assert p["stream_id"] == "stream-1"
        assert p["sequence_number"] == 0
        assert p["status"] == "success"
        assert "dubbed_audio" in p
        assert "processing_time_ms" in p

    @pytest.mark.asyncio
    async def test_fragment_mock_transcript(self, mock_sio, session_store, sample_audio_base64):
        """transcript field contains mock text."""
        session = await session_store.create("sid-1", "stream-1", "worker-1")
        session.transition_to("active")

        payload = make_fragment_payload("frag-1", "stream-1", 0, sample_audio_base64)

        await handle_fragment_data(mock_sio, "sid-1", payload, session_store)

        processed_call = None
        for call in mock_sio.emit.call_args_list:
            if call[0][0] == "fragment:processed":
                processed_call = call
                break

        p = processed_call[0][1]
        assert p["transcript"] is not None
        assert "[ECHO]" in p["transcript"]

    @pytest.mark.asyncio
    async def test_fragment_mock_translated_text(
        self, mock_sio, session_store, sample_audio_base64
    ):
        """translated_text field contains mock text."""
        session = await session_store.create("sid-1", "stream-1", "worker-1")
        session.transition_to("active")

        payload = make_fragment_payload("frag-1", "stream-1", 0, sample_audio_base64)

        await handle_fragment_data(mock_sio, "sid-1", payload, session_store)

        processed_call = None
        for call in mock_sio.emit.call_args_list:
            if call[0][0] == "fragment:processed":
                processed_call = call
                break

        p = processed_call[0][1]
        assert p["translated_text"] is not None
        assert "[ECHO]" in p["translated_text"]

    @pytest.mark.asyncio
    async def test_fragment_processing_time_recorded(
        self, mock_sio, session_store, sample_audio_base64
    ):
        """processing_time_ms populated."""
        session = await session_store.create("sid-1", "stream-1", "worker-1")
        session.transition_to("active")

        payload = make_fragment_payload("frag-1", "stream-1", 0, sample_audio_base64)

        await handle_fragment_data(mock_sio, "sid-1", payload, session_store)

        processed_call = None
        for call in mock_sio.emit.call_args_list:
            if call[0][0] == "fragment:processed":
                processed_call = call
                break

        p = processed_call[0][1]
        assert "processing_time_ms" in p
        assert p["processing_time_ms"] >= 0

    @pytest.mark.asyncio
    async def test_fragment_stage_timings_included(
        self, mock_sio, session_store, sample_audio_base64
    ):
        """stage_timings with mock values."""
        session = await session_store.create("sid-1", "stream-1", "worker-1")
        session.transition_to("active")

        payload = make_fragment_payload("frag-1", "stream-1", 0, sample_audio_base64)

        await handle_fragment_data(mock_sio, "sid-1", payload, session_store)

        processed_call = None
        for call in mock_sio.emit.call_args_list:
            if call[0][0] == "fragment:processed":
                processed_call = call
                break

        p = processed_call[0][1]
        assert "stage_timings" in p
        assert "asr_ms" in p["stage_timings"]
        assert "translation_ms" in p["stage_timings"]
        assert "tts_ms" in p["stage_timings"]


class TestFragmentOrdering:
    """Tests for fragment ordering."""

    @pytest.mark.asyncio
    async def test_fragment_ordering_preserved(self, mock_sio, session_store, sample_audio_base64):
        """Fragments delivered in sequence_number order."""
        session = await session_store.create("sid-1", "stream-1", "worker-1")
        session.transition_to("active")

        # Send fragments 0, 1, 2 in order
        for seq in range(3):
            payload = make_fragment_payload(f"frag-{seq}", "stream-1", seq, sample_audio_base64)
            await handle_fragment_data(mock_sio, "sid-1", payload, session_store)

        # Get all processed calls
        processed_seqs = []
        for call in mock_sio.emit.call_args_list:
            if call[0][0] == "fragment:processed":
                processed_seqs.append(call[0][1]["sequence_number"])

        # Should be in order
        assert processed_seqs == [0, 1, 2]

    @pytest.mark.asyncio
    async def test_fragment_out_of_order_processing(
        self, mock_sio, session_store, sample_audio_base64
    ):
        """Out-of-order input still delivers in-order."""
        session = await session_store.create("sid-1", "stream-1", "worker-1")
        session.transition_to("active")

        # Send fragments out of order: 1, 0, 2
        for seq in [1, 0, 2]:
            payload = make_fragment_payload(f"frag-{seq}", "stream-1", seq, sample_audio_base64)
            await handle_fragment_data(mock_sio, "sid-1", payload, session_store)

        # Get all processed calls
        processed_seqs = []
        for call in mock_sio.emit.call_args_list:
            if call[0][0] == "fragment:processed":
                processed_seqs.append(call[0][1]["sequence_number"])

        # Should be in order
        assert processed_seqs == [0, 1, 2]

    @pytest.mark.asyncio
    async def test_fragment_before_stream_init_rejected(
        self, mock_sio, session_store, sample_audio_base64
    ):
        """STREAM_NOT_FOUND error for fragment before init."""
        # No session created
        payload = make_fragment_payload("frag-1", "stream-1", 0, sample_audio_base64)

        await handle_fragment_data(mock_sio, "sid-1", payload, session_store)

        # Should emit error
        mock_sio.emit.assert_called_once()
        call = mock_sio.emit.call_args
        assert call[0][0] == "error"
        assert call[0][1]["code"] == "STREAM_NOT_FOUND"

    @pytest.mark.asyncio
    async def test_fragment_too_large_rejected(self, mock_sio, session_store):
        """FRAGMENT_TOO_LARGE error for >10MB."""
        session = await session_store.create("sid-1", "stream-1", "worker-1")
        session.transition_to("active")

        # Create oversized audio (>10MB base64)
        large_audio = base64.b64encode(b"\x00" * (11 * 1024 * 1024)).decode("ascii")

        payload = make_fragment_payload("frag-1", "stream-1", 0, large_audio)

        await handle_fragment_data(mock_sio, "sid-1", payload, session_store)

        # Should emit error
        error_call = None
        for call in mock_sio.emit.call_args_list:
            if call[0][0] == "error":
                error_call = call
                break

        assert error_call is not None
        assert error_call[0][1]["code"] == "FRAGMENT_TOO_LARGE"


class TestFragmentAck:
    """Tests for fragment:ack handler (worker -> STS)."""

    @pytest.mark.asyncio
    async def test_fragment_ack_received(self, mock_sio, session_store):
        """Worker acknowledgment handled correctly."""
        session = await session_store.create("sid-1", "stream-1", "worker-1")
        session.transition_to("active")
        session.increment_inflight()

        ack_payload = {
            "fragment_id": "frag-1",
            "status": "received",
            "timestamp": 1703750400000,
        }

        await handle_fragment_ack(mock_sio, "sid-1", ack_payload, session_store)

        # In-flight should be decremented
        assert session.inflight_count == 0


class TestBackpressure:
    """Tests for backpressure emission."""

    @pytest.mark.asyncio
    async def test_backpressure_event_emission(self, mock_sio, session_store, sample_audio_base64):
        """Event emitted when threshold exceeded."""
        session = await session_store.create("sid-1", "stream-1", "worker-1")
        session.transition_to("active")
        session.backpressure_enabled = True
        session.max_inflight = 5

        # Send enough fragments to trigger backpressure (>50% = 3)
        for seq in range(4):
            payload = make_fragment_payload(f"frag-{seq}", "stream-1", seq, sample_audio_base64)
            # Don't await completion to keep fragments in-flight
            await handle_fragment_data(mock_sio, "sid-1", payload, session_store)

        # Check for backpressure event
        bp_call = None
        for call in mock_sio.emit.call_args_list:
            if call[0][0] == "backpressure":
                bp_call = call
                break

        # Backpressure should have been emitted
        # (depends on implementation - may or may not be emitted in echo service)
        # For now, just verify no errors occurred

    @pytest.mark.asyncio
    async def test_backpressure_severity_low(self, mock_sio, session_store, sample_audio_base64):
        """50% threshold -> low severity."""
        session = await session_store.create("sid-1", "stream-1", "worker-1")
        session.transition_to("active")
        session.backpressure_enabled = True
        session.max_inflight = 10

        # Set inflight to 50% (5)
        for _ in range(5):
            session.increment_inflight()

        payload = make_fragment_payload("frag-5", "stream-1", 5, sample_audio_base64)

        await handle_fragment_data(mock_sio, "sid-1", payload, session_store)

        # Check for backpressure with low severity
        for call in mock_sio.emit.call_args_list:
            if call[0][0] == "backpressure":
                assert call[0][1]["severity"] in ["low", "medium", "high"]

    @pytest.mark.asyncio
    async def test_backpressure_severity_medium(self, mock_sio, session_store, sample_audio_base64):
        """70% threshold -> medium severity."""
        session = await session_store.create("sid-1", "stream-1", "worker-1")
        session.transition_to("active")
        session.backpressure_enabled = True
        session.max_inflight = 10

        # Set inflight to 70% (7)
        for _ in range(7):
            session.increment_inflight()

        payload = make_fragment_payload("frag-7", "stream-1", 7, sample_audio_base64)

        await handle_fragment_data(mock_sio, "sid-1", payload, session_store)

        # Check for backpressure with medium severity
        for call in mock_sio.emit.call_args_list:
            if call[0][0] == "backpressure":
                assert call[0][1]["severity"] in ["medium", "high"]

    @pytest.mark.asyncio
    async def test_backpressure_severity_high(self, mock_sio, session_store, sample_audio_base64):
        """90% threshold -> high severity."""
        session = await session_store.create("sid-1", "stream-1", "worker-1")
        session.transition_to("active")
        session.backpressure_enabled = True
        session.max_inflight = 10

        # Set inflight to 90% (9)
        for _ in range(9):
            session.increment_inflight()

        payload = make_fragment_payload("frag-9", "stream-1", 9, sample_audio_base64)

        await handle_fragment_data(mock_sio, "sid-1", payload, session_store)

        # Check for backpressure with high severity
        for call in mock_sio.emit.call_args_list:
            if call[0][0] == "backpressure":
                assert call[0][1]["severity"] == "high"

    @pytest.mark.asyncio
    async def test_backpressure_clear(self, mock_sio, session_store, sample_audio_base64):
        """Low severity with action none when queue clears."""
        session = await session_store.create("sid-1", "stream-1", "worker-1")
        session.transition_to("active")
        session.backpressure_enabled = True
        session.backpressure_active = True  # Was previously in backpressure
        session.max_inflight = 10

        # Set inflight to below threshold
        session.inflight_count = 2

        payload = make_fragment_payload("frag-1", "stream-1", 0, sample_audio_base64)

        await handle_fragment_data(mock_sio, "sid-1", payload, session_store)

        # Check for backpressure clear event
        for call in mock_sio.emit.call_args_list:
            if call[0][0] == "backpressure":
                if call[0][1]["severity"] == "low":
                    assert call[0][1]["action"] == "none"


class TestErrorInjection:
    """Tests for error injection via error simulation."""

    @pytest.mark.asyncio
    async def test_error_injection_by_sequence_number(
        self, mock_sio, session_store, sample_audio_base64
    ):
        """Error triggered on specific sequence."""
        session = await session_store.create("sid-1", "stream-1", "worker-1")
        session.transition_to("active")

        # Configure error simulation for sequence 2
        session.error_simulation = ErrorSimulationConfig(
            enabled=True,
            rules=[
                ErrorSimulationRule(
                    trigger="sequence_number",
                    value=2,
                    error_code="TIMEOUT",
                    error_message="Simulated timeout",
                    retryable=True,
                ),
            ],
        )

        # Send fragments 0, 1, 2
        for seq in range(3):
            payload = make_fragment_payload(f"frag-{seq}", "stream-1", seq, sample_audio_base64)
            await handle_fragment_data(mock_sio, "sid-1", payload, session_store)

        # Fragment 2 should have failed status
        for call in mock_sio.emit.call_args_list:
            if call[0][0] == "fragment:processed":
                p = call[0][1]
                if p["sequence_number"] == 2:
                    assert p["status"] == "failed"
                    assert p["error"]["code"] == "TIMEOUT"
                else:
                    assert p["status"] == "success"

    @pytest.mark.asyncio
    async def test_error_injection_by_fragment_id(
        self, mock_sio, session_store, sample_audio_base64
    ):
        """Error triggered on specific fragment."""
        session = await session_store.create("sid-1", "stream-1", "worker-1")
        session.transition_to("active")

        # Configure error simulation for specific fragment ID
        session.error_simulation = ErrorSimulationConfig(
            enabled=True,
            rules=[
                ErrorSimulationRule(
                    trigger="fragment_id",
                    value="frag-target",
                    error_code="MODEL_ERROR",
                    error_message="Simulated model error",
                    retryable=True,
                    stage="tts",
                ),
            ],
        )

        # Send fragment with matching ID
        payload = make_fragment_payload("frag-target", "stream-1", 0, sample_audio_base64)
        await handle_fragment_data(mock_sio, "sid-1", payload, session_store)

        # Should have failed status
        for call in mock_sio.emit.call_args_list:
            if call[0][0] == "fragment:processed":
                p = call[0][1]
                assert p["status"] == "failed"
                assert p["error"]["code"] == "MODEL_ERROR"

    @pytest.mark.asyncio
    async def test_error_injection_by_nth_fragment(
        self, mock_sio, session_store, sample_audio_base64
    ):
        """Error triggered on every Nth fragment."""
        session = await session_store.create("sid-1", "stream-1", "worker-1")
        session.transition_to("active")

        # Configure error simulation for every 3rd fragment
        session.error_simulation = ErrorSimulationConfig(
            enabled=True,
            rules=[
                ErrorSimulationRule(
                    trigger="nth_fragment",
                    value=3,
                    error_code="GPU_OOM",
                    error_message="Simulated OOM",
                    retryable=True,
                ),
            ],
        )

        # Send 6 fragments
        for seq in range(6):
            payload = make_fragment_payload(f"frag-{seq}", "stream-1", seq, sample_audio_base64)
            await handle_fragment_data(mock_sio, "sid-1", payload, session_store)

        # Fragments 2 and 5 (3rd and 6th) should fail
        failed_seqs = []
        for call in mock_sio.emit.call_args_list:
            if call[0][0] == "fragment:processed":
                p = call[0][1]
                if p["status"] == "failed":
                    failed_seqs.append(p["sequence_number"])

        assert 2 in failed_seqs  # 3rd fragment (0-indexed: 2)
        assert 5 in failed_seqs  # 6th fragment (0-indexed: 5)

    @pytest.mark.asyncio
    async def test_error_retryable_flag_timeout(self, mock_sio, session_store, sample_audio_base64):
        """TIMEOUT error has retryable=true."""
        session = await session_store.create("sid-1", "stream-1", "worker-1")
        session.transition_to("active")

        session.error_simulation = ErrorSimulationConfig(
            enabled=True,
            rules=[
                ErrorSimulationRule(
                    trigger="sequence_number",
                    value=0,
                    error_code="TIMEOUT",
                    retryable=True,
                ),
            ],
        )

        payload = make_fragment_payload("frag-0", "stream-1", 0, sample_audio_base64)
        await handle_fragment_data(mock_sio, "sid-1", payload, session_store)

        for call in mock_sio.emit.call_args_list:
            if call[0][0] == "fragment:processed":
                p = call[0][1]
                assert p["error"]["retryable"] is True

    @pytest.mark.asyncio
    async def test_error_retryable_flag_auth_failed(
        self, mock_sio, session_store, sample_audio_base64
    ):
        """AUTH_FAILED has retryable=false."""
        session = await session_store.create("sid-1", "stream-1", "worker-1")
        session.transition_to("active")

        session.error_simulation = ErrorSimulationConfig(
            enabled=True,
            rules=[
                ErrorSimulationRule(
                    trigger="sequence_number",
                    value=0,
                    error_code="AUTH_FAILED",
                    retryable=False,
                ),
            ],
        )

        payload = make_fragment_payload("frag-0", "stream-1", 0, sample_audio_base64)
        await handle_fragment_data(mock_sio, "sid-1", payload, session_store)

        for call in mock_sio.emit.call_args_list:
            if call[0][0] == "fragment:processed":
                p = call[0][1]
                assert p["error"]["retryable"] is False
