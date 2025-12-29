"""Unit tests for authentication in Echo STS Service.

Tests API key validation and authentication middleware behavior.
"""

import pytest
from sts_service.echo.auth import (
    AuthenticationError,
    authenticate_connection,
    validate_api_key,
)
from sts_service.echo.config import EchoConfig, reset_config, set_config


@pytest.fixture(autouse=True)
def reset_config_fixture():
    """Reset config before and after each test."""
    reset_config()
    yield
    reset_config()


class TestValidateApiKey:
    """Tests for validate_api_key function."""

    def test_authentication_valid_key(self):
        """Valid API key should return True."""
        config = EchoConfig(api_key="test-key-12345", require_auth=True)
        set_config(config)

        assert validate_api_key("test-key-12345") is True

    def test_authentication_invalid_key(self):
        """Invalid API key should return False."""
        config = EchoConfig(api_key="test-key-12345", require_auth=True)
        set_config(config)

        assert validate_api_key("wrong-key") is False

    def test_authentication_missing_key(self):
        """Missing (None or empty) key should return False."""
        config = EchoConfig(api_key="test-key-12345", require_auth=True)
        set_config(config)

        assert validate_api_key(None) is False
        assert validate_api_key("") is False

    def test_authentication_disabled(self):
        """When auth is disabled, any key should be accepted."""
        config = EchoConfig(api_key="test-key-12345", require_auth=False)
        set_config(config)

        assert validate_api_key("any-key") is True
        assert validate_api_key(None) is True
        assert validate_api_key("") is True


class TestAuthenticateConnection:
    """Tests for authenticate_connection function."""

    def test_authenticate_valid_token(self):
        """Valid token in auth dict should succeed."""
        config = EchoConfig(api_key="valid-token", require_auth=True)
        set_config(config)

        # Should not raise
        authenticate_connection({"token": "valid-token"})

    def test_authenticate_invalid_token(self):
        """Invalid token should raise AuthenticationError."""
        config = EchoConfig(api_key="valid-token", require_auth=True)
        set_config(config)

        with pytest.raises(AuthenticationError) as exc_info:
            authenticate_connection({"token": "invalid-token"})

        assert exc_info.value.error_code == "AUTH_FAILED"
        assert "invalid" in exc_info.value.message.lower()

    def test_authenticate_missing_token(self):
        """Missing token should raise AuthenticationError."""
        config = EchoConfig(api_key="valid-token", require_auth=True)
        set_config(config)

        with pytest.raises(AuthenticationError) as exc_info:
            authenticate_connection({})

        assert exc_info.value.error_code == "AUTH_FAILED"

    def test_authenticate_missing_auth_dict(self):
        """None auth dict should raise AuthenticationError."""
        config = EchoConfig(api_key="valid-token", require_auth=True)
        set_config(config)

        with pytest.raises(AuthenticationError) as exc_info:
            authenticate_connection(None)

        assert exc_info.value.error_code == "AUTH_FAILED"

    def test_authenticate_disabled_auth(self):
        """When auth is disabled, any auth should pass."""
        config = EchoConfig(api_key="valid-token", require_auth=False)
        set_config(config)

        # All these should not raise
        authenticate_connection(None)
        authenticate_connection({})
        authenticate_connection({"token": "anything"})


class TestAuthenticationError:
    """Tests for AuthenticationError class."""

    def test_error_attributes(self):
        """AuthenticationError should have correct attributes."""
        error = AuthenticationError("Test message", "TEST_CODE")

        assert str(error) == "Test message"
        assert error.message == "Test message"
        assert error.error_code == "TEST_CODE"

    def test_default_error_code(self):
        """Default error code should be AUTH_FAILED."""
        error = AuthenticationError("Test message")

        assert error.error_code == "AUTH_FAILED"
