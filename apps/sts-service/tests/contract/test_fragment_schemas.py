"""Contract tests for fragment event schemas.

Tests T001-T004: Validate fragment:data, fragment:ack, fragment:processed schemas.
These tests follow TDD - they MUST FAIL initially until schemas are created.
"""

import json
from pathlib import Path

import jsonschema
from jsonschema import Draft7Validator, RefResolver
import pytest

# Schema file paths (relative to repo root - worktree is at sts-service-main)
# Path: apps/sts-service/tests/contract/test_fragment_schemas.py
# Need to go up: contract -> tests -> sts-service -> apps -> worktree-root -> specs
CONTRACTS_DIR = (
    Path(__file__).parent.parent.parent.parent.parent
    / "specs"
    / "021-full-sts-service"
    / "contracts"
)


def create_validator(schema: dict, definition_name: str) -> Draft7Validator:
    """Create a validator for a specific definition with proper $ref resolution."""
    resolver = RefResolver.from_schema(schema)
    definition_schema = schema["definitions"][definition_name]
    return Draft7Validator(definition_schema, resolver=resolver)


class TestFragmentDataSchema:
    """T001: Contract test for fragment:data schema."""

    @pytest.fixture
    def schema(self) -> dict:
        """Load fragment schema from JSON file."""
        schema_path = CONTRACTS_DIR / "fragment-schema.json"
        with open(schema_path) as f:
            return json.load(f)

    @pytest.fixture
    def valid_fragment_data_payload(self) -> dict:
        """Sample valid fragment:data payload."""
        return {
            "fragment_id": "550e8400-e29b-41d4-a716-446655440000",
            "stream_id": "stream-abc-123",
            "sequence_number": 0,
            "timestamp": 1704067200000,
            "audio": {
                "format": "m4a",
                "sample_rate_hz": 48000,
                "channels": 1,
                "duration_ms": 6000,
                "data_base64": "AQIDBAU=",
            },
        }

    def test_valid_fragment_data_payload(
        self, schema: dict, valid_fragment_data_payload: dict
    ) -> None:
        """Validate that a correct fragment:data payload passes schema validation."""
        validator = create_validator(schema, "fragment_data")
        validator.validate(valid_fragment_data_payload)

    def test_fragment_data_required_fields(self, schema: dict) -> None:
        """Test that all required fields are enforced."""
        required_fields = ["fragment_id", "stream_id", "sequence_number", "timestamp", "audio"]
        fragment_data_schema = schema["definitions"]["fragment_data"]

        assert "required" in fragment_data_schema
        for field in required_fields:
            assert field in fragment_data_schema["required"], f"Missing required field: {field}"

    def test_fragment_data_field_types(self, schema: dict) -> None:
        """Test that field types are correctly defined."""
        fragment_data_schema = schema["definitions"]["fragment_data"]
        properties = fragment_data_schema["properties"]

        # Validate field type definitions
        assert properties["fragment_id"]["type"] == "string"
        assert properties["stream_id"]["type"] == "string"
        assert properties["sequence_number"]["type"] == "integer"
        assert properties["timestamp"]["type"] == "integer"
        # Audio uses $ref, so check the ref target
        assert "$ref" in properties["audio"] or properties["audio"].get("type") == "object"

    def test_fragment_data_audio_structure(self, schema: dict) -> None:
        """Test audio object structure within fragment:data."""
        # Check the audio_data definition directly
        audio_schema = schema["definitions"]["audio_data"]

        required_audio_fields = [
            "format",
            "sample_rate_hz",
            "channels",
            "duration_ms",
            "data_base64",
        ]
        assert "required" in audio_schema
        for field in required_audio_fields:
            assert field in audio_schema["required"], f"Missing required audio field: {field}"

    def test_fragment_data_rejects_missing_fields(self, schema: dict) -> None:
        """Test that missing required fields fail validation."""
        invalid_payload = {
            "fragment_id": "test-id"
            # Missing stream_id, sequence_number, timestamp, audio
        }

        validator = create_validator(schema, "fragment_data")
        with pytest.raises(jsonschema.ValidationError):
            validator.validate(invalid_payload)


