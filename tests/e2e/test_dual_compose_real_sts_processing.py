"""Dual Compose E2E Test: Real STS Processing (User Story 3).

Tests real STS service processing with ASR + Translation + TTS:
- Send audio fragment via Socket.IO
- Verify transcript contains expected text (ASR check)
- Verify translated_text is in target language (Translation check)
- Verify dubbed_audio field present and non-empty (TTS check)
- Verify processing_time_ms is reasonable for CPU

Priority: P1 (MVP)
"""

import asyncio
import base64
import logging
from pathlib import Path

import pytest

logger = logging.getLogger(__name__)


@pytest.mark.e2e
@pytest.mark.slow
@pytest.mark.requires_docker
@pytest.mark.requires_sts
@pytest.mark.asyncio
async def test_sts_processes_real_audio(sts_compose_env, sts_monitor):
    """Test STS processes real audio with ASR + Translation + TTS.

    Test Scenario:
    1. Extract 6-second audio from test fixture (segment with "One, two, three, four, five, six")
    2. Send fragment:data event with audio_data (base64 PCM), source=en, target=es
    3. Wait for fragment:processed event (timeout 20s for real STS latency)
    4. Verify transcript contains expected counting phrases (ASR accuracy)
    5. Verify translated_text is Spanish (Translation check)
    6. Verify dubbed_audio field present and non-empty (TTS check)

    Expected Results:
    - fragment:processed event received within 20s
    - transcript contains expected English text
    - translated_text is Spanish
    - dubbed_audio is present and non-empty
    - processing_time_ms < 15000ms (15s for 6s audio on CPU)

    This test MUST initially FAIL if:
    - STS service not running
    - ASR/Translation/TTS modules not configured
    - Socket.IO event contract incorrect
    """
    logger.info("Testing real STS processing with audio fragment...")

    # Step 1: Extract 6-second audio segment from test fixture
    logger.info("Step 1: Extracting 6s audio segment from test fixture...")

    fixture_path = Path(__file__).parent / "fixtures/test_streams/30s-counting-english.mp4"
    assert fixture_path.exists(), f"Test fixture should exist at {fixture_path}"

    # Extract first 6 seconds as PCM audio using ffmpeg
    import subprocess

    # Extract as PCM s16le (signed 16-bit little-endian) at 16kHz mono (standard for ASR)
    audio_pcm_path = "/tmp/test_audio_6s.pcm"
    subprocess.run(
        [
            "ffmpeg",
            "-i", str(fixture_path),
            "-ss", "0",
            "-t", "6",
            "-ar", "16000",
            "-ac", "1",
            "-f", "s16le",
            "-y",
            audio_pcm_path,
        ],
        capture_output=True,
        check=True,
    )

    # Read PCM data and encode as base64
    with open(audio_pcm_path, "rb") as f:
        pcm_data = f.read()

    audio_base64 = base64.b64encode(pcm_data).decode("utf-8")

    logger.info(f"Extracted {len(pcm_data)} bytes of PCM audio (base64: {len(audio_base64)} chars)")

    # Step 2: Send fragment:data event to STS service
    logger.info("Step 2: Sending fragment:data event to STS service...")

    fragment_data = {
        "fragment_id": "test_fragment_001",
        "audio_data": audio_base64,
        "audio_format": "pcm_s16le",
        "sample_rate": 16000,
        "channels": 1,
        "source_language": "en",
        "target_language": "es",
        "timestamp_ns": 0,
    }

    await sts_monitor.emit("fragment:data", fragment_data)

    # Step 3: Wait for fragment:processed event
    logger.info("Step 3: Waiting for fragment:processed event...")

    try:
        processed_event = await sts_monitor.wait_for_event(
            event_name="fragment:processed",
            timeout=20.0,
            predicate=lambda data: data.get("fragment_id") == "test_fragment_001",
        )

        logger.info("Received fragment:processed event")

    except asyncio.TimeoutError:
        raise AssertionError("Timeout waiting for fragment:processed event (20s)")

    # Step 4: Verify event data schema and content
    logger.info("Step 4: Verifying fragment:processed event schema...")

    data = processed_event.data

    # Verify required fields
    assert "fragment_id" in data, "Event should contain fragment_id"
    assert "transcript" in data, "Event should contain transcript"
    assert "translated_text" in data, "Event should contain translated_text"
    assert "dubbed_audio" in data, "Event should contain dubbed_audio"
    assert "processing_time_ms" in data, "Event should contain processing_time_ms"

    # Verify field values
    assert data["fragment_id"] == "test_fragment_001", \
        f"fragment_id should match, got {data['fragment_id']}"

    transcript = data["transcript"]
    assert transcript is not None and len(transcript) > 0, \
        "Transcript should not be empty"

    translated_text = data["translated_text"]
    assert translated_text is not None and len(translated_text) > 0, \
        "Translated text should not be empty"

    dubbed_audio = data["dubbed_audio"]
    assert dubbed_audio is not None and len(dubbed_audio) > 0, \
        "Dubbed audio should not be empty"

    processing_time_ms = data["processing_time_ms"]
    assert processing_time_ms is not None and processing_time_ms > 0, \
        "Processing time should be positive"
    assert processing_time_ms < 15000, \
        f"Processing time should be < 15s for 6s audio on CPU, got {processing_time_ms}ms"

    logger.info(f"Transcript: '{transcript}'")
    logger.info(f"Translation: '{translated_text}'")
    logger.info(f"Dubbed audio size: {len(dubbed_audio)} bytes")
    logger.info(f"Processing time: {processing_time_ms}ms")

    # Step 5: Verify transcript contains expected counting phrases
    logger.info("Step 5: Verifying transcript content (ASR accuracy)...")

    # Expected: audio should contain "one, two, three, four, five, six" (case-insensitive)
    transcript_lower = transcript.lower()

    # Check for at least some of the expected numbers
    expected_words = ["one", "two", "three", "four", "five", "six"]
    found_words = [word for word in expected_words if word in transcript_lower]

    assert len(found_words) >= 3, \
        f"Transcript should contain at least 3 of the expected counting words, found: {found_words}"

    logger.info(f"ASR accuracy check: Found {len(found_words)}/6 expected words: {found_words}")

    # Step 6: Verify translation is Spanish
    logger.info("Step 6: Verifying translation is Spanish...")

    # Check for Spanish words (uno, dos, tres, etc.)
    spanish_words = ["uno", "dos", "tres", "cuatro", "cinco", "seis"]
    translation_lower = translated_text.lower()

    found_spanish = [word for word in spanish_words if word in translation_lower]

    # At least some Spanish words should be present
    assert len(found_spanish) >= 2, \
        f"Translation should contain Spanish words, found: {found_spanish}"

    logger.info(f"Translation check: Found {len(found_spanish)} Spanish words: {found_spanish}")

    logger.info("Real STS processing test PASSED")


