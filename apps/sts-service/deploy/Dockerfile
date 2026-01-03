# STS Service Dockerfile for E2E Testing
# Provides real ASR (Whisper) + Translation + TTS (Coqui) processing

FROM python:3.10-slim

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    git \
    ffmpeg \
    curl \
    ca-certificates \
    cargo \
    rustc \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy package files
COPY pyproject.toml ./
COPY src ./src

# Install Python dependencies
RUN pip3 install --no-cache-dir --upgrade pip setuptools wheel && \
    pip3 install --no-cache-dir \
    "python-socketio[asyncio]>=5.0" \
    "uvicorn[standard]>=0.24.0" \
    "pydantic>=2.0" \
    "starlette>=0.27.0" \
    "openai-whisper>=20230314" \
    "deep-translator>=1.11.0" \
    "TTS>=0.21.0" \
    "torch>=2.0.0" \
    "torchaudio>=2.0.0" \
    "numpy<2.0.0" \
    "pydub>=0.25.1" \
    "soundfile>=0.12.0" \
    && pip3 install --no-cache-dir --no-deps -e .

# Expose Socket.IO port
EXPOSE 3000

# Health check
HEALTHCHECK --interval=5s --timeout=3s --start-period=30s --retries=10 \
    CMD curl -f http://localhost:3000/health || exit 1

# Run STS service (using echo service temporarily until real STS main.py is implemented)
# TODO: Replace with real STS service once main.py is created
CMD ["python", "-m", "sts_service.echo", "--host", "0.0.0.0", "--port", "3000"]
