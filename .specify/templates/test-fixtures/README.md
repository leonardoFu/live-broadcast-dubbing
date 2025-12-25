# Test Fixtures for TDD

This directory contains deterministic test fixtures for contract and integration testing (Constitution Principle II).

## STS Event Fixtures

`sts-events.py` provides mock STS events for testing without live services:

- `mock_fragment_data_event()` - Mock input fragment
- `mock_fragment_processed_event()` - Mock output fragment
- `mock_sts_api_success_response()` - Mock API success
- `mock_sts_api_error_response()` - Mock API failure

## Usage

```python
from .specify.templates.test_fixtures.sts_events import mock_fragment_data_event

def test_process_fragment():
    fragment = mock_fragment_data_event(fragment_id="test-001")
    result = process_fragment(fragment)
    assert result["status"] == "success"
```

## Adding New Fixtures

When adding new contracts (APIs, events), create corresponding fixtures here:
- Match production schema exactly
- Use deterministic data (no randomness)
- Document all fields
