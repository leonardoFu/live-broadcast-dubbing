# STS Service (Speech-to-Speech Translation)

GPU-accelerated speech-to-speech translation service for live broadcast dubbing.

## Description

The STS (Speech-to-Speech) service provides real-time speech translation functionality:
- **ASR (Automatic Speech Recognition)** - Convert audio to text using Whisper
- **Translation** - Translate text to target language
- **TTS (Text-to-Speech)** - Synthesize translated text to speech

This service is designed to run on GPU infrastructure (NVIDIA CUDA) for optimal performance, with CPU fallback mode for development.

## GPU Requirements

### Production (Recommended)
- NVIDIA GPU with CUDA support
- CUDA 11.x or 12.x
- Minimum 8GB VRAM (16GB recommended for large models)
- NVIDIA driver version compatible with CUDA

### Development (CPU Fallback)
- The service can run on CPU for development/testing
- Performance will be significantly slower
- Some models may require reduced batch sizes

## Prerequisites

- Python 3.10.x (required, not compatible with 3.11+)
- NVIDIA GPU with CUDA (for production) or CPU (for development)
- CUDA toolkit (if using GPU)

## Setup

### 1. Install Python 3.10

```bash
# Ubuntu/Debian
sudo apt-get install python3.10 python3.10-venv

# macOS (using Homebrew)
brew install python@3.10
```

### 2. Install CUDA Dependencies (GPU mode only)

```bash
# Ubuntu/Debian
# Follow NVIDIA CUDA installation guide for your system
# https://developer.nvidia.com/cuda-downloads
```

### 3. Create Virtual Environment and Install

From the repository root:

```bash
make setup-sts
```

This will:
- Create `.venv-sts` virtual environment
- Install shared libraries (`dubbing-common`, `dubbing-contracts`)
- Install `sts-service` package with development dependencies

### 4. Activate Virtual Environment

```bash
source .venv-sts/bin/activate
```

## Development Workflow

### Running Tests in CPU Fallback Mode

```bash
# Run all tests for this service (CPU mode)
pytest apps/sts-service/tests/ -v

# Run only unit tests (fast, mocked models)
pytest apps/sts-service/tests/unit/ -m unit -v

# Run integration tests (with model loading)
pytest apps/sts-service/tests/integration/ -m integration -v

# Run with coverage report
pytest apps/sts-service/tests/ --cov=sts_service --cov-report=html
```

### Code Quality

```bash
# Format code
make fmt

# Lint code
make lint

# Type checking
make typecheck
```

### Local Development

1. Activate the virtual environment
2. Make code changes in `src/sts_service/`
3. Run unit tests (fast, mocked models)
4. Run integration tests (slower, loads models)
5. Test with sample audio files

## Project Structure

```
apps/sts-service/
├── src/
│   └── sts_service/
│       ├── __init__.py
│       ├── asr/                # Automatic Speech Recognition
│       │   └── __init__.py
│       ├── translation/        # Text translation
│       │   └── __init__.py
│       └── tts/                # Text-to-Speech synthesis
│           └── __init__.py
├── tests/
│   ├── unit/                   # Fast, mocked model tests
│   ├── integration/            # Real model loading tests
│   └── conftest.py             # Shared test fixtures
├── pyproject.toml              # Package metadata and dependencies
└── README.md                   # This file
```

## Dependencies

### Core Dependencies
- `faster-whisper` - Optimized Whisper ASR inference
- `transformers` - Translation models
- `fastapi` - REST API framework
- `uvicorn` - ASGI server
- `torch` - PyTorch framework
- `numpy<2.0` - Numerical computations

### Shared Libraries
- `dubbing-common` - Shared utilities and configurations
- `dubbing-contracts` - API contracts and event schemas

### Development Dependencies
- `pytest>=7.0` - Testing framework
- `mypy>=1.0` - Type checking
- `ruff>=0.1.0` - Linting and formatting
- `httpx` - HTTP testing for FastAPI

## Configuration

### Environment Variables

- `CUDA_VISIBLE_DEVICES` - GPU device selection (e.g., "0,1")
- `STS_CPU_ONLY` - Force CPU mode (set to "1" for development)

### Model Configuration

Model selection and parameters are managed via configuration files (to be added in implementation phase).

## Performance Considerations

### GPU Mode (Production)
- ASR: ~50-100ms latency per second of audio
- Translation: ~10-20ms latency
- TTS: ~100-200ms latency per second of audio

### CPU Mode (Development)
- Expect 10-20x slower processing times
- Suitable for testing logic, not performance testing

## API Endpoints

REST API endpoints (to be implemented):
- `POST /asr/transcribe` - Audio to text
- `POST /translate` - Text translation
- `POST /tts/synthesize` - Text to speech
- `POST /sts/process` - End-to-end STS pipeline

## Related Services

- `stream-infrastructure` - Audio stream processing service (CPU-based)
- See repository root README.md for monorepo overview

## Troubleshooting

### CUDA Out of Memory
- Reduce batch size in configuration
- Use smaller model variants
- Ensure no other GPU processes are running

### Model Download Issues
- Models are downloaded automatically on first use
- Ensure internet connection for initial setup
- Models are cached in `~/.cache/huggingface/`

## License

(Add license information as needed)
