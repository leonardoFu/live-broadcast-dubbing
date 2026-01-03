"""
Integration tests for multi-fragment ordering in Pipeline.

Task ID: T088

These tests verify that the FragmentQueue correctly orders fragments
that complete out of sequence. This is critical for maintaining
proper A/V sync when processing happens in parallel.

Tests:
- Process 5 fragments submitted out of order (3,1,5,2,4)
- Validate results are emitted in correct order (1,2,3,4,5)
- Validate FragmentQueue handles blocking correctly
- Validate gap detection and handling

Requirements:
- faster-whisper package installed (for real ASR tests)
- Test audio fixtures available
"""

import asyncio
import base64
import random
import time
from pathlib import Path
from typing import Any, Callable
from unittest.mock import MagicMock

import pytest

from sts_service.full.fragment_queue import FragmentQueue
from sts_service.full.models.asset import AssetStatus, DurationMatchMetadata
from sts_service.full.models.fragment import (
    AudioData,
    FragmentData,
    FragmentMetadata,
    FragmentResult,
    ProcessingStatus,
    StageTiming,
)
from sts_service.full.models.stream import StreamConfig, StreamSession, StreamState
from sts_service.full.pipeline import PipelineCoordinator

from .conftest import requires_faster_whisper


class TestFragmentQueueOrdering:
    """Tests for FragmentQueue in-order delivery (T088)."""

    def test_queue_delivers_fragments_in_sequence_order(self):
        """Test that fragments are emitted in sequence order regardless of add order."""
        # Arrange
        queue = FragmentQueue(stream_id="test-stream", start_sequence=1)

        # Create fragments with sequence numbers 1-5
        fragments = []
        for seq in range(1, 6):
            result = FragmentResult(
                fragment_id=f"frag-{seq:03d}",
                stream_id="test-stream",
                sequence_number=seq,
                status=ProcessingStatus.SUCCESS,
                dubbed_audio=None,
                transcript=f"Transcript {seq}",
                translated_text=f"Translation {seq}",
                processing_time_ms=100,
                stage_timings=StageTiming(asr_ms=50, translation_ms=25, tts_ms=25),
            )
            fragments.append(result)

        # Add fragments out of order: 3, 1, 5, 2, 4
        out_of_order = [2, 0, 4, 1, 3]  # indices for seq 3,1,5,2,4
        for idx in out_of_order:
            queue.add_result(fragments[idx])

        # Act - Get all fragments in order
        ordered_results = []
        for _ in range(5):
            result = queue.try_get_next()
            if result:
                ordered_results.append(result)

        # Assert - Should be in sequence order 1,2,3,4,5
        assert len(ordered_results) == 5
        for i, result in enumerate(ordered_results):
            expected_seq = i + 1
            assert result.sequence_number == expected_seq, (
                f"Expected sequence {expected_seq}, got {result.sequence_number}"
            )

    def test_queue_blocks_until_expected_sequence_available(self):
        """Test that get_next_in_order blocks until expected sequence arrives."""
        queue = FragmentQueue(stream_id="test-stream", start_sequence=1)

        # Add sequence 3, but we expect 1 first
        result_3 = FragmentResult(
            fragment_id="frag-003",
            stream_id="test-stream",
            sequence_number=3,
            status=ProcessingStatus.SUCCESS,
            dubbed_audio=None,
            transcript="Transcript 3",
            translated_text="Translation 3",
            processing_time_ms=100,
            stage_timings=StageTiming(asr_ms=50, translation_ms=25, tts_ms=25),
        )
        queue.add_result(result_3)

        # try_get_next should return None (waiting for seq 1)
        assert queue.try_get_next() is None

        # Add sequence 1
        result_1 = FragmentResult(
            fragment_id="frag-001",
            stream_id="test-stream",
            sequence_number=1,
            status=ProcessingStatus.SUCCESS,
            dubbed_audio=None,
            transcript="Transcript 1",
            translated_text="Translation 1",
            processing_time_ms=100,
            stage_timings=StageTiming(asr_ms=50, translation_ms=25, tts_ms=25),
        )
        queue.add_result(result_1)

        # Now try_get_next should return seq 1
        got = queue.try_get_next()
        assert got is not None
        assert got.sequence_number == 1

        # Next expected is 2, but only 3 is in queue
        assert queue.try_get_next() is None

    @pytest.mark.asyncio
    async def test_queue_async_get_next_in_order(self):
        """Test async get_next_in_order waits for correct sequence."""
        queue = FragmentQueue(stream_id="test-stream", start_sequence=1)

        async def add_fragments_with_delay():
            """Add fragments after a short delay."""
            await asyncio.sleep(0.05)  # 50ms delay
            for seq in [2, 1, 3]:  # Add out of order
                result = FragmentResult(
                    fragment_id=f"frag-{seq:03d}",
                    stream_id="test-stream",
                    sequence_number=seq,
                    status=ProcessingStatus.SUCCESS,
                    dubbed_audio=None,
                    transcript=f"Transcript {seq}",
                    translated_text=f"Translation {seq}",
                    processing_time_ms=100,
                    stage_timings=StageTiming(asr_ms=50, translation_ms=25, tts_ms=25),
                )
                queue.add_result(result)
                await asyncio.sleep(0.01)  # 10ms between adds

        async def get_ordered_results():
            """Get results in order."""
            results = []
            for _ in range(3):
                result = await asyncio.wait_for(
                    queue.get_next_in_order(), timeout=1.0
                )
                results.append(result)
            return results

        # Run both concurrently
        _, results = await asyncio.gather(
            add_fragments_with_delay(),
            get_ordered_results(),
        )

        # Verify order
        assert len(results) == 3
        assert results[0].sequence_number == 1
        assert results[1].sequence_number == 2
        assert results[2].sequence_number == 3

    def test_queue_rejects_duplicate_sequence(self):
        """Test that duplicate sequence numbers are rejected."""
        queue = FragmentQueue(stream_id="test-stream", start_sequence=1)

        result_1 = FragmentResult(
            fragment_id="frag-001-original",
            stream_id="test-stream",
            sequence_number=1,
            status=ProcessingStatus.SUCCESS,
            dubbed_audio=None,
            transcript="Original",
            translated_text="Original",
            processing_time_ms=100,
            stage_timings=StageTiming(asr_ms=50, translation_ms=25, tts_ms=25),
        )

        result_1_dup = FragmentResult(
            fragment_id="frag-001-duplicate",
            stream_id="test-stream",
            sequence_number=1,
            status=ProcessingStatus.SUCCESS,
            dubbed_audio=None,
            transcript="Duplicate",
            translated_text="Duplicate",
            processing_time_ms=100,
            stage_timings=StageTiming(asr_ms=50, translation_ms=25, tts_ms=25),
        )

        # Add original - should return True
        assert queue.add_result(result_1) is True

        # Add duplicate - should return False
        assert queue.add_result(result_1_dup) is False

        # Get should return original
        got = queue.try_get_next()
        assert got is not None
        assert got.fragment_id == "frag-001-original"

    def test_queue_gap_info_reports_missing_sequences(self):
        """Test that gap_info correctly identifies missing sequences."""
        queue = FragmentQueue(stream_id="test-stream", start_sequence=1)

        # Add sequences 1, 3, 5 (missing 2 and 4)
        for seq in [1, 3, 5]:
            result = FragmentResult(
                fragment_id=f"frag-{seq:03d}",
                stream_id="test-stream",
                sequence_number=seq,
                status=ProcessingStatus.SUCCESS,
                dubbed_audio=None,
                transcript=f"Transcript {seq}",
                translated_text=f"Translation {seq}",
                processing_time_ms=100,
                stage_timings=StageTiming(asr_ms=50, translation_ms=25, tts_ms=25),
            )
            queue.add_result(result)

        # Check gap info
        gap_info = queue.get_gap_info()
        assert gap_info["expected"] == 1
        assert gap_info["available"] == [1, 3, 5]
        assert gap_info["missing"] == [2, 4]

        # Get sequence 1
        queue.try_get_next()

        # Gap info should update
        gap_info = queue.get_gap_info()
        assert gap_info["expected"] == 2
        assert gap_info["available"] == [3, 5]
        assert gap_info["missing"] == [2, 4]


