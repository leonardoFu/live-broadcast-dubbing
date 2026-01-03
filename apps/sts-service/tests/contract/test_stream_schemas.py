"""Contract tests for stream event schemas.

Tests T005-T008: Validate stream:init, stream:ready, stream:pause/resume/end, stream:complete schemas.
These tests follow TDD - they MUST FAIL initially until schemas are created.
"""

import json
from pathlib import Path

import jsonschema
from jsonschema import Draft7Validator, RefResolver
import pytest

# Schema file paths (relative to repo root - worktree is at sts-service-main)
# Path: apps/sts-service/tests/contract/test_stream_schemas.py
# Need to go up: contract -> tests -> sts-service -> apps -> worktree-root -> specs
CONTRACTS_DIR = Path(__file__).parent.parent.parent.parent.parent / "specs" / "021-full-sts-service" / "contracts"


def create_validator(schema: dict, definition_name: str) -> Draft7Validator:
    """Create a validator for a specific definition with proper $ref resolution."""
    resolver = RefResolver.from_schema(schema)
    definition_schema = schema["definitions"][definition_name]
    return Draft7Validator(definition_schema, resolver=resolver)


class TestStreamInitSchema:
    """T005: Contract test for stream:init schema."""

    @pytest.fixture
    def schema(self) -> dict:
        """Load stream schema from JSON file."""
        schema_path = CONTRACTS_DIR / "stream-schema.json"
        with open(schema_path) as f:
            return json.load(f)

    @pytest.fixture
    def valid_stream_init_payload(self) -> dict:
        """Sample valid stream:init payload."""
        return {
            "stream_id": "stream-abc-123",
            "worker_id": "worker-001",
            "config": {
                "source_language": "en",
                "target_language": "es",
                "voice_profile": "spanish_male_1",
                "chunk_duration_ms": 6000,
                "sample_rate_hz": 48000,
                "channels": 1,
                "format": "m4a"
            }
        }

    def test_valid_stream_init_payload(self, schema: dict, valid_stream_init_payload: dict) -> None:
        """Validate that a correct stream:init payload passes schema validation."""
        validator = create_validator(schema, "stream_init")
        validator.validate(valid_stream_init_payload)

    def test_stream_init_required_fields(self, schema: dict) -> None:
        """Test that all required fields are enforced."""
        required_fields = ["stream_id", "worker_id", "config"]
        stream_init_schema = schema["definitions"]["stream_init"]

        assert "required" in stream_init_schema
        for field in required_fields:
            assert field in stream_init_schema["required"], f"Missing required field: {field}"

    def test_config_required_fields(self, schema: dict) -> None:
        """Test that config has all required fields."""
        # Check the stream_config definition directly
        config_schema = schema["definitions"]["stream_config"]

        required_config_fields = [
            "source_language", "target_language", "voice_profile",
            "chunk_duration_ms", "sample_rate_hz", "channels", "format"
        ]
        assert "required" in config_schema
        for field in required_config_fields:
            assert field in config_schema["required"], f"Missing required config field: {field}"

    def test_config_optional_domain_hints(self, schema: dict) -> None:
        """Test that domain_hints is optional in config."""
        config_schema = schema["definitions"]["stream_config"]

        # domain_hints should be in properties but not in required
        assert "domain_hints" in config_schema["properties"]
        if "required" in config_schema:
            assert "domain_hints" not in config_schema["required"]

    def test_language_code_format(self, schema: dict) -> None:
        """Test that language codes are strings (e.g., 'en', 'es', 'fr')."""
        config_schema = schema["definitions"]["stream_config"]

        assert config_schema["properties"]["source_language"]["type"] == "string"
        assert config_schema["properties"]["target_language"]["type"] == "string"


class TestStreamReadySchema:
    """T006: Contract test for stream:ready schema."""

    @pytest.fixture
    def schema(self) -> dict:
        """Load stream schema from JSON file."""
        schema_path = CONTRACTS_DIR / "stream-schema.json"
        with open(schema_path) as f:
            return json.load(f)

    @pytest.fixture
    def valid_stream_ready_payload(self) -> dict:
        """Sample valid stream:ready payload."""
        return {
            "stream_id": "stream-abc-123",
            "session_id": "session-xyz-789",
            "max_inflight": 3,
            "capabilities": ["asr", "translation", "tts", "duration_matching"]
        }

    def test_valid_stream_ready_payload(self, schema: dict, valid_stream_ready_payload: dict) -> None:
        """Validate that a correct stream:ready payload passes schema validation."""
        validator = create_validator(schema, "stream_ready")
        validator.validate(valid_stream_ready_payload)

    def test_stream_ready_required_fields(self, schema: dict) -> None:
        """Test that all required fields are enforced."""
        required_fields = ["stream_id", "session_id", "max_inflight", "capabilities"]
        stream_ready_schema = schema["definitions"]["stream_ready"]

        assert "required" in stream_ready_schema
        for field in required_fields:
            assert field in stream_ready_schema["required"], f"Missing required field: {field}"

    def test_capabilities_is_array(self, schema: dict) -> None:
        """Test that capabilities is an array of strings."""
        stream_ready_schema = schema["definitions"]["stream_ready"]
        capabilities_schema = stream_ready_schema["properties"]["capabilities"]

        assert capabilities_schema["type"] == "array"
        assert capabilities_schema["items"]["type"] == "string"

    def test_max_inflight_is_integer(self, schema: dict) -> None:
        """Test that max_inflight is an integer."""
        stream_ready_schema = schema["definitions"]["stream_ready"]
        max_inflight_schema = stream_ready_schema["properties"]["max_inflight"]

        assert max_inflight_schema["type"] == "integer"
        assert max_inflight_schema.get("minimum", 0) >= 1


