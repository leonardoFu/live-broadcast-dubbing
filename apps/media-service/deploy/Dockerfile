# Media Service Dockerfile
# Multi-stage build for production-ready image with GStreamer support
#
# GStreamer dependencies added for spec 003 (Stream Worker Implementation)

FROM python:3.10-slim as builder

WORKDIR /build

# Install build dependencies including GStreamer development packages
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    pkg-config \
    libcairo2-dev \
    libgirepository1.0-dev \
    gir1.2-gstreamer-1.0 \
    gir1.2-gst-plugins-base-1.0 \
    && rm -rf /var/lib/apt/lists/*

# Copy application source
COPY pyproject.toml ./
COPY src ./src

# Install dependencies
RUN pip install --no-cache-dir --upgrade pip setuptools wheel && \
    pip install --no-cache-dir -e .

# Production image
FROM python:3.10-slim

WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /usr/local/lib/python3.10/site-packages /usr/local/lib/python3.10/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin
COPY --from=builder /build/src /app/src

# Install runtime dependencies including GStreamer
# Per spec 003: GStreamer 1.x with plugins for RTSP/RTMP/FLV processing
RUN apt-get update && apt-get install -y --no-install-recommends \
    wget \
    # GStreamer core and Python bindings
    gstreamer1.0-tools \
    gstreamer1.0-plugins-base \
    gstreamer1.0-plugins-good \
    gstreamer1.0-plugins-bad \
    gstreamer1.0-plugins-ugly \
    gstreamer1.0-libav \
    # GObject introspection for PyGObject
    python3-gi \
    gir1.2-gstreamer-1.0 \
    gir1.2-gst-plugins-base-1.0 \
    # GStreamer app plugin for appsrc/appsink
    gstreamer1.0-plugins-base-apps \
    && rm -rf /var/lib/apt/lists/*

# Set Python path
ENV PYTHONPATH=/app/src

# Expose port
EXPOSE 8080

# Health check
HEALTHCHECK --interval=10s --timeout=5s --start-period=5s --retries=3 \
    CMD wget -q -O - http://localhost:8080/health || exit 1

# Run service
CMD ["uvicorn", "media_service.main:app", "--host", "0.0.0.0", "--port", "8080"]
