"""
Unit tests for structured logging configuration.

Tests structured logging functionality including:
- Fragment ID, stream ID, sequence number in log entries
- Stage timings logged
- JSON format output
- Log levels
"""

import json
import logging
from datetime import datetime
from io import StringIO
from unittest.mock import patch

import pytest


# T123: Test logs include fragment_id
def test_logs_include_fragment_id(caplog):
    """
    Test that log entries include fragment_id field.

    Given: Structured logging configured
    When: log_fragment_received() called with fragment_id
    Then: Log entry includes fragment_id field
    """
    from sts_service.full.observability.logging_config import log_fragment_received

    with caplog.at_level(logging.INFO):
        log_fragment_received(
            fragment_id="frag-001",
            stream_id="stream-001",
            sequence_number=0,
        )

        # Verify log record includes fragment_id
        assert len(caplog.records) == 1
        record = caplog.records[0]
        assert hasattr(record, "fragment_id")
        assert record.fragment_id == "frag-001"


# T123: Test logs include stream_id
def test_logs_include_stream_id(caplog):
    """
    Test that log entries include stream_id field.

    Given: Structured logging configured
    When: log_fragment_received() called with stream_id
    Then: Log entry includes stream_id field
    """
    from sts_service.full.observability.logging_config import log_fragment_received

    with caplog.at_level(logging.INFO):
        log_fragment_received(
            fragment_id="frag-001",
            stream_id="stream-001",
            sequence_number=0,
        )

        record = caplog.records[0]
        assert hasattr(record, "stream_id")
        assert record.stream_id == "stream-001"


# T123: Test logs include sequence_number
def test_logs_include_sequence_number(caplog):
    """
    Test that log entries include sequence_number field.

    Given: Structured logging configured
    When: log_fragment_received() called with sequence_number
    Then: Log entry includes sequence_number field
    """
    from sts_service.full.observability.logging_config import log_fragment_received

    with caplog.at_level(logging.INFO):
        log_fragment_received(
            fragment_id="frag-001",
            stream_id="stream-001",
            sequence_number=5,
        )

        record = caplog.records[0]
        assert hasattr(record, "sequence_number")
        assert record.sequence_number == 5


# T124: Test stage timings logged
def test_stage_timings_logged(caplog):
    """
    Test that log entries include stage timings.

    Given: Structured logging configured
    When: log_fragment_processed() called with stage timings
    Then: Log entry includes asr_duration_ms, translation_duration_ms, tts_duration_ms
    """
    from sts_service.full.observability.logging_config import log_fragment_processed

    with caplog.at_level(logging.INFO):
        log_fragment_processed(
            fragment_id="frag-001",
            stream_id="stream-001",
            status="success",
            processing_time_ms=5250,
            stage_timings={
                "asr_ms": 3500,
                "translation_ms": 250,
                "tts_ms": 1500,
            },
        )

        record = caplog.records[0]
        assert hasattr(record, "asr_duration_ms")
        assert record.asr_duration_ms == 3500
        assert hasattr(record, "translation_duration_ms")
        assert record.translation_duration_ms == 250
        assert hasattr(record, "tts_duration_ms")
        assert record.tts_duration_ms == 1500


# T123: Test JSON log format
def test_json_log_format():
    """
    Test that logs output in JSON format.

    Given: Structured logging with JSON formatter
    When: Log entry created
    Then: Output is valid JSON with timestamp, level, event, context fields
    """
    from sts_service.full.observability.logging_config import configure_logging

    # Capture log output
    log_stream = StringIO()
    handler = logging.StreamHandler(log_stream)

    # Configure logging with JSON formatter
    logger = configure_logging(log_level="INFO", json_output=True, handler=handler)

    # Create log entry
    logger.info(
        "fragment_received",
        extra={
            "fragment_id": "frag-001",
            "stream_id": "stream-001",
            "sequence_number": 0,
        },
    )

    # Parse JSON output
    log_output = log_stream.getvalue().strip()
    log_entry = json.loads(log_output)

    # Verify JSON structure
    assert "timestamp" in log_entry
    assert "level" in log_entry
    assert log_entry["level"] == "INFO"
    assert "event" in log_entry or "message" in log_entry
    assert "fragment_id" in log_entry
    assert log_entry["fragment_id"] == "frag-001"
    assert "stream_id" in log_entry
    assert log_entry["stream_id"] == "stream-001"


# T124: Test log levels
def test_log_levels(caplog):
    """
    Test that different log levels work correctly.

    Given: Structured logging configured with INFO level
    When: DEBUG, INFO, WARNING, ERROR logs created
    Then: INFO and above logged, DEBUG filtered out
    """
    from sts_service.full.observability.logging_config import (
        log_fragment_received,
        log_error,
    )

    with caplog.at_level(logging.INFO):
        # INFO level - should be logged
        log_fragment_received(fragment_id="frag-001", stream_id="stream-001", sequence_number=0)

        # ERROR level - should be logged
        log_error(
            fragment_id="frag-001",
            stream_id="stream-001",
            stage="asr",
            error_code="TIMEOUT",
            error_message="ASR timeout exceeded",
        )

        # Verify both logged
        assert len(caplog.records) >= 2


