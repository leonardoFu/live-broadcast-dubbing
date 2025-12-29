"""Integration tests for Echo STS Service.

These tests use real Socket.IO connections to verify the complete
connection lifecycle, fragment round-trip, and error handling.

Test modules:
- test_connection_lifecycle: Connection and stream lifecycle tests
- test_fragment_echo: Fragment echo round-trip tests
- test_backpressure: Backpressure simulation tests
- test_error_simulation: Error injection tests
"""
