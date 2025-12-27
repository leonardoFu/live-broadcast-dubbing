# Dubbing Common Library

Shared utilities and common functionality for live broadcast dubbing services.

## Description

The `dubbing-common` library provides shared utilities used across all services in the monorepo:
- Configuration management and validation
- Logging and observability utilities
- Audio processing helpers
- Error handling and custom exceptions
- Shared constants and enumerations

This library is designed to reduce code duplication and ensure consistent behavior across services.

## Installation

### For Development (Editable Mode)

When developing services that depend on this library:

```bash
# From repository root, after creating a virtual environment
pip install -e libs/common
```

### For Other Packages in Monorepo

This library is automatically installed when you run:
- `make setup-stream` (for media-service service)
- `make setup-sts` (for sts-service)

## Usage Examples

### Configuration Management

```python
from dubbing_common.config import load_config, ConfigValidator

# Load YAML configuration
config = load_config("config/service.yaml")

# Validate configuration schema
validator = ConfigValidator(config)
validator.validate()
```

### Logging Utilities

```python
from dubbing_common.logging import get_logger

# Get structured logger
logger = get_logger(__name__)
logger.info("Processing audio fragment", fragment_id=123, duration_ms=500)
```

### Audio Helpers

```python
from dubbing_common.audio import AudioBuffer, resample_audio

# Create audio buffer
buffer = AudioBuffer(sample_rate=48000, channels=2)
buffer.write(audio_data)

# Resample audio to target rate
resampled = resample_audio(audio_data, source_rate=48000, target_rate=16000)
```

### Error Handling

```python
from dubbing_common.exceptions import AudioProcessingError, ConfigurationError

# Raise domain-specific exceptions
raise AudioProcessingError("Failed to decode audio", fragment_id=123)
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
pip install -e "libs/common[dev]"
```

### 3. Run Tests

```bash
# Run all tests for this library
pytest libs/common/tests/ -v

# Run only unit tests
pytest libs/common/tests/unit/ -m unit -v

# Run with coverage
pytest libs/common/tests/ --cov=dubbing_common --cov-report=html
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
libs/common/
├── src/
│   └── dubbing_common/
│       ├── __init__.py
│       ├── config.py           # Configuration utilities (to be implemented)
│       ├── logging.py          # Logging utilities (to be implemented)
│       ├── audio.py            # Audio processing helpers (to be implemented)
│       └── exceptions.py       # Custom exceptions (to be implemented)
├── tests/
│   ├── unit/                   # Fast, isolated tests
│   │   └── __init__.py
│   └── conftest.py             # Shared test fixtures
├── pyproject.toml              # Package metadata and dependencies
└── README.md                   # This file
```

## Dependencies

### Core Dependencies
- `numpy<2.0` - Numerical computations for audio processing
- `pyyaml` - YAML configuration file parsing
- `pydantic>=2.0` - Configuration validation and data models
- `rich` - Enhanced terminal output and logging

### Development Dependencies
- `pytest>=7.0` - Testing framework
- `mypy>=1.0` - Type checking
- `ruff>=0.1.0` - Linting and formatting

## Design Principles

### 1. No Service-Specific Logic
This library should contain only utilities that are genuinely shared across multiple services. Service-specific logic belongs in the service packages.

### 2. Minimal Dependencies
Keep dependencies minimal to avoid version conflicts when used by different services.

### 3. Backward Compatibility
Changes to this library affect all services. Follow semantic versioning and maintain backward compatibility when possible.

### 4. Comprehensive Testing
Aim for high test coverage (>90%) as bugs in common utilities affect all services.

## Version Management

This library follows semantic versioning:
- **MAJOR** - Breaking changes to public API
- **MINOR** - New features, backward compatible
- **PATCH** - Bug fixes, backward compatible

Current version: `0.1.0` (initial development)

## Usage in Services

### media-service
- Configuration loading and validation
- Audio buffer management
- Logging utilities

### sts-service
- Configuration management
- Shared error types
- Logging utilities

## Related Libraries

- `dubbing-contracts` - API contracts and event schemas
- See repository root README.md for monorepo overview

## Contributing

When adding new utilities:
1. Ensure the utility is genuinely needed by multiple services
2. Write comprehensive unit tests (coverage >90%)
3. Add type hints for all public APIs
4. Document usage with docstrings and examples
5. Update this README with usage examples

## License

(Add license information as needed)
