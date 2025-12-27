#!/usr/bin/env bash
#
# gstreamer-publish.sh - Publish test stream to MediaMTX via RTMP using GStreamer
#
# This script generates a test stream with:
# - SMPTE color bars video pattern (videotestsrc)
# - 1kHz sine wave audio (audiotestsrc)
# - H.264 + AAC codecs (compatible with MediaMTX)
#
# Usage:
#   ./gstreamer-publish.sh [stream-id] [rtmp-host] [rtmp-port]
#
# Arguments:
#   stream-id   - Unique stream identifier (default: test-stream)
#   rtmp-host   - MediaMTX RTMP host (default: localhost)
#   rtmp-port   - MediaMTX RTMP port (default: 1935)
#
# Examples:
#   # Publish test stream
#   ./gstreamer-publish.sh
#
#   # Publish with custom stream ID
#   ./gstreamer-publish.sh my-stream
#
#   # Publish to remote MediaMTX
#   ./gstreamer-publish.sh my-stream mediamtx.example.com 1935
#
# Prerequisites:
#   - GStreamer 1.0 installed with:
#     - gst-plugins-base (videotestsrc, audiotestsrc)
#     - gst-plugins-good (flvmux)
#     - gst-plugins-bad (rtmpsink)
#     - gst-plugins-ugly (x264enc)
#     - gst-libav or gst-plugins-bad (voaacenc)
#   - MediaMTX running and accepting RTMP connections
#
# Output Format:
#   - Video: H.264 (x264enc), 1280x720 @ 30fps, 2000kbps
#   - Audio: AAC (voaacenc), 48kHz stereo, 128kbps
#   - Container: FLV (for RTMP)
#

set -euo pipefail

# Default configuration
DEFAULT_STREAM_ID="test-stream"
DEFAULT_RTMP_HOST="localhost"
DEFAULT_RTMP_PORT="1935"

# Video configuration
VIDEO_WIDTH="1280"
VIDEO_HEIGHT="720"
VIDEO_FRAMERATE="30"
VIDEO_BITRATE="2000"  # kbps
VIDEO_PATTERN="smpte"  # SMPTE color bars

# Audio configuration
AUDIO_FREQUENCY="1000"  # 1kHz sine wave
AUDIO_SAMPLE_RATE="48000"
AUDIO_CHANNELS="2"
AUDIO_BITRATE="128000"  # bps

# Parse arguments
STREAM_ID="${1:-$DEFAULT_STREAM_ID}"
RTMP_HOST="${2:-$DEFAULT_RTMP_HOST}"
RTMP_PORT="${3:-$DEFAULT_RTMP_PORT}"

# Validate stream ID (alphanumeric, hyphens, underscores only)
if ! [[ "$STREAM_ID" =~ ^[a-zA-Z0-9_-]+$ ]]; then
    echo "Error: Invalid stream ID '$STREAM_ID'" >&2
    echo "Stream ID must contain only alphanumeric characters, hyphens, and underscores" >&2
    exit 1
fi

# Build RTMP URL
RTMP_URL="rtmp://${RTMP_HOST}:${RTMP_PORT}/live/${STREAM_ID}/in"

echo "=========================================="
echo "GStreamer Test Stream Publisher"
echo "=========================================="
echo "Stream ID:    $STREAM_ID"
echo "RTMP URL:     $RTMP_URL"
echo "Video:        ${VIDEO_WIDTH}x${VIDEO_HEIGHT} @ ${VIDEO_FRAMERATE}fps, ${VIDEO_BITRATE}kbps"
echo "Audio:        ${AUDIO_FREQUENCY}Hz sine, $((AUDIO_BITRATE / 1000))kbps"
echo "Pattern:      $VIDEO_PATTERN"
echo "=========================================="
echo ""
echo "Press Ctrl+C to stop streaming..."
echo ""

# Run GStreamer pipeline
# Notes:
# - videotestsrc generates test patterns (smpte, ball, etc.)
# - audiotestsrc generates audio test signals (sine wave)
# - x264enc encodes H.264 with zerolatency for low latency
# - voaacenc encodes AAC audio
# - flvmux combines video and audio into FLV container
# - rtmpsink publishes to RTMP server
exec gst-launch-1.0 -e \
    videotestsrc pattern="${VIDEO_PATTERN}" ! \
    "video/x-raw,width=${VIDEO_WIDTH},height=${VIDEO_HEIGHT},framerate=${VIDEO_FRAMERATE}/1" ! \
    x264enc tune=zerolatency bitrate="${VIDEO_BITRATE}" speed-preset=veryfast ! \
    h264parse ! \
    flvmux name=mux streamable=true ! \
    rtmpsink location="${RTMP_URL} live=1" \
    \
    audiotestsrc wave=sine freq="${AUDIO_FREQUENCY}" ! \
    "audio/x-raw,rate=${AUDIO_SAMPLE_RATE},channels=${AUDIO_CHANNELS}" ! \
    voaacenc bitrate="${AUDIO_BITRATE}" ! \
    aacparse ! \
    mux.
