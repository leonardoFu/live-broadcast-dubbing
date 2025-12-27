#!/usr/bin/env bash
#
# gstreamer-bypass.sh - Read stream via RTSP and republish via RTMP (passthrough)
#
# This script creates a bypass pipeline that:
# - Reads a stream from MediaMTX via RTSP
# - Re-publishes the same stream to a different path via RTMP
# - Uses TCP transport to avoid UDP packet loss in containers
#
# Usage:
#   ./gstreamer-bypass.sh [stream-id] [host]
#
# Arguments:
#   stream-id   - Stream identifier (default: test-stream)
#   host        - MediaMTX host (default: localhost)
#
# Examples:
#   # Bypass default test stream (in -> out)
#   ./gstreamer-bypass.sh
#
#   # Bypass specific stream
#   ./gstreamer-bypass.sh my-stream
#
#   # Bypass from Docker container
#   ./gstreamer-bypass.sh my-stream mediamtx
#
# Prerequisites:
#   - GStreamer 1.0 installed with:
#     - gst-plugins-good (rtpbin, flvmux)
#     - gst-plugins-bad (rtmpsink)
#     - gst-libav (avdec_h264, avdec_aac)
#   - Source stream must be active at rtsp://<host>:8554/live/<stream-id>/in
#   - MediaMTX running and accepting RTMP connections
#
# Data Flow:
#   RTSP input (live/<stream-id>/in) -> GStreamer bypass -> RTMP output (live/<stream-id>/out)
#

set -euo pipefail

# Default configuration
DEFAULT_STREAM_ID="test-stream"
DEFAULT_HOST="localhost"
RTSP_PORT="8554"
RTMP_PORT="1935"

# Parse arguments
STREAM_ID="${1:-$DEFAULT_STREAM_ID}"
HOST="${2:-$DEFAULT_HOST}"

# Validate stream ID
if ! [[ "$STREAM_ID" =~ ^[a-zA-Z0-9_-]+$ ]]; then
    echo "Error: Invalid stream ID '$STREAM_ID'" >&2
    echo "Stream ID must contain only alphanumeric characters, hyphens, and underscores" >&2
    exit 1
fi

# Build URLs
RTSP_URL="rtsp://${HOST}:${RTSP_PORT}/live/${STREAM_ID}/in"
RTMP_URL="rtmp://${HOST}:${RTMP_PORT}/live/${STREAM_ID}/out"

echo "=========================================="
echo "GStreamer Stream Bypass (RTSP -> RTMP)"
echo "=========================================="
echo "Stream ID:    $STREAM_ID"
echo "Input (RTSP): $RTSP_URL"
echo "Output (RTMP):$RTMP_URL"
echo "Transport:    TCP (to avoid packet loss)"
echo "=========================================="
echo ""
echo "Note: Source stream must be active before running this script."
echo "Press Ctrl+C to stop..."
echo ""

# Run GStreamer bypass pipeline
# Notes:
# - rtspsrc reads from RTSP with TCP transport
# - rtph264depay and rtpmp4gdepay extract raw H264/AAC from RTP
# - No re-encoding: copy mode for minimal latency
# - flvmux packages for RTMP
# - rtmpsink publishes to output path
exec gst-launch-1.0 -e \
    rtspsrc location="${RTSP_URL}" protocols=tcp latency=0 ! \
    rtph264depay ! \
    h264parse ! \
    flvmux name=mux streamable=true ! \
    rtmpsink location="${RTMP_URL} live=1" \
    \
    rtspsrc location="${RTSP_URL}" protocols=tcp latency=0 name=src ! \
    rtpmp4gdepay ! \
    aacparse ! \
    mux.