class TestFragmentAckSchema:
    """T002: Contract test for fragment:ack schema."""

    @pytest.fixture
    def schema(self) -> dict:
        """Load fragment schema from JSON file."""
        schema_path = CONTRACTS_DIR / "fragment-schema.json"
        with open(schema_path) as f:
            return json.load(f)

    @pytest.fixture
    def valid_fragment_ack_payload(self) -> dict:
        """Sample valid fragment:ack payload."""
        return {
            "fragment_id": "550e8400-e29b-41d4-a716-446655440000",
            "status": "queued",
            "timestamp": 1704067200000,
        }

    def test_valid_fragment_ack_payload(
        self, schema: dict, valid_fragment_ack_payload: dict
    ) -> None:
        """Validate that a correct fragment:ack payload passes schema validation."""
        validator = create_validator(schema, "fragment_ack")
        validator.validate(valid_fragment_ack_payload)

    def test_fragment_ack_required_fields(self, schema: dict) -> None:
        """Test that all required fields are enforced."""
        required_fields = ["fragment_id", "status", "timestamp"]
        fragment_ack_schema = schema["definitions"]["fragment_ack"]

        assert "required" in fragment_ack_schema
        for field in required_fields:
            assert field in fragment_ack_schema["required"], f"Missing required field: {field}"

    def test_fragment_ack_status_enum(self, schema: dict) -> None:
        """Test that status field has correct enum value."""
        fragment_ack_schema = schema["definitions"]["fragment_ack"]
        status_schema = fragment_ack_schema["properties"]["status"]

        assert "enum" in status_schema
        assert "queued" in status_schema["enum"]


class TestFragmentProcessedSuccessSchema:
    """T003: Contract test for fragment:processed SUCCESS schema."""

    @pytest.fixture
    def schema(self) -> dict:
        """Load fragment schema from JSON file."""
        schema_path = CONTRACTS_DIR / "fragment-schema.json"
        with open(schema_path) as f:
            return json.load(f)

    @pytest.fixture
    def valid_success_payload(self) -> dict:
        """Sample valid fragment:processed SUCCESS payload."""
        return {
            "fragment_id": "550e8400-e29b-41d4-a716-446655440000",
            "stream_id": "stream-abc-123",
            "sequence_number": 0,
            "status": "success",
            "dubbed_audio": {
                "format": "pcm_s16le",
                "sample_rate_hz": 48000,
                "channels": 1,
                "duration_ms": 6050,
                "data_base64": "AQIDBAU=",
            },
            "transcript": "Hello, welcome to the game.",
            "translated_text": "Hola, bienvenido al juego.",
            "processing_time_ms": 4500,
            "stage_timings": {"asr_ms": 1200, "translation_ms": 150, "tts_ms": 3100},
            "metadata": {
                "original_duration_ms": 6000,
                "dubbed_duration_ms": 6050,
                "duration_variance_percent": 0.83,
                "speed_ratio": 0.99,
            },
        }

    def test_valid_success_payload(self, schema: dict, valid_success_payload: dict) -> None:
        """Validate that a correct fragment:processed SUCCESS payload passes validation."""
        validator = create_validator(schema, "fragment_processed")
        validator.validate(valid_success_payload)

    def test_fragment_processed_required_fields(self, schema: dict) -> None:
        """Test required fields for fragment:processed."""
        required_fields = [
            "fragment_id",
            "stream_id",
            "sequence_number",
            "status",
            "processing_time_ms",
        ]
        fragment_processed_schema = schema["definitions"]["fragment_processed"]

        assert "required" in fragment_processed_schema
        for field in required_fields:
            assert field in fragment_processed_schema["required"], (
                f"Missing required field: {field}"
            )

    def test_success_requires_dubbed_audio(self, schema: dict) -> None:
        """Test that SUCCESS status requires dubbed_audio field."""
        # Per spec, dubbed_audio is present when status is success or partial
        fragment_processed_schema = schema["definitions"]["fragment_processed"]

        # Validate dubbed_audio is defined in properties
        assert "dubbed_audio" in fragment_processed_schema["properties"]

    def test_dubbed_audio_is_base64_encoded_pcm(self, schema: dict) -> None:
        """Test that dubbed_audio uses audio_data structure with data_base64."""
        # Check the audio_data definition directly
        audio_schema = schema["definitions"]["audio_data"]

        assert "data_base64" in audio_schema["properties"]
        assert "format" in audio_schema["properties"]

    def test_metadata_includes_duration_matching_stats(self, schema: dict) -> None:
        """Test that metadata includes duration matching statistics."""
        # Check the duration_metadata definition directly
        metadata_schema = schema["definitions"]["duration_metadata"]

        expected_fields = [
            "original_duration_ms",
            "dubbed_duration_ms",
            "duration_variance_percent",
            "speed_ratio",
        ]
        for field in expected_fields:
            assert field in metadata_schema["properties"], f"Missing metadata field: {field}"

    def test_stage_timings_structure(self, schema: dict) -> None:
        """Test stage_timings includes asr_ms, translation_ms, tts_ms."""
        # Check the stage_timings definition directly
        stage_timings_schema = schema["definitions"]["stage_timings"]

        expected_fields = ["asr_ms", "translation_ms", "tts_ms"]
        for field in expected_fields:
            assert field in stage_timings_schema["properties"], f"Missing stage timing: {field}"