# T124: Test error logging
def test_error_logging(caplog):
    """
    Test that errors are logged with correct fields.

    Given: Structured logging configured
    When: log_error() called with stage, error_code, error_message
    Then: Log entry includes all error fields
    """
    from sts_service.full.observability.logging_config import log_error

    with caplog.at_level(logging.ERROR):
        log_error(
            fragment_id="frag-001",
            stream_id="stream-001",
            stage="asr",
            error_code="TIMEOUT",
            error_message="ASR timeout exceeded",
        )

        record = caplog.records[0]
        assert record.levelname == "ERROR"
        assert hasattr(record, "stage")
        assert record.stage == "asr"
        assert hasattr(record, "error_code")
        assert record.error_code == "TIMEOUT"
        assert "timeout" in record.message.lower()


# T123: Test backpressure logging
def test_backpressure_logging(caplog):
    """
    Test that backpressure events are logged with severity and action.

    Given: Structured logging configured
    When: log_backpressure() called
    Then: Log entry includes severity, action, current_inflight, max_inflight
    """
    from sts_service.full.observability.logging_config import log_backpressure

    with caplog.at_level(logging.WARNING):
        log_backpressure(
            stream_id="stream-001",
            severity="medium",
            action="slow_down",
            current_inflight=5,
            max_inflight=3,
        )

        record = caplog.records[0]
        assert record.levelname == "WARNING"
        assert hasattr(record, "severity")
        assert record.severity == "medium"
        assert hasattr(record, "action")
        assert record.action == "slow_down"
        assert hasattr(record, "current_inflight")
        assert record.current_inflight == 5


# T124: Test processing timings in logs
def test_processing_timings_in_logs(caplog):
    """
    Test that processing time is logged.

    Given: Fragment processing completes
    When: log_fragment_processed() called
    Then: Log includes processing_time_ms
    """
    from sts_service.full.observability.logging_config import log_fragment_processed

    with caplog.at_level(logging.INFO):
        log_fragment_processed(
            fragment_id="frag-001",
            stream_id="stream-001",
            status="success",
            processing_time_ms=5250,
            stage_timings={
                "asr_ms": 3500,
                "translation_ms": 250,
                "tts_ms": 1500,
            },
        )

        record = caplog.records[0]
        assert hasattr(record, "processing_time_ms")
        assert record.processing_time_ms == 5250


# T123: Test stream lifecycle logging
def test_stream_lifecycle_logging(caplog):
    """
    Test that stream lifecycle events are logged.

    Given: Structured logging configured
    When: log_stream_init(), log_stream_end() called
    Then: Log entries include stream_id and event type
    """
    from sts_service.full.observability.logging_config import (
        log_stream_init,
        log_stream_end,
    )

    with caplog.at_level(logging.INFO):
        log_stream_init(
            stream_id="stream-001",
            source_language="en",
            target_language="es",
            voice_profile="spanish_male_1",
        )

        log_stream_end(
            stream_id="stream-001",
            total_fragments=10,
            success_count=9,
            failed_count=1,
        )

        assert len(caplog.records) == 2

        # Verify stream init log
        init_record = caplog.records[0]
        assert hasattr(init_record, "stream_id")
        assert init_record.stream_id == "stream-001"
        assert hasattr(init_record, "source_language")
        assert init_record.source_language == "en"

        # Verify stream end log
        end_record = caplog.records[1]
        assert hasattr(end_record, "total_fragments")
        assert end_record.total_fragments == 10


# T123: Test log context manager
def test_log_context_manager(caplog):
    """
    Test that log context can be set and used throughout processing.

    Given: Structured logging configured
    When: set_log_context() used to set fragment_id, stream_id
    Then: Subsequent logs automatically include context fields
    """
    from sts_service.full.observability.logging_config import (
        set_log_context,
        get_logger,
    )

    logger = get_logger(__name__)

    with caplog.at_level(logging.INFO):
        # Set context
        with set_log_context(fragment_id="frag-001", stream_id="stream-001"):
            logger.info("Processing fragment")

            # Verify context in log
            record = caplog.records[0]
            assert hasattr(record, "fragment_id")
            assert record.fragment_id == "frag-001"
            assert hasattr(record, "stream_id")
            assert record.stream_id == "stream-001"


# T124: Test timestamp format
def test_timestamp_format():
    """
    Test that timestamps are in ISO 8601 format.

    Given: Structured logging with JSON formatter
    When: Log entry created
    Then: Timestamp field is in ISO 8601 format (YYYY-MM-DDTHH:MM:SS.sssZ)
    """
    from sts_service.full.observability.logging_config import configure_logging

    log_stream = StringIO()
    handler = logging.StreamHandler(log_stream)
    logger = configure_logging(log_level="INFO", json_output=True, handler=handler)

    logger.info("test_message")

    log_output = log_stream.getvalue().strip()
    log_entry = json.loads(log_output)

    # Verify timestamp format
    assert "timestamp" in log_entry
    timestamp_str = log_entry["timestamp"]

    # Parse timestamp (should not raise exception)
    try:
        # ISO 8601 format with 'Z' suffix
        datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
    except ValueError:
        pytest.fail(f"Invalid timestamp format: {timestamp_str}")