@pytest.mark.e2e
@pytest.mark.slow
@pytest.mark.requires_docker
@pytest.mark.requires_sts
@pytest.mark.asyncio
async def test_sts_fragment_processing_contract(sts_compose_env, sts_monitor):
    """Test STS fragment:processed event contract (spec 016).

    Test Scenario:
    1. Send fragment:data event with minimal valid data
    2. Verify fragment:processed event schema matches spec 016
    3. Verify processing_time_ms is reasonable

    Expected Results:
    - Event schema matches: fragment_id, transcript, translated_text, dubbed_audio, processing_time_ms
    - All required fields present
    - processing_time_ms < 15000ms

    This test MUST initially FAIL if:
    - Event schema doesn't match spec 016
    - Required fields missing
    - Field types incorrect
    """
    logger.info("Testing fragment:processed event contract...")

    # Send minimal fragment (silence or very short audio)
    # Generate 1 second of silence as PCM
    import struct

    sample_rate = 16000
    duration = 1  # 1 second
    silence_samples = [0] * (sample_rate * duration)
    silence_pcm = b"".join(struct.pack("<h", sample) for sample in silence_samples)
    silence_base64 = base64.b64encode(silence_pcm).decode("utf-8")

    fragment_data = {
        "fragment_id": "contract_test_001",
        "audio_data": silence_base64,
        "audio_format": "pcm_s16le",
        "sample_rate": 16000,
        "channels": 1,
        "source_language": "en",
        "target_language": "es",
        "timestamp_ns": 0,
    }

    await sts_monitor.emit("fragment:data", fragment_data)

    # Wait for response
    try:
        processed_event = await sts_monitor.wait_for_event(
            event_name="fragment:processed",
            timeout=20.0,
            predicate=lambda data: data.get("fragment_id") == "contract_test_001",
        )
    except asyncio.TimeoutError:
        raise AssertionError("Timeout waiting for fragment:processed event")

    # Verify contract
    data = processed_event.data

    required_fields = [
        "fragment_id",
        "transcript",
        "translated_text",
        "dubbed_audio",
        "processing_time_ms",
    ]

    for field in required_fields:
        assert field in data, f"Event should contain required field: {field}"

    # Verify field types
    assert isinstance(data["fragment_id"], str), "fragment_id should be string"
    assert isinstance(data["transcript"], str), "transcript should be string"
    assert isinstance(data["translated_text"], str), "translated_text should be string"
    assert isinstance(data["dubbed_audio"], str), "dubbed_audio should be string (base64)"
    assert isinstance(data["processing_time_ms"], (int, float)), \
        "processing_time_ms should be numeric"

    # Verify processing time is reasonable
    assert data["processing_time_ms"] < 15000, \
        f"Processing time should be < 15s, got {data['processing_time_ms']}ms"

    logger.info("Fragment:processed event contract PASSED")
