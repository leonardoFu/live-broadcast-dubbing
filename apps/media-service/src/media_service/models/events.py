"""
Data models for MediaMTX hook events.

These models follow the contract schema defined in:
specs/001-mediamtx-integration/contracts/hook-events.json
"""

from datetime import datetime
from typing import Optional
from uuid import uuid4

from pydantic import BaseModel, Field, field_validator


class HookEvent(BaseModel):
    """Base model for MediaMTX hook events."""

    path: str = Field(
        ...,
        description="Stream path in MediaMTX (e.g., live/stream123/in)",
        pattern=r"^live/[a-zA-Z0-9_-]+/(in|out)$",
    )
    query: Optional[str] = Field(
        default=None, description="Query string from RTMP URL (e.g., lang=es)"
    )
    source_type: str = Field(
        ...,
        alias="sourceType",
        description="Source protocol type",
    )
    source_id: str = Field(
        ..., alias="sourceId", description="Unique identifier for the source connection"
    )
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Event timestamp")
    correlation_id: str = Field(
        default_factory=lambda: str(uuid4()), description="Unique correlation ID for tracing"
    )

    @field_validator("source_type")
    @classmethod
    def validate_source_type(cls, v: str) -> str:
        """Validate source type is one of the allowed protocols."""
        allowed_types = ["rtmp", "rtsp", "webrtc"]
        if v not in allowed_types:
            raise ValueError(f"source_type must be one of {allowed_types}, got {v}")
        return v

    @field_validator("path")
    @classmethod
    def validate_path_format(cls, v: str) -> str:
        """Validate path matches the expected format."""
        import re

        pattern = r"^live/[a-zA-Z0-9_-]+/(in|out)$"
        if not re.match(pattern, v):
            raise ValueError(
                f"path must match pattern 'live/<streamId>/(in|out)', got {v}"
            )
        return v

    def extract_stream_id(self) -> str:
        """Extract stream ID from path."""
        # Path format: live/<streamId>/(in|out)
        parts = self.path.split("/")
        if len(parts) >= 2:
            return parts[1]
        return ""

    def extract_direction(self) -> str:
        """Extract direction (in/out) from path."""
        # Path format: live/<streamId>/(in|out)
        parts = self.path.split("/")
        if len(parts) >= 3:
            return parts[2]
        return ""

    class Config:
        """Pydantic model configuration."""

        populate_by_name = True
        json_schema_extra = {
            "example": {
                "path": "live/stream123/in",
                "query": "lang=es",
                "sourceType": "rtmp",
                "sourceId": "1",
            }
        }


class ReadyEvent(HookEvent):
    """Event triggered when a stream becomes available."""

    event_type: str = Field(default="ready", description="Event type identifier")


class NotReadyEvent(HookEvent):
    """Event triggered when a stream becomes unavailable."""

    event_type: str = Field(default="not-ready", description="Event type identifier")
