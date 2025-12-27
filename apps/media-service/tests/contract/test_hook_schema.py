"""
Contract tests for MediaMTX hook event schemas.

Validates hook event payloads match the contract schema in:
specs/001-mediamtx-integration/contracts/hook-events.json
"""

import pytest
from fastapi.testclient import TestClient

from media_service.main import app
from media_service.models.events import HookEvent, NotReadyEvent, ReadyEvent


@pytest.mark.contract
class TestHookEventReadySchema:
    """Test ready event schema validation."""

    def test_ready_event_valid_payload(self, client: TestClient) -> None:
        """Validate POST /v1/mediamtx/events/ready accepts valid payload."""
        payload = {
            "path": "live/test-stream/in",
            "query": "lang=es",
            "sourceType": "rtmp",
            "sourceId": "1",
        }

        response = client.post("/v1/mediamtx/events/ready", json=payload)

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["stream_id"] == "test-stream"

    def test_ready_event_required_fields(self, client: TestClient) -> None:
        """Validate required fields: path, sourceType, sourceId."""
        payload = {
            "path": "live/stream123/in",
            "sourceType": "rtmp",
            "sourceId": "2",
        }

        response = client.post("/v1/mediamtx/events/ready", json=payload)

        assert response.status_code == 200

    def test_ready_event_optional_query_field(self, client: TestClient) -> None:
        """Validate optional fields: query."""
        # Query included
        payload_with_query = {
            "path": "live/stream123/in",
            "query": "lang=es&quality=hd",
            "sourceType": "rtmp",
            "sourceId": "1",
        }

        response = client.post("/v1/mediamtx/events/ready", json=payload_with_query)
        assert response.status_code == 200

        # Query omitted
        payload_without_query = {
            "path": "live/stream123/in",
            "sourceType": "rtmp",
            "sourceId": "1",
        }

        response = client.post("/v1/mediamtx/events/ready", json=payload_without_query)
        assert response.status_code == 200

    def test_ready_event_path_pattern_validation(self, client: TestClient) -> None:
        """Validate path pattern: live/<streamId>/(in|out)."""
        # Valid paths
        valid_paths = [
            "live/test123/in",
            "live/test-stream/in",
            "live/my_stream/in",
            "live/stream123/out",
        ]

        for path in valid_paths:
            payload = {
                "path": path,
                "sourceType": "rtmp",
                "sourceId": "1",
            }
            response = client.post("/v1/mediamtx/events/ready", json=payload)
            assert response.status_code == 200, f"Valid path '{path}' rejected"

        # Invalid paths
        invalid_paths = [
            "invalid/path",
            "live/test",
            "live/test/invalid",
            "test/stream/in",
        ]

        for path in invalid_paths:
            payload = {
                "path": path,
                "sourceType": "rtmp",
                "sourceId": "1",
            }
            response = client.post("/v1/mediamtx/events/ready", json=payload)
            assert response.status_code == 422, f"Invalid path '{path}' accepted"

    def test_ready_event_missing_required_field(self, client: TestClient) -> None:
        """Validate error when required field is missing."""
        # Missing path
        payload_missing_path = {
            "sourceType": "rtmp",
            "sourceId": "1",
        }
        response = client.post("/v1/mediamtx/events/ready", json=payload_missing_path)
        assert response.status_code == 422

        # Missing sourceType
        payload_missing_source_type = {
            "path": "live/test/in",
            "sourceId": "1",
        }
        response = client.post("/v1/mediamtx/events/ready", json=payload_missing_source_type)
        assert response.status_code == 422

        # Missing sourceId
        payload_missing_source_id = {
            "path": "live/test/in",
            "sourceType": "rtmp",
        }
        response = client.post("/v1/mediamtx/events/ready", json=payload_missing_source_id)
        assert response.status_code == 422


@pytest.mark.contract
class TestHookEventNotReadySchema:
    """Test not-ready event schema validation."""

    def test_not_ready_event_valid_payload(self, client: TestClient) -> None:
        """Validate POST /v1/mediamtx/events/not-ready accepts valid payload."""
        payload = {
            "path": "live/test-stream/in",
            "sourceType": "rtmp",
            "sourceId": "1",
        }

        response = client.post("/v1/mediamtx/events/not-ready", json=payload)

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["stream_id"] == "test-stream"

    def test_not_ready_event_matches_ready_schema(self, client: TestClient) -> None:
        """Validate not-ready event has same schema as ready event."""
        payload = {
            "path": "live/stream123/in",
            "query": "lang=es",
            "sourceType": "rtmp",
            "sourceId": "1",
        }

        response = client.post("/v1/mediamtx/events/not-ready", json=payload)
        assert response.status_code == 200


@pytest.mark.contract
class TestHookEventDataModel:
    """Test Pydantic data model validation."""

    def test_hook_event_model_validation(self) -> None:
        """Test HookEvent model validates correctly."""
        # Valid event
        event_data = {
            "path": "live/test/in",
            "query": "lang=es",
            "sourceType": "rtmp",
            "sourceId": "1",
        }
        event = HookEvent(**event_data)
        assert event.path == "live/test/in"
        assert event.query == "lang=es"
        assert event.source_type == "rtmp"
        assert event.source_id == "1"

    def test_hook_event_model_extract_stream_id(self) -> None:
        """Test stream ID extraction from path."""
        event = HookEvent(
            path="live/my-stream-123/in",
            sourceType="rtmp",
            sourceId="1",
        )
        assert event.extract_stream_id() == "my-stream-123"

    def test_hook_event_model_extract_direction(self) -> None:
        """Test direction extraction from path."""
        event_in = HookEvent(
            path="live/test/in",
            sourceType="rtmp",
            sourceId="1",
        )
        assert event_in.extract_direction() == "in"

        event_out = HookEvent(
            path="live/test/out",
            sourceType="rtmp",
            sourceId="1",
        )
        assert event_out.extract_direction() == "out"

    def test_hook_event_model_invalid_source_type(self) -> None:
        """Test invalid source type is rejected."""
        with pytest.raises(ValueError, match="source_type must be one of"):
            HookEvent(
                path="live/test/in",
                sourceType="invalid",
                sourceId="1",
            )

    def test_hook_event_model_invalid_path_format(self) -> None:
        """Test invalid path format is rejected."""
        with pytest.raises(ValueError, match="path must match pattern"):
            HookEvent(
                path="invalid/path/format",
                sourceType="rtmp",
                sourceId="1",
            )

    def test_ready_event_model(self) -> None:
        """Test ReadyEvent model has correct event_type."""
        event = ReadyEvent(
            path="live/test/in",
            sourceType="rtmp",
            sourceId="1",
        )
        assert event.event_type == "ready"

    def test_not_ready_event_model(self) -> None:
        """Test NotReadyEvent model has correct event_type."""
        event = NotReadyEvent(
            path="live/test/in",
            sourceType="rtmp",
            sourceId="1",
        )
        assert event.event_type == "not-ready"
