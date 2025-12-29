"""Pydantic models for error payloads and error simulation.

Implements error event structure and error simulation configuration
as defined in spec 016 section 8.1.
"""

from typing import Any, Literal

from pydantic import BaseModel, Field

# Error codes from spec 016 section 8.1
ERROR_CODES = {
    "AUTH_FAILED": {"severity": "fatal", "retryable": False},
    "STREAM_NOT_FOUND": {"severity": "error", "retryable": False},
    "INVALID_CONFIG": {"severity": "error", "retryable": False},
    "FRAGMENT_TOO_LARGE": {"severity": "error", "retryable": False},
    "TIMEOUT": {"severity": "error", "retryable": True},
    "MODEL_ERROR": {"severity": "error", "retryable": True},
    "GPU_OOM": {"severity": "error", "retryable": True},
    "QUEUE_FULL": {"severity": "warning", "retryable": True},
    "INVALID_SEQUENCE": {"severity": "error", "retryable": False},
    "RATE_LIMIT": {"severity": "warning", "retryable": True},
}

ErrorCode = Literal[
    "AUTH_FAILED",
    "STREAM_NOT_FOUND",
    "INVALID_CONFIG",
    "FRAGMENT_TOO_LARGE",
    "TIMEOUT",
    "MODEL_ERROR",
    "GPU_OOM",
    "QUEUE_FULL",
    "INVALID_SEQUENCE",
    "RATE_LIMIT",
]

ErrorSeverity = Literal["warning", "error", "fatal"]


class ErrorPayload(BaseModel):
    """Error event payload.

    Matches spec 016 section 5.2 error structure.
    """

    error_id: str | None = Field(
        default=None,
        description="Unique error identifier",
    )
    stream_id: str | None = None
    fragment_id: str | None = None
    code: str = Field(
        description="Error code from spec 016 section 8.1",
    )
    message: str = Field(
        description="Human-readable description",
    )
    severity: ErrorSeverity = Field(default="error")
    retryable: bool = Field(default=False)
    metadata: dict[str, Any] | None = None

    @classmethod
    def from_error_code(
        cls,
        code: ErrorCode,
        message: str | None = None,
        stream_id: str | None = None,
        fragment_id: str | None = None,
        error_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> "ErrorPayload":
        """Create an error payload from a predefined error code.

        Args:
            code: Error code from spec 016.
            message: Optional custom message (defaults to code-based message).
            stream_id: Optional stream ID context.
            fragment_id: Optional fragment ID context.
            error_id: Optional unique error identifier.
            metadata: Optional additional metadata.

        Returns:
            ErrorPayload with appropriate severity and retryable flags.
        """
        error_info = ERROR_CODES.get(code, {"severity": "error", "retryable": False})
        default_messages = {
            "AUTH_FAILED": "Authentication failed: invalid API key",
            "STREAM_NOT_FOUND": "Stream not found: no active session",
            "INVALID_CONFIG": "Invalid configuration in stream:init",
            "FRAGMENT_TOO_LARGE": "Fragment exceeds 10MB size limit",
            "TIMEOUT": "Processing timeout exceeded",
            "MODEL_ERROR": "Model processing error",
            "GPU_OOM": "Out of GPU memory",
            "QUEUE_FULL": "Processing queue is full",
            "INVALID_SEQUENCE": "Invalid sequence number",
            "RATE_LIMIT": "Rate limit exceeded",
        }

        return cls(
            error_id=error_id,
            stream_id=stream_id,
            fragment_id=fragment_id,
            code=code,
            message=message or default_messages.get(code, f"Error: {code}"),
            severity=error_info["severity"],
            retryable=error_info["retryable"],
            metadata=metadata,
        )


class ErrorSimulationRule(BaseModel):
    """Single error simulation rule.

    Defines when and what error to inject during testing.
    """

    trigger: Literal["sequence_number", "fragment_id", "nth_fragment"] = Field(
        description="How to match fragments for error injection",
    )
    value: int | str = Field(
        description="Trigger value: sequence number, fragment ID, or N for nth fragment",
    )
    error_code: str = Field(
        description="Error code from spec 016 section 8.1",
    )
    error_message: str = Field(
        default="Simulated error",
        description="Human-readable error message",
    )
    retryable: bool = Field(
        default=True,
        description="Whether the error is retryable",
    )
    stage: Literal["asr", "translation", "tts"] | None = Field(
        default=None,
        description="Processing stage that failed",
    )

    def matches(
        self,
        sequence_number: int,
        fragment_id: str,
        fragment_count: int,
    ) -> bool:
        """Check if this rule matches the given fragment.

        Args:
            sequence_number: Fragment sequence number.
            fragment_id: Fragment unique ID.
            fragment_count: Total fragments processed in this session (1-based).

        Returns:
            True if the rule matches and error should be injected.
        """
        if self.trigger == "sequence_number":
            return sequence_number == self.value
        elif self.trigger == "fragment_id":
            return fragment_id == self.value
        elif self.trigger == "nth_fragment":
            # nth_fragment triggers on every Nth fragment (e.g., every 3rd)
            return fragment_count > 0 and fragment_count % int(self.value) == 0
        return False


class ErrorSimulationConfig(BaseModel):
    """Error simulation configuration sent via config:error_simulation.

    Allows tests to dynamically configure error injection without
    service restart.
    """

    enabled: bool = Field(
        default=False,
        description="Enable error simulation",
    )
    rules: list[ErrorSimulationRule] = Field(
        default_factory=list,
        description="List of error simulation rules",
    )

    def find_matching_rule(
        self,
        sequence_number: int,
        fragment_id: str,
        fragment_count: int,
    ) -> ErrorSimulationRule | None:
        """Find the first rule that matches the given fragment.

        Args:
            sequence_number: Fragment sequence number.
            fragment_id: Fragment unique ID.
            fragment_count: Total fragments processed in this session.

        Returns:
            The matching rule, or None if no rule matches.
        """
        if not self.enabled:
            return None

        for rule in self.rules:
            if rule.matches(sequence_number, fragment_id, fragment_count):
                return rule

        return None


class ConfigErrorSimulationAck(BaseModel):
    """Acknowledgment for config:error_simulation event."""

    status: Literal["accepted", "rejected"]
    rules_count: int = Field(ge=0)
    message: str | None = None
