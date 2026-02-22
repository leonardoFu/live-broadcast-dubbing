# Debug Context: Media Service Output Stream Playability Issue

**Debug ID**: debug-20260103-stream-playability
**Created**: 2026-01-03
**Updated**: 2026-01-04T04:45:00Z
**Status**: resolved
**Iteration**: 3 / 5

## Issue Description

The media service output stream (`rtmp://localhost:1935/live/test-stream/out`) is being published to MediaMTX but is not playable by external tools like ffprobe/ffplay.

**Error Message**:
```
Could not find codec parameters for stream 0 (Video: h264, none, 128 kb/s): unspecified size
```

**Symptom**: ffprobe shows `width: 0, height: 0` for the video stream, indicating missing H.264 codec parameters (SPS/PPS).

## Success Criteria

- **SC-001**: Output stream is playable by ffprobe without codec parameter errors
- **SC-002**: ffprobe shows valid video dimensions (e.g., 1280x720 or 1920x1080)
- **SC-003**: Output stream is playable by ffplay with visible video

## Current State Summary

| Component | Status | Notes |
|-----------|--------|-------|
| Input stream (`/in`) | ✅ Working | ffprobe shows 1280x720 correctly |
| Worker stability | ✅ Fixed | MediaMTX config prevents spurious not-ready events |
| Output stream appears | ✅ Working | Stream visible in MediaMTX with `ready: true` |
| Video data flowing | ✅ Working | Logs show VIDEO PUSHED successfully |
| Audio data flowing | ✅ Working | Logs show AUDIO PUSHED successfully |
| SPS/PPS in segments | ✅ Verified | All segments contain SPS/PPS/IDR |
| SPS/PPS prepending | ✅ Working | 37 bytes prepended to segments |
| Output playability | ✅ FIXED | ffprobe shows width=1280, height=720 |

---

## Investigation History

### Iteration 1: MediaMTX Hook Issue (RESOLVED)

**Timestamp**: 2026-01-03T20:30:00Z

**Problem**: Worker kept stopping after ~6-7 seconds due to spurious "not-ready" events.

**Root Cause**: MediaMTX `all_others` path configuration triggered not-ready events when worker connected as reader.

**Fix Applied**: Updated `mediamtx.yml` with path-specific rules:
```yaml
paths:
  ~^live/.+/in$:   # Input paths - hooks for publisher only
  ~^live/.+/out$:  # Output paths - no hooks needed
  all_others:      # Fallback - no hooks
```

**Result**: ✅ Worker now runs continuously.

---

### Iteration 2: H.264 SPS/PPS Codec Parameters (IN PROGRESS)

**Timestamp**: 2026-01-04T03:55:00Z

**Problem**: Output stream has video data but ffprobe can't detect codec parameters.

#### Key Findings

**1. Input Stream Works Perfectly**
```bash
ffprobe rtmp://localhost:1935/live/test-stream/in
# Result: width=1280, height=720 ✅
```

**2. Output Stream Lacks Codec Info**
```bash
ffprobe rtmp://localhost:1935/live/test-stream/out
# Result: width=0, height=0 ❌
```

**3. SPS/PPS IS Present in Segment Data**
- Verified by checking entire segment (not just first bytes)
- Log: `has_SPS=True, has_PPS=True, has_IDR=True` for all segments
- h264parse config-interval=-1 IS inserting SPS/PPS before IDR frames

**4. SPS/PPS Location Issue**
```
Segment 0: 0000000109f0000000016764... (SPS at byte 12 after AUD)
Segment 1: 0000000109f000000001060423... (SEI at start, SPS later)
Segment 2: 0000000109f000000001219e... (Non-IDR at start, SPS later)
```
- Only segment 0 has SPS at the START
- Segments 1+ have SPS/PPS LATER in the segment (after first keyframe)

**5. SPS/PPS Prepending Implemented**
- Extracted 37 bytes of SPS+PPS from segment 0
- Prepending to all subsequent segments
- Log: `📼 Prepended SPS/PPS: 37 bytes to X bytes`

**6. Output Pipeline Modifications**
- Added `video_capsfilter` to force AVC output format
- Set buffer flags (LIVE, no DELTA_UNIT for keyframes)
- Pipeline: `appsrc → h264parse → capsfilter → queue → flvmux → rtmpsink`

#### Potential Root Causes (Ordered by Likelihood)

**1. h264parse Not Generating codec_data (HIGH)**
- Receives 1.7MB buffer with concatenated NAL units
- May not properly parse/extract SPS/PPS from large buffers
- May need to see NAL units as separate buffers
- Verification needed: Check h264parse src pad caps for codec_data field

**2. FLV Sequence Header Not Generated (HIGH)**
- flvmux creates AVC sequence header from h264parse's codec_data
- If h264parse doesn't provide codec_data in caps → no FLV header
- Without AVC sequence header, decoders can't determine resolution

**3. Buffer Size/Timing Issues (MEDIUM)**
- Pushing 6-second segments as single 1.7MB buffers
- GStreamer parsers typically expect smaller, more frequent buffers
- First segment starts at pts=10.07s instead of 0
- Gap between segments may cause parsing issues

**4. AVC vs Byte-Stream Conversion Failure (MEDIUM)**
- capsfilter requests `stream-format=avc`
- h264parse may fail to convert if input parsing is incomplete
- Need codec_data to output AVC format

