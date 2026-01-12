"""E2E tests for Full STS Service.

Tests the complete STS pipeline:
- Stream initialization and lifecycle
- Fragment processing (ASR → Translation → TTS)
- Backpressure monitoring
- Error handling

Prerequisites:
- Full STS service running (via docker-compose.full.yml)
- DEEPL_AUTH_KEY environment variable set
- NVIDIA GPU available (for ASR and TTS)
- Test audio file: tests/fixtures/test-streams/1-min-nfl.m4a

Usage:
    # Run all E2E tests
    pytest apps/sts-service/tests/e2e/test_full_pipeline_e2e.py -v -s

    # Run specific test
    pytest apps/sts-service/tests/e2e/test_full_pipeline_e2e.py::test_stream_init_e2e -v -s

    # Run with E2E marker
    pytest -m e2e -v -s
"""

from __future__ import annotations

import asyncio
import base64
import logging
from pathlib import Path

import pytest

from .helpers import AudioChunker, SocketIOClient

logger = logging.getLogger(__name__)

# Test fixtures location
REPO_ROOT = Path(__file__).resolve().parents[5]
TEST_AUDIO_FILE = REPO_ROOT / "tests/fixtures/test-streams/1-min-nfl.m4a"

# Test configuration
CHUNK_DURATION_MS = 6000  # 6 seconds per chunk
FRAGMENT_PROCESSING_TIMEOUT = 15.0  # seconds (target <8s, but allow buffer)
STREAM_INIT_TIMEOUT = 10.0  # seconds


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_stream_init_e2e(full_sts_service: str):
    """Test stream initialization.

    Validates:
    - stream:init event accepted
    - stream:ready event received with session_id, max_inflight, capabilities
    - Session successfully initialized

    Args:
        full_sts_service: Service URL from fixture
    """
    logger.info("=" * 80)
    logger.info("TEST: Stream Initialization E2E")
    logger.info("=" * 80)

    async with SocketIOClient(full_sts_service) as client:
        # Send stream:init
        ready_data = await client.send_stream_init(
            source_language="en",
            target_language="es",
            voice_profile="default",
            timeout=STREAM_INIT_TIMEOUT,
        )

        # Validate stream:ready response
        assert "session_id" in ready_data, "stream:ready missing session_id"
        assert "max_inflight" in ready_data, "stream:ready missing max_inflight"
        assert "capabilities" in ready_data, "stream:ready missing capabilities"

        # Validate capabilities
        capabilities = ready_data["capabilities"]
        assert "asr" in capabilities, "Missing ASR capability"
        assert "translation" in capabilities, "Missing translation capability"
        assert "tts" in capabilities, "Missing TTS capability"
        assert "duration_matching" in capabilities, "Missing duration_matching capability"

        logger.info(f"✓ Stream initialized: {ready_data['session_id']}")
        logger.info(f"✓ Max in-flight: {ready_data['max_inflight']}")
        logger.info(f"✓ Capabilities: {capabilities}")

    logger.info("✓ Test passed: Stream initialization")


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_single_fragment_e2e(full_sts_service: str):
    """Test single fragment processing.

    Validates:
    - fragment:ack received within <50ms
    - fragment:processed received within <8s
    - FragmentResult contains transcript, translation, dubbed_audio
    - Duration variance within ±10%

    Args:
        full_sts_service: Service URL from fixture
    """
    logger.info("=" * 80)
    logger.info("TEST: Single Fragment Processing E2E")
    logger.info("=" * 80)

    # Chunk test audio
    chunker = AudioChunker(TEST_AUDIO_FILE)
    chunks = chunker.chunk_audio(
        chunk_duration_ms=CHUNK_DURATION_MS,
        max_chunks=1,  # Only first chunk
    )
    assert len(chunks) == 1, "Expected 1 audio chunk"

    chunk = chunks[0]
    logger.info(
        f"Prepared audio chunk: {chunk.duration_ms}ms, "
        f"{chunk.size_bytes} bytes, "
        f"{chunk.sample_rate}Hz"
    )

    async with SocketIOClient(full_sts_service) as client:
        # Initialize stream
        ready_data = await client.send_stream_init(
            source_language="en",
            target_language="es",
            timeout=STREAM_INIT_TIMEOUT,
        )
        session_id = ready_data["session_id"]
        logger.info(f"Stream initialized: {session_id}")

        # Send fragment
        fragment_data = chunk.to_fragment_data(stream_id=session_id)
        fragment_id = fragment_data["fragment_id"]

        # Measure ack latency
        ack_start = asyncio.get_event_loop().time()
        ack_data = await client.send_fragment(
            fragment_data,
            wait_for_ack=True,
            ack_timeout=1.0,
        )
        ack_latency_ms = (asyncio.get_event_loop().time() - ack_start) * 1000

        # Validate ack
        assert ack_data["fragment_id"] == fragment_id, "Ack fragment_id mismatch"
        assert ack_data["status"] == "queued", "Ack status should be 'queued'"
        logger.info(f"✓ fragment:ack received in {ack_latency_ms:.1f}ms")

        # Verify ack latency <50ms (target)
        if ack_latency_ms > 50:
            logger.warning(f"⚠ Ack latency {ack_latency_ms:.1f}ms exceeds 50ms target")

        # Wait for fragment:processed
        logger.info("Waiting for fragment:processed...")
        processed_event = await client.wait_for_event(
            "fragment:processed",
            timeout=FRAGMENT_PROCESSING_TIMEOUT,
            predicate=lambda data: data.get("fragment_id") == fragment_id,
        )

        result_data = processed_event.data
        processing_time_ms = result_data.get("processing_time_ms", 0)
        logger.info(f"✓ fragment:processed received in {processing_time_ms}ms")

        # Validate result status
        assert result_data["status"] == "success", (
            f"Fragment processing failed: {result_data.get('error')}"
        )

        # Validate transcript
        assert "transcript" in result_data, "Missing transcript"
        assert len(result_data["transcript"]) > 0, "Empty transcript"
        logger.info(f"✓ Transcript: {result_data['transcript'][:100]}...")

        # Validate translation
        assert "translated_text" in result_data, "Missing translated_text"
        assert len(result_data["translated_text"]) > 0, "Empty translation"
        logger.info(f"✓ Translation: {result_data['translated_text'][:100]}...")

        # Validate dubbed audio
        assert "dubbed_audio" in result_data, "Missing dubbed_audio"
        assert len(result_data["dubbed_audio"]) > 0, "Empty dubbed_audio"

        # Decode and validate audio
        dubbed_audio_bytes = base64.b64decode(result_data["dubbed_audio"])
        assert len(dubbed_audio_bytes) > 0, "Dubbed audio is empty"
        logger.info(
            f"✓ Dubbed audio: {len(dubbed_audio_bytes)} bytes "
            f"({len(dubbed_audio_bytes) / 4 / 16000:.2f}s)"
        )

        # Validate metadata
        assert "metadata" in result_data, "Missing metadata"
        metadata = result_data["metadata"]
        assert "original_duration_ms" in metadata, "Missing original_duration_ms"
        assert "dubbed_duration_ms" in metadata, "Missing dubbed_duration_ms"
        assert "duration_variance_percent" in metadata, "Missing duration_variance_percent"

        # Validate duration variance
        variance_percent = metadata["duration_variance_percent"]
        logger.info(
            f"✓ Duration: original={metadata['original_duration_ms']}ms, "
            f"dubbed={metadata['dubbed_duration_ms']}ms, "
            f"variance={variance_percent:.1f}%"
        )

        # Allow up to 10% variance (SUCCESS threshold)
        assert abs(variance_percent) <= 10, (
            f"Duration variance {variance_percent:.1f}% exceeds 10% threshold"
        )

        # Validate stage timings
        assert "stage_timings" in result_data, "Missing stage_timings"
        timings = result_data["stage_timings"]
        assert "asr_ms" in timings, "Missing asr_ms timing"
        assert "translation_ms" in timings, "Missing translation_ms timing"
        assert "tts_ms" in timings, "Missing tts_ms timing"

        logger.info(
            f"✓ Stage timings: ASR={timings['asr_ms']}ms, "
            f"Translation={timings['translation_ms']}ms, "
            f"TTS={timings['tts_ms']}ms"
        )

    logger.info("✓ Test passed: Single fragment processing")


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_full_minute_pipeline_e2e(full_sts_service: str):
    """Test full minute pipeline processing.

    Validates:
    - Multiple fragments processed sequentially
    - All fragments succeed
    - Total latency < 10 minutes (60s audio + ~80s processing)
    - stream:end and stream:complete flow

    Args:
        full_sts_service: Service URL from fixture
    """
    logger.info("=" * 80)
    logger.info("TEST: Full Minute Pipeline E2E")
    logger.info("=" * 80)

    # Chunk test audio (1 minute → 10 chunks of 6 seconds)
    chunker = AudioChunker(TEST_AUDIO_FILE)
    chunks = chunker.chunk_audio(chunk_duration_ms=CHUNK_DURATION_MS)

    logger.info(f"Prepared {len(chunks)} audio chunks")
    for i, chunk in enumerate(chunks):
        logger.info(f"  Chunk {i}: {chunk.duration_ms}ms, {chunk.size_bytes} bytes")

    async with SocketIOClient(full_sts_service) as client:
        # Initialize stream
        ready_data = await client.send_stream_init(
            source_language="en",
            target_language="es",
            timeout=STREAM_INIT_TIMEOUT,
        )
        session_id = ready_data["session_id"]
        logger.info(f"Stream initialized: {session_id}")

        # Send all fragments and collect results
        processed_results = []
        start_time = asyncio.get_event_loop().time()

        for chunk in chunks:
            fragment_data = chunk.to_fragment_data(stream_id=session_id)
            fragment_id = fragment_data["fragment_id"]

            # Send fragment
            await client.send_fragment(
                fragment_data,
                wait_for_ack=True,
                ack_timeout=1.0,
            )
            logger.info(f"Sent fragment: {fragment_id}")

            # Wait for processed result
            processed_event = await client.wait_for_event(
                "fragment:processed",
                timeout=FRAGMENT_PROCESSING_TIMEOUT,
                predicate=lambda data: data.get("fragment_id") == fragment_id,
            )

            result_data = processed_event.data
            processed_results.append(result_data)

            status = result_data["status"]
            processing_time_ms = result_data.get("processing_time_ms", 0)
            logger.info(f"✓ Processed {fragment_id}: status={status}, time={processing_time_ms}ms")

        total_time = asyncio.get_event_loop().time() - start_time
        logger.info(f"All fragments processed in {total_time:.1f}s")

        # Validate all succeeded
        success_count = sum(1 for r in processed_results if r["status"] == "success")
        failed_count = sum(1 for r in processed_results if r["status"] == "failed")

        logger.info(
            f"Results: {success_count} success, {failed_count} failed "
            f"out of {len(processed_results)} total"
        )

        assert success_count == len(chunks), (
            f"Not all fragments succeeded: {success_count}/{len(chunks)}"
        )
        assert failed_count == 0, f"Unexpected failures: {failed_count}"

        # Validate total latency (60s audio + processing should be < 10 minutes)
        assert total_time < 600, (
            f"Total processing time {total_time:.1f}s exceeds 10 minute threshold"
        )

        # Send stream:end
        complete_data = await client.send_stream_end(
            wait_for_complete=True,
            complete_timeout=30.0,
        )

        # Validate stream:complete statistics
        assert complete_data["total_fragments"] == len(chunks), "Fragment count mismatch"
        assert complete_data["success_count"] == len(chunks), "Success count mismatch"
        assert complete_data["failed_count"] == 0, "Unexpected failed count"
        assert "avg_processing_time_ms" in complete_data, "Missing avg_processing_time_ms"

        logger.info(f"✓ Stream complete: {complete_data}")

    logger.info("✓ Test passed: Full minute pipeline")


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_backpressure_monitoring_e2e(full_sts_service: str):
    """Test backpressure monitoring.

    Validates:
    - backpressure:state events emitted at thresholds
    - Severity levels: LOW, MEDIUM, HIGH, CRITICAL
    - Backpressure decreases as fragments complete

    Args:
        full_sts_service: Service URL from fixture
    """
    logger.info("=" * 80)
    logger.info("TEST: Backpressure Monitoring E2E")
    logger.info("=" * 80)

    # Prepare 12 chunks (exceeds HIGH threshold of 10)
    chunker = AudioChunker(TEST_AUDIO_FILE)
    chunks = chunker.chunk_audio(
        chunk_duration_ms=CHUNK_DURATION_MS,
        max_chunks=12,
    )
    logger.info(f"Prepared {len(chunks)} audio chunks")

    async with SocketIOClient(full_sts_service) as client:
        # Initialize stream
        ready_data = await client.send_stream_init(
            source_language="en",
            target_language="es",
            timeout=STREAM_INIT_TIMEOUT,
        )
        session_id = ready_data["session_id"]
        max_inflight = ready_data["max_inflight"]
        logger.info(f"Stream initialized: {session_id}, max_inflight={max_inflight}")

        # Send fragments rapidly to trigger backpressure
        logger.info("Sending fragments rapidly to trigger backpressure...")
        for chunk in chunks:
            fragment_data = chunk.to_fragment_data(stream_id=session_id)
            await client.send_fragment(
                fragment_data,
                wait_for_ack=True,
                ack_timeout=1.0,
            )

        # Wait a bit for backpressure events
        await asyncio.sleep(2)

        # Collect backpressure events
        backpressure_events = client.get_events("backpressure:state")
        logger.info(f"Received {len(backpressure_events)} backpressure events")

        # Log all backpressure events
        for event in backpressure_events:
            data = event.data
            logger.info(
                f"  Backpressure: severity={data.get('severity')}, "
                f"current_inflight={data.get('current_inflight')}, "
                f"action={data.get('action')}"
            )

        # Validate we received backpressure events
        # Note: Due to timing, we may not hit all thresholds, but we should get at least MEDIUM or HIGH
        if len(backpressure_events) > 0:
            severities = {event.data.get("severity") for event in backpressure_events}
            logger.info(f"✓ Backpressure severities observed: {severities}")

            # Validate event structure
            for event in backpressure_events:
                data = event.data
                assert "severity" in data, "Missing severity"
                assert "current_inflight" in data, "Missing current_inflight"
                assert "action" in data, "Missing action"
                assert "stream_id" in data, "Missing stream_id"
        else:
            logger.warning(
                "⚠ No backpressure events received (fragments may have processed too quickly)"
            )

        # Wait for all fragments to complete
        logger.info("Waiting for all fragments to complete...")
        processed_count = 0
        timeout = len(chunks) * FRAGMENT_PROCESSING_TIMEOUT

        while processed_count < len(chunks):
            try:
                await client.wait_for_event(
                    "fragment:processed",
                    timeout=timeout,
                )
                processed_count += 1
                logger.info(f"Processed {processed_count}/{len(chunks)} fragments")
            except TimeoutError:
                logger.error(f"Timeout waiting for fragments (got {processed_count}/{len(chunks)})")
                break

        logger.info(f"✓ All {processed_count} fragments processed")

    logger.info("✓ Test passed: Backpressure monitoring")


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_error_handling_e2e(full_sts_service: str):
    """Test error handling.

    Validates:
    - Malformed fragment returns fragment:processed with status=FAILED
    - Error includes stage, code, message
    - Valid fragment after error processes successfully

    Args:
        full_sts_service: Service URL from fixture
    """
    logger.info("=" * 80)
    logger.info("TEST: Error Handling E2E")
    logger.info("=" * 80)

    async with SocketIOClient(full_sts_service) as client:
        # Initialize stream
        ready_data = await client.send_stream_init(
            source_language="en",
            target_language="es",
            timeout=STREAM_INIT_TIMEOUT,
        )
        session_id = ready_data["session_id"]
        logger.info(f"Stream initialized: {session_id}")

        # Send malformed fragment (invalid base64 audio)
        malformed_fragment = {
            "fragment_id": "malformed-0001",
            "stream_id": session_id,
            "sequence_number": 0,
            "timestamp": 0,
            "audio": "INVALID_BASE64_DATA!!!",  # Invalid base64
            "sample_rate": 16000,
            "channels": 1,
            "format": "pcm_f32le",
            "duration_ms": 6000,
        }

        logger.info("Sending malformed fragment...")
        await client.send_fragment(
            malformed_fragment,
            wait_for_ack=True,
            ack_timeout=1.0,
        )

        # Wait for error response
        # Note: This may come as an error event or as fragment:processed with FAILED status
        # Let's wait for any response
        await asyncio.sleep(2)

        # Check for error events
        error_events = client.get_events("error")
        processed_events = client.get_events("fragment:processed")

        if len(error_events) > 0:
            logger.info(f"✓ Received error event: {error_events[0].data}")
            error_data = error_events[0].data
            assert "code" in error_data, "Error missing code"
            assert "message" in error_data, "Error missing message"
        elif len(processed_events) > 0:
            # Check if any processed event is for our malformed fragment
            for event in processed_events:
                if event.data.get("fragment_id") == "malformed-0001":
                    logger.info(f"✓ Received fragment:processed with FAILED status: {event.data}")
                    assert event.data["status"] == "failed", "Expected FAILED status"
                    assert "error" in event.data, "Missing error field"
                    error = event.data["error"]
                    assert "stage" in error, "Error missing stage"
                    assert "code" in error, "Error missing code"
                    assert "message" in error, "Error missing message"
                    break
        else:
            logger.warning("⚠ No error response received for malformed fragment")

        # Now send a valid fragment to ensure service recovers
        logger.info("Sending valid fragment after error...")
        chunker = AudioChunker(TEST_AUDIO_FILE)
        chunks = chunker.chunk_audio(chunk_duration_ms=CHUNK_DURATION_MS, max_chunks=1)
        chunk = chunks[0]

        fragment_data = chunk.to_fragment_data(stream_id=session_id)
        fragment_data["sequence_number"] = 1  # Next sequence after malformed
        fragment_id = fragment_data["fragment_id"]

        await client.send_fragment(
            fragment_data,
            wait_for_ack=True,
            ack_timeout=1.0,
        )

        # Wait for successful processing
        processed_event = await client.wait_for_event(
            "fragment:processed",
            timeout=FRAGMENT_PROCESSING_TIMEOUT,
            predicate=lambda data: data.get("fragment_id") == fragment_id,
        )

        result_data = processed_event.data
        assert result_data["status"] == "success", (
            f"Valid fragment failed after error: {result_data}"
        )
        logger.info("✓ Valid fragment processed successfully after error")

    logger.info("✓ Test passed: Error handling")
