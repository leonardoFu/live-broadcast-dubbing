# Media Service Dockerfile
# Uses Ubuntu 22.04 (Jammy) which has Python 3.10 as system Python
# This allows apt-installed python3-gi to work natively with our Python version
#
# GStreamer dependencies for spec 003 (Stream Worker Implementation)

FROM ubuntu:22.04

# Prevent interactive prompts during apt install
ENV DEBIAN_FRONTEND=noninteractive

WORKDIR /app

# Install Python 3.10, GStreamer, and PyGObject via apt
# Ubuntu 22.04 uses Python 3.10 as default, so python3-gi is compatible
RUN apt-get update && apt-get install -y --no-install-recommends \
    # Python 3.10 and pip
    python3 \
    python3-pip \
    python3-venv \
    # GStreamer runtime and plugins
    gstreamer1.0-tools \
    gstreamer1.0-plugins-base \
    gstreamer1.0-plugins-good \
    gstreamer1.0-plugins-bad \
    gstreamer1.0-plugins-ugly \
    gstreamer1.0-libav \
    # Python GObject bindings (system package - compatible with Python 3.10)
    python3-gi \
    python3-gi-cairo \
    gir1.2-gstreamer-1.0 \
    gir1.2-gst-plugins-base-1.0 \
    # Utilities
    wget \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Copy application source
COPY pyproject.toml ./
COPY src ./src

# Install Python dependencies (excluding PyGObject since we use system package)
# Use --break-system-packages since we're using system Python
RUN pip3 install --no-cache-dir --upgrade pip setuptools wheel && \
    pip3 install --no-cache-dir --break-system-packages \
    "fastapi>=0.104.0" \
    "uvicorn[standard]>=0.24.0" \
    "pydantic>=2.5.0" \
    "python-multipart>=0.0.6" \
    "httpx>=0.25.0" \
    "python-socketio[asyncio]>=5.0" \
    "prometheus_client>=0.19.0" && \
    pip3 install --no-cache-dir --break-system-packages --no-deps -e .

# Verify GStreamer Python bindings work
RUN python3 -c "import gi; gi.require_version('Gst', '1.0'); from gi.repository import Gst; print('GStreamer OK')"

# Set Python path
ENV PYTHONPATH=/app/src

# Expose port
EXPOSE 8080

# Health check
HEALTHCHECK --interval=10s --timeout=5s --start-period=5s --retries=3 \
    CMD wget -q -O - http://localhost:8080/health || exit 1

# Run service
CMD ["python3", "-m", "uvicorn", "media_service.main:app", "--host", "0.0.0.0", "--port", "8080"]