class TestPipelineMultiFragmentOrdering:
    """Integration tests for pipeline with multiple fragments (T088)."""

    @pytest.fixture
    def mock_asr_component(self) -> MagicMock:
        """Create mock ASR with variable processing time."""
        mock = MagicMock()
        mock.component_name = "asr"
        mock.component_instance = "mock-asr-v1"
        mock.is_ready = True

        call_count = 0

        def transcribe_side_effect(*args: Any, **kwargs: Any) -> MagicMock:
            nonlocal call_count
            call_count += 1

            # Variable delay to simulate real processing
            time.sleep(random.uniform(0.01, 0.05))

            result = MagicMock()
            result.asset_id = f"asr-asset-{call_count:04d}"
            result.status = AssetStatus.SUCCESS
            result.transcript = f"Transcript for call {call_count}"
            result.total_text = f"Transcript for call {call_count}"
            result.segments = []
            result.confidence = 0.95
            result.latency_ms = 100
            result.error_message = None
            return result

        mock.transcribe.side_effect = transcribe_side_effect
        return mock

    @pytest.fixture
    def mock_translation_component(self) -> MagicMock:
        """Create mock translation."""
        mock = MagicMock()
        mock.component_name = "translate"
        mock.component_instance = "mock-translate-v1"
        mock.is_ready = True

        def translate_side_effect(
            source_text: str, *args: Any, **kwargs: Any
        ) -> MagicMock:
            result = MagicMock()
            result.asset_id = f"trans-{hash(source_text) % 10000:04d}"
            result.status = AssetStatus.SUCCESS
            result.translated_text = f"[ES] {source_text}"
            result.source_text = source_text
            result.error_message = None
            result.parent_asset_ids = kwargs.get("parent_asset_ids", [])
            return result

        mock.translate.side_effect = translate_side_effect
        return mock

    @pytest.fixture
    def mock_tts_component(self) -> MagicMock:
        """Create mock TTS."""
        mock = MagicMock()
        mock.component_name = "tts"
        mock.component_instance = "mock-tts-v1"
        mock.is_ready = True

        def synthesize_side_effect(
            text_asset: Any, target_duration_ms: int | None = None, **kwargs: Any
        ) -> MagicMock:
            duration_ms = target_duration_ms or 2000
            sample_rate = kwargs.get("output_sample_rate_hz", 16000)
            samples = int(sample_rate * duration_ms / 1000)

            result = MagicMock()
            result.asset_id = "audio-mock"
            result.status = AssetStatus.SUCCESS
            result.audio_bytes = b"\x00\x00" * samples
            result.format = "pcm_s16le"
            result.sample_rate_hz = sample_rate
            result.channels = 1
            result.duration_ms = duration_ms
            result.duration_metadata = DurationMatchMetadata(
                original_duration_ms=duration_ms,
                raw_duration_ms=duration_ms,
                final_duration_ms=duration_ms,
                duration_variance_percent=0.0,
                speed_ratio=1.0,
                speed_clamped=False,
            )
            result.error_message = None
            result.parent_asset_ids = []
            return result

        mock.synthesize.side_effect = synthesize_side_effect
        return mock

    @pytest.fixture
    def sample_stream_session(self) -> StreamSession:
        """Create sample stream session."""
        return StreamSession(
            stream_id="stream-multi-test",
            session_id="session-multi-001",
            worker_id="worker-test",
            socket_id="sid-multi-12345",
            config=StreamConfig(
                source_language="en",
                target_language="es",
                voice_profile="default",
                chunk_duration_ms=2000,
                sample_rate_hz=16000,
                channels=1,
                format="pcm_s16le",
            ),
            state=StreamState.READY,
            max_inflight=5,
        )

    def create_fragment(self, sequence_number: int) -> FragmentData:
        """Create a fragment with given sequence number."""
        # Generate simple audio data
        sample_rate = 16000
        duration_ms = 2000
        samples = int(sample_rate * duration_ms / 1000)
        audio_bytes = b"\x00\x00" * samples
        audio_b64 = base64.b64encode(audio_bytes).decode("utf-8")

        return FragmentData(
            fragment_id=f"frag-{sequence_number:03d}",
            stream_id="stream-multi-test",
            sequence_number=sequence_number,
            timestamp=1704067200000 + (sequence_number * duration_ms),
            audio=AudioData(
                format="pcm_s16le",
                sample_rate_hz=sample_rate,
                channels=1,
                duration_ms=duration_ms,
                data_base64=audio_b64,
            ),
            metadata=FragmentMetadata(pts_ns=sequence_number * duration_ms * 1_000_000),
        )

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_pipeline_processes_out_of_order_fragments(
        self,
        sample_stream_session: StreamSession,
        mock_asr_component: MagicMock,
        mock_translation_component: MagicMock,
        mock_tts_component: MagicMock,
    ):
        """Test pipeline processes fragments submitted out of order.

        Submit: 3, 1, 5, 2, 4
        Validate: All fragments processed successfully
        """
        # Arrange
        coordinator = PipelineCoordinator(
            asr=mock_asr_component,
            translation=mock_translation_component,
            tts=mock_tts_component,
        )

        # Create fragments for sequences 1-5
        fragments = {seq: self.create_fragment(seq) for seq in range(1, 6)}

        # Process out of order: 3, 1, 5, 2, 4
        out_of_order = [3, 1, 5, 2, 4]
        results: dict[int, FragmentResult] = {}

        for seq in out_of_order:
            result = await coordinator.process_fragment(
                fragment_data=fragments[seq],
                session=sample_stream_session,
            )
            results[seq] = result

        # Assert - All should succeed
        for seq in range(1, 6):
            assert results[seq].status == ProcessingStatus.SUCCESS, (
                f"Fragment {seq} failed: {results[seq].error}"
            )
            assert results[seq].sequence_number == seq

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_fragment_queue_emits_in_correct_order(
        self,
        sample_stream_session: StreamSession,
        mock_asr_component: MagicMock,
        mock_translation_component: MagicMock,
        mock_tts_component: MagicMock,
    ):
        """Test FragmentQueue emits results in correct sequence order.

        Process: 3, 1, 5, 2, 4
        Emit order: 1, 2, 3, 4, 5
        """
        # Arrange
        coordinator = PipelineCoordinator(
            asr=mock_asr_component,
            translation=mock_translation_component,
            tts=mock_tts_component,
        )

        queue = FragmentQueue(stream_id="stream-multi-test", start_sequence=1)

        # Create and process fragments out of order
        fragments = {seq: self.create_fragment(seq) for seq in range(1, 6)}
        out_of_order = [3, 1, 5, 2, 4]

        # Process all fragments and add to queue
        for seq in out_of_order:
            result = await coordinator.process_fragment(
                fragment_data=fragments[seq],
                session=sample_stream_session,
            )
            queue.add_result(result)

        # Act - Get results in order from queue
        ordered_results = []
        for _ in range(5):
            result = queue.try_get_next()
            if result:
                ordered_results.append(result)

        # Assert - Results should be in sequence order 1,2,3,4,5
        assert len(ordered_results) == 5
        for i, result in enumerate(ordered_results):
            expected_seq = i + 1
            assert result.sequence_number == expected_seq, (
                f"Position {i}: expected seq {expected_seq}, got {result.sequence_number}"
            )

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_concurrent_fragment_processing_with_ordering(
        self,
        sample_stream_session: StreamSession,
        mock_asr_component: MagicMock,
        mock_translation_component: MagicMock,
        mock_tts_component: MagicMock,
    ):
        """Test concurrent fragment processing maintains correct ordering.

        Process 5 fragments concurrently, verify ordered emission.
        """
        # Arrange
        coordinator = PipelineCoordinator(
            asr=mock_asr_component,
            translation=mock_translation_component,
            tts=mock_tts_component,
        )

        queue = FragmentQueue(stream_id="stream-multi-test", start_sequence=1)
        fragments = {seq: self.create_fragment(seq) for seq in range(1, 6)}

        async def process_and_queue(seq: int) -> None:
            """Process fragment and add to queue."""
            result = await coordinator.process_fragment(
                fragment_data=fragments[seq],
                session=sample_stream_session,
            )
            queue.add_result(result)

        # Act - Process all fragments concurrently
        tasks = [process_and_queue(seq) for seq in [3, 1, 5, 2, 4]]
        await asyncio.gather(*tasks)

        # Get results in order
        ordered_results = []
        for _ in range(5):
            result = queue.try_get_next()
            if result:
                ordered_results.append(result)

        # Assert - Should be in order despite concurrent processing
        assert len(ordered_results) == 5
        for i, result in enumerate(ordered_results):
            expected_seq = i + 1
            assert result.sequence_number == expected_seq

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_async_ordered_emission_with_delays(
        self,
        sample_stream_session: StreamSession,
        mock_asr_component: MagicMock,
        mock_translation_component: MagicMock,
        mock_tts_component: MagicMock,
    ):
        """Test async get_next_in_order waits for correct sequence."""
        # Arrange
        coordinator = PipelineCoordinator(
            asr=mock_asr_component,
            translation=mock_translation_component,
            tts=mock_tts_component,
        )

        queue = FragmentQueue(stream_id="stream-multi-test", start_sequence=1)
        fragments = {seq: self.create_fragment(seq) for seq in range(1, 4)}

        async def process_with_delay(seq: int, delay: float) -> None:
            """Process fragment after delay."""
            await asyncio.sleep(delay)
            result = await coordinator.process_fragment(
                fragment_data=fragments[seq],
                session=sample_stream_session,
            )
            queue.add_result(result)

        async def get_ordered_results() -> list[FragmentResult]:
            """Get results in order using async method."""
            results = []
            for _ in range(3):
                result = await asyncio.wait_for(
                    queue.get_next_in_order(), timeout=2.0
                )
                results.append(result)
            return results

        # Act - Process in order 3, 2, 1 with delays (seq 1 arrives last)
        # but they should be emitted in order 1, 2, 3
        tasks = [
            process_with_delay(3, 0.01),  # seq 3 arrives first
            process_with_delay(2, 0.05),  # seq 2 arrives second
            process_with_delay(1, 0.10),  # seq 1 arrives last
            get_ordered_results(),
        ]

        results_list = await asyncio.gather(*tasks)
        ordered_results = results_list[-1]  # Last result is from get_ordered_results

        # Assert - Despite arrival order 3,2,1, emission should be 1,2,3
        assert len(ordered_results) == 3
        assert ordered_results[0].sequence_number == 1
        assert ordered_results[1].sequence_number == 2
        assert ordered_results[2].sequence_number == 3


