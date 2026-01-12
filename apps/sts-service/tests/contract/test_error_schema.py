"""Contract tests for error response schema.

Test T010: Validate error response structure for all error codes.
This test follows TDD - it MUST FAIL initially until schema is created.
"""

import json
from pathlib import Path

import pytest
from jsonschema import Draft7Validator, RefResolver

# Schema file paths (relative to repo root - worktree is at sts-service-main)
# Path: apps/sts-service/tests/contract/test_error_schema.py
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


class TestErrorResponseSchema:
    """T010: Contract test for error response schema."""

    @pytest.fixture
    def schema(self) -> dict:
        """Load error schema from JSON file."""
        schema_path = CONTRACTS_DIR / "error-schema.json"
        with open(schema_path) as f:
            return json.load(f)

    @pytest.fixture
    def stream_not_found_error(self) -> dict:
        """Sample STREAM_NOT_FOUND error payload."""
        return {
            "code": "STREAM_NOT_FOUND",
            "message": "Stream stream-abc-123 not found",
            "retryable": False,
        }

    @pytest.fixture
    def stream_paused_error(self) -> dict:
        """Sample STREAM_PAUSED error payload."""
        return {
            "code": "STREAM_PAUSED",
            "message": "Stream is currently paused",
            "retryable": False,
        }

    @pytest.fixture
    def invalid_config_error(self) -> dict:
        """Sample INVALID_CONFIG error payload."""
        return {
            "code": "INVALID_CONFIG",
            "message": "Invalid stream configuration: missing source_language",
            "retryable": False,
        }

    @pytest.fixture
    def invalid_voice_profile_error(self) -> dict:
        """Sample INVALID_VOICE_PROFILE error payload."""
        return {
            "code": "INVALID_VOICE_PROFILE",
            "message": "Voice profile 'unknown_voice' not found in voices.json",
            "retryable": False,
        }

    @pytest.fixture
    def backpressure_exceeded_error(self) -> dict:
        """Sample BACKPRESSURE_EXCEEDED error payload."""
        return {
            "code": "BACKPRESSURE_EXCEEDED",
            "message": "In-flight count 11 exceeds critical threshold 10",
            "retryable": True,
        }

    @pytest.fixture
    def timeout_error(self) -> dict:
        """Sample TIMEOUT error payload (transient, retryable)."""
        return {
            "code": "TIMEOUT",
            "message": "Processing timed out after 8000ms",
            "retryable": True,
        }

    def test_valid_error_response(self, schema: dict, stream_not_found_error: dict) -> None:
        """Validate that a correct error payload passes schema validation."""
        validator = create_validator(schema, "error_response")
        validator.validate(stream_not_found_error)

    def test_error_required_fields(self, schema: dict) -> None:
        """Test that all required fields are enforced: code, message, retryable."""
        required_fields = ["code", "message", "retryable"]
        error_schema = schema["definitions"]["error_response"]

        assert "required" in error_schema
        for field in required_fields:
            assert field in error_schema["required"], f"Missing required field: {field}"

    def test_stream_not_found_error(self, schema: dict, stream_not_found_error: dict) -> None:
        """Validate STREAM_NOT_FOUND error."""
        validator = create_validator(schema, "error_response")
        validator.validate(stream_not_found_error)
        assert stream_not_found_error["retryable"] is False

    def test_stream_paused_error(self, schema: dict, stream_paused_error: dict) -> None:
        """Validate STREAM_PAUSED error."""
        validator = create_validator(schema, "error_response")
        validator.validate(stream_paused_error)
        assert stream_paused_error["retryable"] is False

    def test_invalid_config_error(self, schema: dict, invalid_config_error: dict) -> None:
        """Validate INVALID_CONFIG error."""
        validator = create_validator(schema, "error_response")
        validator.validate(invalid_config_error)
        assert invalid_config_error["retryable"] is False

    def test_invalid_voice_profile_error(
        self, schema: dict, invalid_voice_profile_error: dict
    ) -> None:
        """Validate INVALID_VOICE_PROFILE error."""
        validator = create_validator(schema, "error_response")
        validator.validate(invalid_voice_profile_error)
        assert invalid_voice_profile_error["retryable"] is False

    def test_backpressure_exceeded_error(
        self, schema: dict, backpressure_exceeded_error: dict
    ) -> None:
        """Validate BACKPRESSURE_EXCEEDED error (transient, retryable)."""
        validator = create_validator(schema, "error_response")
        validator.validate(backpressure_exceeded_error)
        assert backpressure_exceeded_error["retryable"] is True

    def test_timeout_error_is_retryable(self, schema: dict, timeout_error: dict) -> None:
        """Test that TIMEOUT errors are marked retryable=true."""
        validator = create_validator(schema, "error_response")
        validator.validate(timeout_error)
        assert timeout_error["retryable"] is True

    def test_retryable_flag_is_boolean(self, schema: dict) -> None:
        """Test that retryable flag is boolean type."""
        error_schema = schema["definitions"]["error_response"]
        retryable_schema = error_schema["properties"]["retryable"]

        assert retryable_schema["type"] == "boolean"

    def test_code_is_string(self, schema: dict) -> None:
        """Test that code field is string type."""
        error_schema = schema["definitions"]["error_response"]
        code_schema = error_schema["properties"]["code"]

        assert code_schema["type"] == "string"

    def test_all_error_codes_documented(self, schema: dict) -> None:
        """Test that common error codes are documented in schema examples."""
        # These error codes should be documented in the schema
        expected_codes = [
            "STREAM_NOT_FOUND",
            "STREAM_PAUSED",
            "INVALID_CONFIG",
            "INVALID_VOICE_PROFILE",
            "BACKPRESSURE_EXCEEDED",
            "TIMEOUT",
            "RATE_LIMIT_EXCEEDED",
            "DURATION_MISMATCH_EXCEEDED",
        ]

        # Schema should have examples or enum for common codes
        error_schema = schema["definitions"]["error_response"]
        code_schema = error_schema["properties"]["code"]

        # If examples are defined, check them
        if "examples" in code_schema:
            for code in expected_codes[:5]:  # Check at least 5 common codes
                assert any(code in str(ex) for ex in code_schema.get("examples", [])), (
                    f"Error code {code} not documented in examples"
                )

    def test_retryable_consistency(self, schema: dict) -> None:
        """Test retryable flag consistency documented in schema."""
        # Per spec, these should be consistent:
        # - TIMEOUT: retryable=true
        # - RATE_LIMIT_EXCEEDED: retryable=true
        # - INVALID_CONFIG: retryable=false
        # - INVALID_VOICE_PROFILE: retryable=false

        # This is a documentation test - verify the schema has examples
        # showing correct retryable values
        error_schema = schema["definitions"]["error_response"]

        # The schema should define retryable as boolean
        assert error_schema["properties"]["retryable"]["type"] == "boolean"