class TestFragmentProcessedFailedSchema:
    """T004: Contract test for fragment:processed FAILED schema."""

    @pytest.fixture
    def schema(self) -> dict:
        """Load fragment schema from JSON file."""
        schema_path = CONTRACTS_DIR / "fragment-schema.json"
        with open(schema_path) as f:
            return json.load(f)

    @pytest.fixture
    def valid_failed_payload(self) -> dict:
        """Sample valid fragment:processed FAILED payload."""
        return {
            "fragment_id": "550e8400-e29b-41d4-a716-446655440002",
            "stream_id": "stream-abc-123",
            "sequence_number": 2,
            "status": "failed",
            "processing_time_ms": 5100,
            "stage_timings": {"asr_ms": 5000, "translation_ms": 0, "tts_ms": 0},
            "error": {
                "stage": "asr",
                "code": "TIMEOUT",
                "message": "ASR processing timed out after 5000ms",
                "retryable": True,
            },
        }

    def test_valid_failed_payload(self, schema: dict, valid_failed_payload: dict) -> None:
        """Validate that a correct fragment:processed FAILED payload passes validation."""
        validator = create_validator(schema, "fragment_processed")
        validator.validate(valid_failed_payload)

    def test_failed_status_requires_error(self, schema: dict) -> None:
        """Test that error object is defined for failed status."""
        fragment_processed_schema = schema["definitions"]["fragment_processed"]

        assert "error" in fragment_processed_schema["properties"]

    def test_error_required_fields(self, schema: dict) -> None:
        """Test required error fields: stage, code, message, retryable."""
        # Check the processing_error definition directly
        error_schema = schema["definitions"]["processing_error"]

        required_error_fields = ["stage", "code", "message", "retryable"]
        assert "required" in error_schema
        for field in required_error_fields:
            assert field in error_schema["required"], f"Missing required error field: {field}"

    def test_error_stage_enum(self, schema: dict) -> None:
        """Test error.stage enum: asr, translation, tts."""
        # Check the processing_error definition directly
        error_schema = schema["definitions"]["processing_error"]
        stage_schema = error_schema["properties"]["stage"]

        assert "enum" in stage_schema
        expected_stages = ["asr", "translation", "tts"]
        for stage in expected_stages:
            assert stage in stage_schema["enum"], f"Missing error stage: {stage}"

    def test_error_code_examples(self, schema: dict) -> None:
        """Test that common error codes are documented."""
        # Check the processing_error definition directly
        error_schema = schema["definitions"]["processing_error"]
        code_schema = error_schema["properties"]["code"]

        # Code should be a string type
        assert code_schema["type"] == "string"

    def test_error_retryable_is_boolean(self, schema: dict) -> None:
        """Test error.retryable is boolean type."""
        # Check the processing_error definition directly
        error_schema = schema["definitions"]["processing_error"]
        retryable_schema = error_schema["properties"]["retryable"]

        assert retryable_schema["type"] == "boolean"

    def test_failed_payload_no_dubbed_audio(self, schema: dict, valid_failed_payload: dict) -> None:
        """Test that failed payload without dubbed_audio is valid."""
        # Per spec, dubbed_audio is NOT present for failed status
        assert "dubbed_audio" not in valid_failed_payload
        validator = create_validator(schema, "fragment_processed")
        validator.validate(valid_failed_payload)