class TestStreamPauseResumeEndSchemas:
    """T007: Contract test for stream:pause/resume/end schemas."""

    @pytest.fixture
    def schema(self) -> dict:
        """Load stream schema from JSON file."""
        schema_path = CONTRACTS_DIR / "stream-schema.json"
        with open(schema_path) as f:
            return json.load(f)

    def test_stream_pause_payload(self, schema: dict) -> None:
        """Validate stream:pause payload structure."""
        valid_pause_payload = {
            "stream_id": "stream-abc-123"
        }
        validator = create_validator(schema, "stream_pause")
        validator.validate(valid_pause_payload)

    def test_stream_pause_with_reason(self, schema: dict) -> None:
        """Validate stream:pause payload with optional reason."""
        pause_with_reason = {
            "stream_id": "stream-abc-123",
            "reason": "backpressure"
        }
        validator = create_validator(schema, "stream_pause")
        validator.validate(pause_with_reason)

    def test_stream_resume_payload(self, schema: dict) -> None:
        """Validate stream:resume payload structure."""
        valid_resume_payload = {
            "stream_id": "stream-abc-123"
        }
        validator = create_validator(schema, "stream_resume")
        validator.validate(valid_resume_payload)

    def test_stream_end_payload(self, schema: dict) -> None:
        """Validate stream:end payload structure."""
        valid_end_payload = {
            "stream_id": "stream-abc-123"
        }
        validator = create_validator(schema, "stream_end")
        validator.validate(valid_end_payload)

    def test_stream_end_with_reason(self, schema: dict) -> None:
        """Validate stream:end payload with optional reason."""
        end_with_reason = {
            "stream_id": "stream-abc-123",
            "reason": "source_ended"
        }
        validator = create_validator(schema, "stream_end")
        validator.validate(end_with_reason)


class TestStreamCompleteSchema:
    """T008: Contract test for stream:complete schema."""

    @pytest.fixture
    def schema(self) -> dict:
        """Load stream schema from JSON file."""
        schema_path = CONTRACTS_DIR / "stream-schema.json"
        with open(schema_path) as f:
            return json.load(f)

    @pytest.fixture
    def valid_stream_complete_payload(self) -> dict:
        """Sample valid stream:complete payload."""
        return {
            "stream_id": "stream-abc-123",
            "total_fragments": 50,
            "success_count": 45,
            "failed_count": 5,
            "avg_processing_time_ms": 4500
        }

    def test_valid_stream_complete_payload(self, schema: dict, valid_stream_complete_payload: dict) -> None:
        """Validate that a correct stream:complete payload passes schema validation."""
        validator = create_validator(schema, "stream_complete")
        validator.validate(valid_stream_complete_payload)

    def test_stream_complete_required_fields(self, schema: dict) -> None:
        """Test required fields: total_fragments, success_count, failed_count, avg_processing_time_ms."""
        required_fields = ["stream_id", "total_fragments", "success_count", "failed_count", "avg_processing_time_ms"]
        stream_complete_schema = schema["definitions"]["stream_complete"]

        assert "required" in stream_complete_schema
        for field in required_fields:
            assert field in stream_complete_schema["required"], f"Missing required field: {field}"

    def test_stream_complete_optional_error_breakdown(self, schema: dict) -> None:
        """Test that error_breakdown is optional."""
        stream_complete_schema = schema["definitions"]["stream_complete"]

        # error_breakdown should be in properties but not in required
        assert "error_breakdown" in stream_complete_schema["properties"]
        if "required" in stream_complete_schema:
            assert "error_breakdown" not in stream_complete_schema["required"]

    def test_stream_complete_with_error_breakdown(self, schema: dict) -> None:
        """Validate stream:complete with error_breakdown."""
        payload_with_breakdown = {
            "stream_id": "stream-abc-123",
            "total_fragments": 50,
            "success_count": 45,
            "failed_count": 5,
            "avg_processing_time_ms": 4500,
            "error_breakdown": {
                "by_stage": {
                    "asr": 2,
                    "translation": 1,
                    "tts": 2
                },
                "by_code": {
                    "TIMEOUT": 3,
                    "RATE_LIMIT_EXCEEDED": 2
                }
            }
        }
        validator = create_validator(schema, "stream_complete")
        validator.validate(payload_with_breakdown)