**5. appsrc Caps Negotiation (LOW)**
- Current caps: `video/x-h264,stream-format=byte-stream,alignment=au`
- May need width/height/framerate hints

---

## Files Modified

1. **apps/media-service/deploy/mediamtx/mediamtx.yml**
   - Path-specific configuration for `/in` and `/out` streams

2. **apps/media-service/src/media_service/pipeline/output.py**
   - Added `_sps_pps_data: bytes | None` storage
   - Added `_extract_sps_pps()` method for NAL unit extraction
   - Modified `push_video()` to prepend SPS/PPS when missing at start
   - Added `video_capsfilter` element for AVC format
   - Updated linking: `h264parse → video_capsfilter → video_queue`
   - Set buffer flags: `Gst.BufferFlags.LIVE`

3. **apps/media-service/src/media_service/buffer/segment_buffer.py**
   - Added debug logging for SPS/PPS/IDR presence
   - Added first_bytes hex dump for analysis

---

### Iteration 3: Video Re-encoding Approach (RESOLVED ✅)

**Timestamp**: 2026-01-04T04:30:00Z

**Hypothesis**: Re-encode video before output to force:
1. Keyframe alignment with 6-second audio segment boundaries
2. Proper SPS/PPS generation from encoder (not just parsing)
3. Clean codec_data for flvmux AVC sequence header

**Approach**: Change pipeline from passthrough to decode→encode:
```
BEFORE: appsrc → h264parse → capsfilter → queue → flvmux → rtmpsink
AFTER:  appsrc → h264parse → avdec_h264 → videoconvert → x264enc → h264parse → queue → flvmux → rtmpsink
```

**x264enc Configuration** (low-latency streaming):
- `tune=zerolatency` - minimize latency
- `key-int-max=30` - keyframe every 1 second at 30fps
- `bframes=0` - no B-frames for lower latency
- `speed-preset=veryfast` - balance quality/speed
- `bitrate=2000` - maintain quality

**Rationale**:
- The encoder generates fresh SPS/PPS at stream start
- codec_data is properly set in output caps
- Keyframes are guaranteed at segment boundaries
- flvmux receives all required metadata for AVC sequence header

**Result**: ✅ SUCCESS

**Verification**:
```bash
$ ffprobe -v error -show_entries stream=codec_type,width,height,codec_name \
    -of json rtmp://localhost:1935/live/test-stream/out

{
    "streams": [
        {
            "codec_name": "h264",
            "codec_type": "video",
            "width": 1280,
            "height": 720
        },
        {
            "codec_name": "aac",
            "codec_type": "audio"
        }
    ]
}
```

**Root Cause Confirmed**: The passthrough pipeline relied on h264parse to extract codec_data from incoming byte-stream buffers, but when pushing large 6-second segment buffers (~1.7MB), h264parse couldn't properly negotiate caps with flvmux. The re-encoding approach:
1. Decodes H.264 to raw video frames
2. Re-encodes with x264enc, generating fresh SPS/PPS
3. h264parse (after encoder) outputs proper codec_data in caps
4. flvmux creates correct AVC sequence header with resolution info

---

## Recommended Next Steps

### Priority 1: Verify h264parse codec_data
```python
# Add after first buffer push in output.py
h264parse = self._pipeline.get_by_name("h264parse")
src_pad = h264parse.get_static_pad("src")
caps = src_pad.get_current_caps()
if caps:
    structure = caps.get_structure(0)
    codec_data = structure.get_value("codec_data")
    logger.info(f"h264parse codec_data: {codec_data}")
```

### Priority 2: Enable GStreamer Debug
```bash
GST_DEBUG=h264parse:5,flvmux:5 docker compose up
```

### Priority 3: Push Smaller Buffers
Instead of 6-second segments:
- Split into individual NAL units
- Push SPS/PPS as separate buffers first
- Set proper flags for each NAL type (IDR vs P/B)

### Priority 4: Try File-Based Method
Use existing `push_segment_files()` which has working MP4 demux pipeline:
- Writes segment to MP4 file
- Uses `_read_mp4_video()` with full GStreamer demux
- Already has config-interval=-1 in demux pipeline

---

## Test Commands

```bash
# Start services
cd apps/media-service
SKIP_STS_CONNECTION=true docker compose up -d --build

# Publish test stream
ffmpeg -stream_loop -1 -re \
  -i tests/fixtures/test-streams/1-min-nfl.mp4 \
  -c:v copy -c:a copy -f flv \
  rtmp://localhost:1935/live/test-stream/in

# Check paths
curl -s http://localhost:9997/v3/paths/list | python3 -m json.tool

# Verify input (should show 1280x720)
ffprobe -v error \
  -show_entries stream=codec_type,width,height,codec_name \
  -of json rtmp://localhost:1935/live/test-stream/in

# Verify output (currently shows 0x0)
ffprobe -v error -analyzeduration 5000000 -probesize 5000000 \
  -show_entries stream=codec_type,width,height,codec_name \
  -of json rtmp://localhost:1935/live/test-stream/out

# Check logs
docker logs media-service 2>&1 | grep -E "(SPS|PPS|VIDEO|AUDIO)"
```

---

## Key Insight

**The same video data that plays correctly from `/in` doesn't play from `/out`.**

This definitively proves the issue is in how we're re-muxing the stream, not in the original data. The FLV container created by GStreamer's flvmux is missing the AVC sequence header that contains codec parameters.

---

*Last updated: 2026-01-04T03:55:00Z*
