# Dubbing Contracts Library

API contracts and event schemas for live broadcast dubbing services.

## Description

The `dubbing-contracts` library defines all contracts and schemas used for communication between services:
- REST API request/response schemas
- Event schemas for pub/sub messaging
- Data transfer objects (DTOs)
- Validation rules and constraints

This library ensures type safety and contract consistency across the entire system using Pydantic models.

## Installation

### For Development (Editable Mode)

When developing services that depend on this library:

```bash
# From repository root, after creating a virtual environment
pip install -e libs/contracts
```

### For Other Packages in Monorepo

This library is automatically installed when you run:
- `make setup-stream` (for stream-infrastructure service)
- `make setup-sts` (for sts-service)

## Usage Examples

### API Request/Response Models

```python
from dubbing_contracts.api.sts import TranscribeRequest, TranscribeResponse

# Client code (sending request)
request = TranscribeRequest(
    audio_data=audio_bytes,
    language="en",
    sample_rate=16000
)

# Server code (sending response)
response = TranscribeResponse(
    text="Hello world",
    confidence=0.95,
    language="en"
)
```

### Event Schemas

```python
from dubbing_contracts.events.stream import AudioFragmentProcessed

# Publish event
event = AudioFragmentProcessed(
    fragment_id="frag_123",
    timestamp_ms=1234567890,
    duration_ms=500,
    sample_rate=48000,
    channels=2,
    status="completed"
)

# Event serialization
event_json = event.model_dump_json()
```

### Data Validation

```python
from dubbing_contracts.models.audio import AudioMetadata
from pydantic import ValidationError

# Valid data
metadata = AudioMetadata(
    sample_rate=48000,
    channels=2,
    bit_depth=16,
    codec="pcm"
)

# Invalid data raises ValidationError
try:
    invalid = AudioMetadata(
        sample_rate=-1,  # Invalid: must be positive
        channels=0,      # Invalid: must be 1 or 2
    )
except ValidationError as e:
    print(e)
```

## Development Setup

### 1. Create Virtual Environment

```bash
# From repository root
python3.10 -m venv .venv
source .venv/bin/activate
```

### 2. Install with Development Dependencies

```bash
pip install -e "libs/contracts[dev]"
```

### 3. Run Tests

```bash
# Run all tests for this library
pytest libs/contracts/tests/ -v

# Run only unit tests (schema validation tests)
pytest libs/contracts/tests/unit/ -m unit -v

# Run with coverage
pytest libs/contracts/tests/ --cov=dubbing_contracts --cov-report=html
```

### 4. Code Quality

```bash
# Format code
make fmt

# Lint code
make lint

# Type checking
make typecheck
```

## Project Structure

```
libs/contracts/
├── src/
│   └── dubbing_contracts/
│       ├── __init__.py
│       ├── api/                # REST API schemas (to be implemented)
│       │   ├── __init__.py
│       │   ├── sts.py          # STS service API contracts
│       │   └── stream.py       # Stream service API contracts
│       ├── events/             # Event schemas (to be implemented)
│       │   ├── __init__.py
│       │   ├── stream.py       # Stream processing events
│       │   └── sts.py          # STS processing events
│       └── models/             # Shared data models (to be implemented)
│           ├── __init__.py
│           ├── audio.py        # Audio metadata models
│           └── translation.py  # Translation models
├── tests/
│   ├── unit/                   # Schema validation tests
│   │   └── __init__.py
│   └── conftest.py             # Shared test fixtures
├── pyproject.toml              # Package metadata and dependencies
└── README.md                   # This file
```

## Dependencies

### Core Dependencies
- `pydantic>=2.0` - Data validation and schema definition

### Development Dependencies
- `pytest>=7.0` - Testing framework
- `mypy>=1.0` - Type checking
- `ruff>=0.1.0` - Linting and formatting

## Design Principles

### 1. Single Source of Truth
All contracts are defined once in this library and imported by services. Never duplicate contract definitions.

### 2. Backward Compatibility
Contract changes must maintain backward compatibility. Use versioning for breaking changes.

### 3. Strict Validation
Use Pydantic's strict mode and explicit field validation to catch errors early.

### 4. Immutability
Contract models should be immutable (use `frozen=True` for Pydantic models where appropriate).

### 5. Documentation
All fields must have descriptions explaining their purpose, constraints, and valid values.

## Contract Testing

This library includes contract tests to ensure:
- All schemas are valid and can be serialized/deserialized
- Field constraints are enforced (e.g., positive integers, valid enums)
- Required fields are present
- Optional fields have sensible defaults

Example contract test:

```python
def test_transcribe_request_valid():
    """Test valid TranscribeRequest creation"""
    request = TranscribeRequest(
        audio_data=b"audio_bytes",
        language="en",
        sample_rate=16000
    )
    assert request.language == "en"
    assert request.sample_rate == 16000

def test_transcribe_request_invalid_sample_rate():
    """Test invalid sample rate raises ValidationError"""
    with pytest.raises(ValidationError):
        TranscribeRequest(
            audio_data=b"audio_bytes",
            language="en",
            sample_rate=-1  # Invalid
        )
```

## Versioning Strategy

### API Contracts
- Use version prefixes in module names (e.g., `api.v1.sts`, `api.v2.sts`)
- Maintain old versions until all clients migrate
- Document deprecation timeline

### Event Schemas
- Include schema version in event payload
- Support multiple schema versions simultaneously during transitions
- Use event transformation/migration for version upgrades

## Usage in Services

### stream-infrastructure Service
- Imports: `events.stream`, `models.audio`
- Uses: Event publishing for fragment processing status
- Uses: Audio metadata validation

### sts-service
- Imports: `api.sts`, `events.sts`, `models.audio`, `models.translation`
- Uses: REST API request/response validation
- Uses: Event publishing for STS processing status

## Breaking Changes Policy

Breaking changes require:
1. Major version bump (e.g., 0.1.0 → 1.0.0)
2. Migration guide in CHANGELOG
3. Deprecation warnings in previous version (if possible)
4. Coordinated deployment of all affected services

## Related Libraries

- `dubbing-common` - Shared utilities and configurations
- See repository root README.md for monorepo overview

## Contributing

When adding new contracts:
1. Define schemas using Pydantic models
2. Add comprehensive field descriptions and examples
3. Write contract tests to validate all constraints
4. Document usage examples in this README
5. Consider backward compatibility impact
6. Update CHANGELOG for any API changes

## Examples

### Complete STS Request/Response Flow

```python
from dubbing_contracts.api.sts import STSRequest, STSResponse

# Client creates request
request = STSRequest(
    audio_data=audio_bytes,
    source_language="en",
    target_language="es",
    sample_rate=48000
)

# Validate and serialize for HTTP
request_json = request.model_dump_json()

# Server receives, validates, and processes
received_request = STSRequest.model_validate_json(request_json)

# Server creates response
response = STSResponse(
    translated_audio=translated_bytes,
    source_text="Hello world",
    translated_text="Hola mundo",
    processing_time_ms=250
)

# Serialize response
response_json = response.model_dump_json()
```

## License

(Add license information as needed)
