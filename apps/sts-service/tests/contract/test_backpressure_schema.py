"""Contract tests for backpressure event schema.

Test T009: Validate backpressure event payload structure.
This test follows TDD - it MUST FAIL initially until schema is created.
"""

import json
from pathlib import Path

import jsonschema
from jsonschema import Draft7Validator, RefResolver
import pytest

# Schema file paths (relative to repo root - worktree is at sts-service-main)
# Path: apps/sts-service/tests/contract/test_backpressure_schema.py
# Need to go up: contract -> tests -> sts-service -> apps -> worktree-root -> specs
CONTRACTS_DIR = Path(__file__).parent.parent.parent.parent.parent / "specs" / "021-full-sts-service" / "contracts"


def create_validator(schema: dict, definition_name: str) -> Draft7Validator:
    """Create a validator for a specific definition with proper $ref resolution."""
    resolver = RefResolver.from_schema(schema)
    definition_schema = schema["definitions"][definition_name]
    return Draft7Validator(definition_schema, resolver=resolver)


class TestBackpressureSchema:
    """T009: Contract test for backpressure event schema."""

    @pytest.fixture
    def schema(self) -> dict:
        """Load backpressure schema from JSON file."""
        schema_path = CONTRACTS_DIR / "backpressure-schema.json"
        with open(schema_path) as f:
            return json.load(f)

    @pytest.fixture
    def valid_backpressure_payload(self) -> dict:
        """Sample valid backpressure event payload."""
        return {
            "stream_id": "stream-abc-123",
            "severity": "medium",
            "action": "slow_down",
            "current_inflight": 5,
            "max_inflight": 3,
            "threshold_exceeded": "medium"
        }

    def test_valid_backpressure_payload(self, schema: dict, valid_backpressure_payload: dict) -> None:
        """Validate that a correct backpressure payload passes schema validation."""
        validator = create_validator(schema, "backpressure")
        validator.validate(valid_backpressure_payload)

    def test_backpressure_required_fields(self, schema: dict) -> None:
        """Test that all required fields are enforced."""
        required_fields = [
            "stream_id", "severity", "action",
            "current_inflight", "max_inflight", "threshold_exceeded"
        ]
        backpressure_schema = schema["definitions"]["backpressure"]

        assert "required" in backpressure_schema
        for field in required_fields:
            assert field in backpressure_schema["required"], f"Missing required field: {field}"

    def test_severity_enum(self, schema: dict) -> None:
        """Test severity enum: low, medium, high."""
        backpressure_schema = schema["definitions"]["backpressure"]
        severity_schema = backpressure_schema["properties"]["severity"]

        assert "enum" in severity_schema
        expected_severities = ["low", "medium", "high"]
        for severity in expected_severities:
            assert severity in severity_schema["enum"], f"Missing severity: {severity}"

    def test_action_enum(self, schema: dict) -> None:
        """Test action enum: none, slow_down, pause."""
        backpressure_schema = schema["definitions"]["backpressure"]
        action_schema = backpressure_schema["properties"]["action"]

        assert "enum" in action_schema
        expected_actions = ["none", "slow_down", "pause"]
        for action in expected_actions:
            assert action in action_schema["enum"], f"Missing action: {action}"

    def test_inflight_counts_are_integers(self, schema: dict) -> None:
        """Test that current_inflight and max_inflight are integers."""
        backpressure_schema = schema["definitions"]["backpressure"]

        assert backpressure_schema["properties"]["current_inflight"]["type"] == "integer"
        assert backpressure_schema["properties"]["max_inflight"]["type"] == "integer"

    def test_low_severity_payload(self, schema: dict) -> None:
        """Validate low severity backpressure (normal operation)."""
        low_severity_payload = {
            "stream_id": "stream-abc-123",
            "severity": "low",
            "action": "none",
            "current_inflight": 2,
            "max_inflight": 3,
            "threshold_exceeded": None
        }
        # threshold_exceeded can be null for low severity
        validator = create_validator(schema, "backpressure")
        validator.validate(low_severity_payload)

    def test_high_severity_payload(self, schema: dict) -> None:
        """Validate high severity backpressure (pause recommended)."""
        high_severity_payload = {
            "stream_id": "stream-abc-123",
            "severity": "high",
            "action": "pause",
            "current_inflight": 9,
            "max_inflight": 3,
            "threshold_exceeded": "high"
        }
        validator = create_validator(schema, "backpressure")
        validator.validate(high_severity_payload)
