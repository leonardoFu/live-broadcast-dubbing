#!/usr/bin/env bash
#
# ffmpeg-publish.sh - Publish test stream to MediaMTX via RTMP
#
# This script generates a test stream with:
# - Color bars video pattern (testsrc)
# - 1kHz sine wave audio
# - H.264 + AAC codecs (compatible with MediaMTX)
#
# Usage:
#   ./ffmpeg-publish.sh [stream-id] [duration] [rtmp-host] [rtmp-port]
#
# Arguments:
#   stream-id   - Unique stream identifier (default: test-stream)
#   duration    - Stream duration in seconds (default: infinite)
#   rtmp-host   - MediaMTX RTMP host (default: localhost)
#   rtmp-port   - MediaMTX RTMP port (default: 1935)
#
# Examples:
#   # Publish infinite test stream
#   ./ffmpeg-publish.sh
#
#   # Publish for 30 seconds
#   ./ffmpeg-publish.sh my-stream 30
#
#   # Publish to remote MediaMTX
#   ./ffmpeg-publish.sh my-stream 60 mediamtx.example.com 1935
#
# Prerequisites:
#   - FFmpeg installed with libx264 and aac encoders
#   - MediaMTX running and accepting RTMP connections
#
# Output Format:
#   - Video: H.264 (libx264), 1280x720 @ 30fps, 2000kbps
#   - Audio: AAC, 48kHz stereo, 128kbps
#   - Container: FLV (for RTMP)
#

set -euo pipefail

# Default configuration
DEFAULT_STREAM_ID="test-stream"
DEFAULT_RTMP_HOST="localhost"
DEFAULT_RTMP_PORT="1935"

# Video configuration
VIDEO_SIZE="1280x720"
VIDEO_FRAMERATE="30"
VIDEO_BITRATE="2000k"
VIDEO_PRESET="veryfast"
VIDEO_TUNE="zerolatency"

# Audio configuration
AUDIO_FREQUENCY="1000"  # 1kHz sine wave
AUDIO_SAMPLE_RATE="48000"
AUDIO_BITRATE="128k"

# Parse arguments
STREAM_ID="${1:-$DEFAULT_STREAM_ID}"
DURATION="${2:-}"
RTMP_HOST="${3:-$DEFAULT_RTMP_HOST}"
RTMP_PORT="${4:-$DEFAULT_RTMP_PORT}"

# Validate stream ID (alphanumeric, hyphens, underscores only)
if ! [[ "$STREAM_ID" =~ ^[a-zA-Z0-9_-]+$ ]]; then
    echo "Error: Invalid stream ID '$STREAM_ID'" >&2
    echo "Stream ID must contain only alphanumeric characters, hyphens, and underscores" >&2
    exit 1
fi

# Build RTMP URL
RTMP_URL="rtmp://${RTMP_HOST}:${RTMP_PORT}/live/${STREAM_ID}/in"

# Build duration arguments
DURATION_ARGS=""
if [[ -n "$DURATION" ]]; then
    DURATION_ARGS="-t $DURATION"
fi

echo "=========================================="
echo "FFmpeg Test Stream Publisher"
echo "=========================================="
echo "Stream ID:    $STREAM_ID"
echo "RTMP URL:     $RTMP_URL"
echo "Video:        ${VIDEO_SIZE} @ ${VIDEO_FRAMERATE}fps, ${VIDEO_BITRATE}"
echo "Audio:        ${AUDIO_FREQUENCY}Hz sine, ${AUDIO_BITRATE}"
echo "Duration:     ${DURATION:-infinite}"
echo "=========================================="
echo ""
echo "Press Ctrl+C to stop streaming..."
echo ""

# Run FFmpeg
# shellcheck disable=SC2086
exec ffmpeg \
    -re \
    -f lavfi -i "testsrc=size=${VIDEO_SIZE}:rate=${VIDEO_FRAMERATE}" \
    -f lavfi -i "sine=frequency=${AUDIO_FREQUENCY}:sample_rate=${AUDIO_SAMPLE_RATE}" \
    -c:v libx264 \
    -preset "$VIDEO_PRESET" \
    -tune "$VIDEO_TUNE" \
    -b:v "$VIDEO_BITRATE" \
    -c:a aac \
    -b:a "$AUDIO_BITRATE" \
    $DURATION_ARGS \
    -f flv \
    "$RTMP_URL"