class TestFragmentQueueEdgeCases:
    """Edge case tests for FragmentQueue."""

    def test_queue_handles_single_fragment(self):
        """Test queue with only one fragment."""
        queue = FragmentQueue(stream_id="test-stream", start_sequence=1)

        result = FragmentResult(
            fragment_id="frag-001",
            stream_id="test-stream",
            sequence_number=1,
            status=ProcessingStatus.SUCCESS,
            dubbed_audio=None,
            transcript="Single",
            translated_text="Unico",
            processing_time_ms=100,
            stage_timings=StageTiming(asr_ms=50, translation_ms=25, tts_ms=25),
        )

        queue.add_result(result)

        got = queue.try_get_next()
        assert got is not None
        assert got.sequence_number == 1

        # Queue should be empty now
        assert queue.try_get_next() is None
        assert queue.is_complete

    def test_queue_handles_large_gap(self):
        """Test queue handles large gaps in sequence numbers."""
        queue = FragmentQueue(stream_id="test-stream", start_sequence=1)

        # Add sequence 100 (large gap from 1)
        result_100 = FragmentResult(
            fragment_id="frag-100",
            stream_id="test-stream",
            sequence_number=100,
            status=ProcessingStatus.SUCCESS,
            dubbed_audio=None,
            transcript="Fragment 100",
            translated_text="Fragmento 100",
            processing_time_ms=100,
            stage_timings=StageTiming(asr_ms=50, translation_ms=25, tts_ms=25),
        )
        queue.add_result(result_100)

        # Should block waiting for 1
        assert queue.try_get_next() is None

        # Gap info should show 99 missing
        gap_info = queue.get_gap_info()
        assert len(gap_info["missing"]) == 99  # 1-99 missing

    def test_queue_clear_resets_state(self):
        """Test that clear() properly resets queue state."""
        queue = FragmentQueue(stream_id="test-stream", start_sequence=1)

        # Add some fragments
        for seq in [1, 2, 3]:
            result = FragmentResult(
                fragment_id=f"frag-{seq:03d}",
                stream_id="test-stream",
                sequence_number=seq,
                status=ProcessingStatus.SUCCESS,
                dubbed_audio=None,
                transcript=f"Fragment {seq}",
                translated_text=f"Fragmento {seq}",
                processing_time_ms=100,
                stage_timings=StageTiming(asr_ms=50, translation_ms=25, tts_ms=25),
            )
            queue.add_result(result)

        # Get one
        queue.try_get_next()
        assert queue.next_expected_sequence == 2

        # Clear
        queue.clear()

        # State should be reset
        assert queue.next_expected_sequence == 0
        assert queue.pending_count == 0
        assert queue.is_complete

    def test_queue_with_failed_fragments(self):
        """Test queue handles failed fragments correctly."""
        queue = FragmentQueue(stream_id="test-stream", start_sequence=1)

        # Add success, failed, success
        results = [
            FragmentResult(
                fragment_id="frag-001",
                stream_id="test-stream",
                sequence_number=1,
                status=ProcessingStatus.SUCCESS,
                dubbed_audio=None,
                transcript="Success 1",
                translated_text="Exito 1",
                processing_time_ms=100,
                stage_timings=StageTiming(asr_ms=50, translation_ms=25, tts_ms=25),
            ),
            FragmentResult(
                fragment_id="frag-002",
                stream_id="test-stream",
                sequence_number=2,
                status=ProcessingStatus.FAILED,
                dubbed_audio=None,
                transcript=None,
                translated_text=None,
                processing_time_ms=100,
                stage_timings=StageTiming(asr_ms=50, translation_ms=0, tts_ms=0),
            ),
            FragmentResult(
                fragment_id="frag-003",
                stream_id="test-stream",
                sequence_number=3,
                status=ProcessingStatus.SUCCESS,
                dubbed_audio=None,
                transcript="Success 3",
                translated_text="Exito 3",
                processing_time_ms=100,
                stage_timings=StageTiming(asr_ms=50, translation_ms=25, tts_ms=25),
            ),
        ]

        for result in results:
            queue.add_result(result)

        # All should be emitted in order, including failed
        for expected_seq in [1, 2, 3]:
            got = queue.try_get_next()
            assert got is not None
            assert got.sequence_number == expected_seq
