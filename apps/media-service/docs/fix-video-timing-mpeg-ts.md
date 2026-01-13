# Fix: Video Timing with MPEG-TS Container

**Date:** 2026-01-12
**Branch:** 021-fragment-length-30s
**Status:** Resolved

## Issue Summary

Video playback stuttered and froze at 30-second segment boundaries in the dubbed output stream. The output pipeline was processing at only 39.7% of real-time speed (0.397x), causing queue buildup, segment drops, and eventual RTMP connection failures.

### Symptoms

| Symptom | Details |
|---------|---------|
| Playback stuttering | 3-8 second gaps at ~30s, ~60s, ~90s boundaries |
| ffmpeg speed | `speed=0.397x` in stderr logs |
| Queue overflow | "Video buffer full (10), dropping oldest segment" |
| RTMP failure | Connection broken after queue filled |

### Root Cause

Raw H.264 byte-stream format has **no embedded timing information**. When ffmpeg attempted to mux raw H.264 video with AAC audio, it couldn't determine frame timestamps:

```
[h264 @ 0x...] Discarding unsupported
[flv @ 0x...] Discarding timestamp offset due to pts/dts
```

Without proper PTS (Presentation Timestamp), ffmpeg processed frames as fast as possible rather than at real-time rate, causing the `-re` flag to malfunction.

## Solution

### 1. Wrap H.264 in MPEG-TS Container (input.py)

Added `mpegtsmux` element to the GStreamer video pipeline to preserve per-frame timestamps:

```
Before: flvdemux → h264parse → queue → appsink (raw H.264)
After:  flvdemux → h264parse → mpegtsmux → queue → appsink (MPEG-TS)
```

Key changes:
- Added `mpegtsmux` element after `h264parse`
- Changed video appsink caps to `video/mpegts,systemstream=true`
- MPEG-TS embeds timestamps in PCR (Program Clock Reference) and PES packet headers

### 2. Update ffmpeg Muxing (ffmpeg_output.py)

Modified the muxing command to accept MPEG-TS input:

```python
# Before
"-f", "h264", "-i", str(video_path),  # Raw H.264 (no timing)

# After
"-f", "mpegts", "-i", str(video_path),  # MPEG-TS (with timing)
```

### 3. Fix Segment Duration Calculation (segment_buffer.py)

Changed from summing individual buffer durations to PTS-based calculation:

```python
# Before (unreliable for MPEG-TS packets)
acc.duration_ns += duration_ns

# After (accurate using PTS span)
acc.duration_ns = (pts_ns - acc.t0_ns) + duration_ns
```

This ensures segments emit at correct 30-second intervals regardless of buffer size variations.

## Why Audio Doesn't Need MPEG-TS

| Format | Timing Info | Reason |
|--------|-------------|--------|
| Raw H.264 | None | Just NAL units, no timestamps |
| AAC ADTS | Self-contained | Each frame has implicit duration (1024 samples / sample_rate) |

AAC ADTS headers contain sample rate and frame size, allowing ffmpeg to calculate timing automatically.

## Files Modified

| File | Change |
|------|--------|
| `src/media_service/pipeline/input.py` | Added mpegtsmux, updated caps |
| `src/media_service/pipeline/ffmpeg_output.py` | Changed to `-f mpegts` input |
| `src/media_service/buffer/segment_buffer.py` | PTS-based duration calculation |

## Verification

### Prerequisites

```bash
# Start services
cd apps/media-service
docker compose up -d

# Wait for healthy status
docker compose ps
```

### Test Procedure

1. **Push test stream to input path:**
   ```bash
   ffmpeg -re -stream_loop -1 \
     -i tests/fixtures/test-streams/1-min-nfl.mp4 \
     -c:v copy -c:a aac -ar 44100 -ac 2 \
     -f flv rtmp://localhost:1935/live/test-stream/in
   ```

2. **Verify segment timing (should emit every ~30s):**
   ```bash
   docker logs media-service 2>&1 | grep "Video segment emitted"
   ```

   Expected output:
   ```
   Video segment emitted: batch=0, duration=30.02s, buffers=45648, size=8581824...
   Video segment emitted: batch=1, duration=30.03s, buffers=45449, size=8544412...
   ```

   Timestamps should be ~30 seconds apart.

3. **Verify muxing success:**
   ```bash
   docker logs media-service 2>&1 | grep "Muxed segment"
   ```

   Expected output:
   ```
   Muxed segment: 8237975 bytes (pts=30.02s)
   Muxed segment: 8662392 bytes (pts=60.07s)
   ```

4. **Verify output stream is live:**
   ```bash
   curl -s http://localhost:9997/v3/paths/list | jq '.items[] | select(.name | contains("out"))'
   ```

   Expected: `"ready": true` with H264 and MPEG-4 Audio tracks.

5. **Capture and analyze output:**
   ```bash
   ffmpeg -i rtmp://localhost:1935/live/test-stream/out -t 5 -c copy /tmp/test.flv
   ffprobe -v error -show_streams /tmp/test.flv
   ```

   Expected: Video H.264 @ 30fps, Audio AAC @ 48kHz.

### Success Criteria

| Metric | Before | After |
|--------|--------|-------|
| ffmpeg speed | 0.397x | 1.0x |
| Segment interval | ~0.5s (wrong) | ~30s (correct) |
| Video buffer drops | Constant | None |
| Output stream | Broken | Stable |

## Technical Details

### MPEG-TS Format

MPEG Transport Stream (TS) is a container format that:
- Uses 188-byte fixed-size packets
- Embeds PCR (Program Clock Reference) for timing synchronization
- Contains PES (Packetized Elementary Stream) headers with PTS/DTS
- First byte of each packet is sync byte `0x47`

### GStreamer Pipeline

```
rtmpsrc location=rtmp://...
    → flvdemux
        → [video] h264parse config-interval=-1
            → mpegtsmux
            → queue max-size-time=5s leaky=downstream
            → appsink caps="video/mpegts,systemstream=true"
        → [audio] aacparse
            → queue max-size-time=5s leaky=downstream
            → appsink caps="audio/mpeg,mpegversion=4,stream-format=adts"
```

### ffmpeg Muxing Command

```bash
ffmpeg -y \
  -f mpegts -i video.ts \      # MPEG-TS video with embedded timestamps
  -f aac -i audio.aac \        # AAC ADTS (self-describing timing)
  -c:v copy -c:a copy \        # No re-encoding
  -output_ts_offset 30.02 \    # Align to segment PTS
  -f flv output.flv
```

## Related Specs

- `specs/021-fragment-length-30s/` - 30-second segment duration
- `specs/003-audio-pipeline/` - A/V synchronization
- `specs/020-rtmp-stream-pull/` - RTMP input pipeline
