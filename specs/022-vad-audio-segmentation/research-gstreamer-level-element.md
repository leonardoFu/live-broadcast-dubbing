# Research: GStreamer Level Element for VAD Silence Detection

**Date**: 2026-01-06
**Related Plan**: [plan.md](./plan.md)
**Status**: Research Complete

## Executive Summary

The current plan proposes using GStreamer's `level` element with **asynchronous bus messages** for silence detection. This research identifies a **critical timing concern**: bus messages are delivered asynchronously to the main loop, which can introduce unpredictable delays between when audio passes through the `level` element and when the application receives the RMS values.

**Recommendation**: The plan is workable but should be enhanced with **timestamp-based correlation** rather than relying on message delivery timing. An alternative approach using **synchronous message handling** or **GstAudioLevelMeta** may provide better real-time guarantees.

---

## 1. How the GStreamer `level` Element Works

### Overview

The `level` element analyzes incoming audio buffers and posts element messages to the GStreamer bus containing RMS, peak, and decay levels.

### Key Properties

| Property | Type | Default | Purpose |
|----------|------|---------|---------|
| `interval` | guint64 | 100ms (ns) | Time between message posts |
| `post-messages` | boolean | true | Enable/disable level message posting |
| `peak-ttl` | guint64 | 300ms | Duration before decay peak begins falling |
| `peak-falloff` | gdouble | 10 dB/sec | Decay rate for peak after TTL expires |
| `audio-level-meta` | boolean | false | Attach GstAudioLevelMeta to output buffers |

### Message Structure

Level messages contain:

```
timestamp:    GstClockTime - buffer timestamp that triggered the message
stream-time:  GstClockTime - stream time of the buffer
running-time: GstClockTime - running time of the buffer
duration:     GstClockTime - duration of the buffer
rms:          GValueArray  - RMS level in dB per channel
peak:         GValueArray  - Peak level in dB per channel
decay:        GValueArray  - Decaying peak level in dB per channel
```

**Important**: The `timestamp` field in the message corresponds to the **buffer's PTS**, not the wall-clock time when the message is delivered.

---

## 2. Audio Buffer Callback vs Bus Message: Timing Analysis

### Current Architecture (from plan.md)

```
┌─────────────────────────────────────────────────────────────────┐
│ GStreamer Pipeline (Streaming Thread)                           │
│                                                                 │
│   rtmpsrc → flvdemux → aacparse → level → appsink              │
│                                      │         │                │
│                                      │         └─→ Buffer callback
│                                      │              (streaming thread)
│                                      │
│                                      └─→ Posts message to bus
└─────────────────────────────────────────────────────────────────┘
                                           │
                                           ↓ (async, via main loop)
┌─────────────────────────────────────────────────────────────────┐
│ Application (Main Thread)                                        │
│                                                                 │
│   Bus watch callback receives level message                      │
│   (gst_bus_add_watch / add_signal_watch)                        │
└─────────────────────────────────────────────────────────────────┘
```

### The Timing Problem

1. **Buffer Callback**: Called **synchronously** in the streaming thread when a buffer arrives at the appsink. This is immediate and deterministic.

2. **Bus Message**: Posted by the `level` element, but delivered **asynchronously** through the GLib main loop. The GStreamer documentation explicitly warns:

   > "The handler will be called in the thread context of the mainloop. This means that the interaction between the pipeline and application over the bus is **asynchronous**, and thus **not suited for some real-time purposes**."

### Potential Race Condition

```
Timeline:
─────────────────────────────────────────────────────────────────────→
   T0          T1          T2          T3          T4
   │           │           │           │           │
   │           │           │           │           │
   Buffer A    Buffer B    Level msg   Buffer C    Level msg
   arrives     arrives     for A       arrives     for B
   (callback)  (callback)  delivered   (callback)  delivered
                           (async)                 (async)
```

The delay between buffer arrival and level message delivery is **non-deterministic** and depends on:
- Main loop iteration frequency
- CPU load
- Other pending events in the main loop

### Impact on VAD Logic

The plan's `handle_level_message()` approach assumes level messages arrive in a timely manner relative to buffer callbacks. However:

1. **Segment emission may be delayed**: If silence is detected via a level message that arrives late, the segment boundary won't align precisely with the actual silence in the audio.

2. **Buffer accumulation continues**: While waiting for the level message, `push_audio()` continues accumulating buffers. If a level message arrives late, more audio than necessary may be included in the segment.

3. **Not a critical failure**: The timestamps in the level message allow reconstruction of when silence actually occurred, but the current plan doesn't explicitly leverage this.

---

## 3. Alternative Approaches

### Option A: Timestamp-Based Correlation (Recommended Enhancement)

Keep the current dual-callback architecture but use **timestamps for correlation**:

```python
class VADAudioSegmenter:
    def __init__(self, ...):
        self._pending_silence_boundary_ns: int | None = None
        self._buffer_queue: deque[tuple[bytes, int, int]] = deque()

    def push_audio(self, data: bytes, pts_ns: int, duration_ns: int):
        # Check if we've passed a pending silence boundary
        if self._pending_silence_boundary_ns is not None:
            if pts_ns >= self._pending_silence_boundary_ns:
                # Emit segment up to the silence boundary
                return self._emit_segment_at_boundary(self._pending_silence_boundary_ns)

        # Accumulate buffer
        self._accumulate(data, pts_ns, duration_ns)
        return None, b""

    def handle_level_message(self, rms_db: float, timestamp_ns: int):
        if self._is_silence(rms_db):
            if not self._in_silence:
                self._silence_start_ns = timestamp_ns
                self._in_silence = True
            elif timestamp_ns - self._silence_start_ns >= self._config.silence_duration_ns:
                # Mark boundary for next push_audio to handle
                self._pending_silence_boundary_ns = timestamp_ns
        else:
            self._in_silence = False
            self._silence_start_ns = None
```

**Pros**:
- Works with existing async bus messages
- Uses timestamps (from level message) for precise boundary detection
- Segment emission happens in `push_audio()` which has the buffer data

**Cons**:
- Slightly more complex state management
- Small latency between silence detection and segment emission (bounded by buffer interval ~23ms)

### Option B: Synchronous Bus Handler

Use `gst_bus_set_sync_handler()` instead of `gst_bus_add_watch()`:

```python
def _setup_bus(self):
    bus = self._pipeline.get_bus()
    bus.set_sync_handler(self._on_sync_message, None)

def _on_sync_message(self, bus, message, user_data):
    """Called in streaming thread context - MUST be fast!"""
    if message.get_structure() and message.get_structure().get_name() == "level":
        rms = message.get_structure().get_value("rms")[0]
        timestamp = message.get_structure().get_value("timestamp")
        # Store for processing (don't block streaming thread)
        self._level_queue.put_nowait((rms, timestamp))
    return Gst.BusSyncReply.PASS  # Continue to async queue
```

**Pros**:
- Messages received in streaming thread (same as buffer callbacks)
- Minimal latency between level calculation and message receipt

**Cons**:
- Handler runs in streaming thread - must be extremely fast
- Requires careful thread synchronization
- GStreamer docs warn: "Applications should handle messages asynchronously"

### Option C: GstAudioLevelMeta (Alternative)

The `level` element can attach `GstAudioLevelMeta` directly to output buffers:

```python
level.set_property("audio-level-meta", True)

def _on_audio_buffer(self, data, pts_ns, duration_ns, buffer):
    # Get level meta from buffer itself
    meta = buffer.get_meta("GstAudioLevelMeta")
    if meta:
        rms_db = meta.level  # Already attached to the buffer!
```

**Pros**:
- RMS level travels with the buffer - perfect synchronization
- No bus messages needed for VAD
- Simplest mental model

**Cons**:
- Requires GStreamer 1.20+ for `GstAudioLevelMeta`
- Need to verify appsink exposes buffer metadata in Python bindings
- Less commonly documented approach

### Option D: Decode Audio in Buffer Callback

Skip the `level` element entirely and calculate RMS in the buffer callback:

```python
def _on_audio_buffer(self, data: bytes, pts_ns: int, duration_ns: int):
    # Decode AAC to PCM (or use raw audio before aacparse)
    pcm_samples = self._decode_aac(data)
    rms_db = self._calculate_rms(pcm_samples)

    # VAD logic with synchronized RMS
    if self._is_silence(rms_db):
        ...
```

**Pros**:
- Perfect synchronization (RMS calculated for exact buffer)
- No bus message complexity

**Cons**:
- AAC decoding in callback adds CPU overhead
- Duplicates work GStreamer could do natively
- More code to maintain

---

## 4. Evaluation of Current Plan

### Strengths

1. **Uses native GStreamer element**: Leverages proven, optimized code
2. **Graceful fallback**: Falls back to fixed 6s on failure
3. **Configurable**: All parameters via environment variables
4. **Good metrics coverage**: Comprehensive observability

### Weaknesses

1. **Async message timing not addressed**: Plan assumes level messages arrive "in time" but doesn't handle the inherent asynchronicity

2. **Dual emission points**: Both `push_audio()` and `handle_level_message()` can emit segments, creating potential race conditions:
   ```python
   # From plan.md - both methods return (AudioSegment | None, bytes)
   def push_audio(...) -> tuple[AudioSegment | None, bytes]:
   def handle_level_message(...) -> tuple[AudioSegment | None, bytes]:
   ```

3. **Missing timestamp correlation**: The plan doesn't explicitly use the `timestamp` field from level messages to correlate with buffer PTS

4. **Thread safety concerns**: If `handle_level_message()` is called from main thread while `push_audio()` is called from streaming thread, shared state needs protection

### Recommended Changes

1. **Single emission point**: Only emit segments from `push_audio()`. Use `handle_level_message()` to set a "pending boundary" flag with timestamp.

2. **Timestamp-based boundaries**: When a silence boundary is detected via level message, store the `timestamp_ns` from the message. In `push_audio()`, check if current buffer PTS has crossed this boundary.

3. **Thread safety**: Add a lock or use thread-safe data structures for shared state between callbacks.

4. **Consider GstAudioLevelMeta**: If targeting GStreamer 1.20+, this provides cleaner synchronization.

---

## 5. Conclusion

The current plan is **fundamentally sound** but needs refinement for production reliability:

| Aspect | Current Plan | Recommendation |
|--------|--------------|----------------|
| Level element | ✅ Good choice | Keep |
| Bus message delivery | ⚠️ Async timing issue | Use timestamps for correlation |
| Segment emission | ⚠️ Dual emission points | Single point in push_audio() |
| Thread safety | ❌ Not addressed | Add synchronization |

**Bottom Line**: The approach works, but add timestamp-based correlation between level messages and audio buffers to ensure segment boundaries align with actual silence periods regardless of bus message delivery timing.

---

## 6. A/V Synchronization with Variable-Length Segments

### The Problem

With VAD, audio segments have **variable length** (1-15s), but the current system uses fixed 6s video segments:

```
Audio:  [====3.2s====][========7.8s========][==2.1s==]
Video:  [===6s===][===6s===][===6s===][===6s===]...

        ↑ Mismatch! batch_number pairing breaks
```

The current `AvSyncManager` pairs video and audio by `batch_number`:
```python
if video_segment.batch_number == audio_segment.batch_number:
    return self._create_pair(...)
```

This **breaks** with variable-length audio because batch numbers no longer correspond to the same time ranges.

### Solution: Audio-Driven Video Segmentation (Recommended)

**Let audio VAD boundaries drive BOTH audio AND video segmentation.**

When silence is detected:
1. Emit audio segment at the silence boundary
2. **Also** emit video segment at the same timestamp (all frames up to that point)
3. Both segments share the same `batch_number` and similar duration

```python
class VADSegmenter:
    """Unified VAD segmenter for both audio and video."""

    def __init__(self, stream_id: str, segment_dir: Path, config: VADConfig):
        self._audio_accumulator = BufferAccumulator()
        self._video_accumulator = BufferAccumulator()
        self._pending_audio_buffers: deque[tuple[bytes, int, int]] = deque()
        self._pending_video_buffers: deque[tuple[bytes, int, int]] = deque()
        self._batch_number = 0
        # ... config, etc.

    def push_audio(self, data: bytes, pts_ns: int, duration_ns: int):
        """Queue audio buffer - wait for RMS info before accumulating."""
        self._pending_audio_buffers.append((data, pts_ns, duration_ns))
        return None, None  # Never emit here

    def push_video(self, data: bytes, pts_ns: int, duration_ns: int):
        """Queue video buffer - wait for audio silence boundary."""
        self._pending_video_buffers.append((data, pts_ns, duration_ns))
        return None, None  # Never emit here

    def handle_level_message(self, rms_db: float, timestamp_ns: int):
        """Process RMS and potentially emit BOTH audio and video segments."""

        # Move pending buffers to accumulators up to this timestamp
        self._process_pending_buffers(timestamp_ns)

        # Check for silence boundary
        if self._is_silence_boundary(rms_db, timestamp_ns):
            # Emit BOTH at same boundary
            audio_segment, audio_data = self._emit_audio_segment()
            video_segment, video_data = self._emit_video_segment()

            # Same batch_number, matching time ranges
            return (audio_segment, audio_data), (video_segment, video_data)

        # Check max duration (15s) - force emit if needed
        if self._audio_accumulator.duration_ns >= self._config.max_segment_duration_ns:
            audio_segment, audio_data = self._emit_audio_segment()
            video_segment, video_data = self._emit_video_segment()
            return (audio_segment, audio_data), (video_segment, video_data)

        return None, None

    def _process_pending_buffers(self, up_to_timestamp_ns: int):
        """Move pending buffers to accumulators up to given timestamp."""
        # Process audio
        while self._pending_audio_buffers:
            data, pts, dur = self._pending_audio_buffers[0]
            if pts > up_to_timestamp_ns:
                break
            self._pending_audio_buffers.popleft()
            self._accumulate_audio(data, pts, dur)

        # Process video up to same timestamp
        while self._pending_video_buffers:
            data, pts, dur = self._pending_video_buffers[0]
            if pts > up_to_timestamp_ns:
                break
            self._pending_video_buffers.popleft()
            self._accumulate_video(data, pts, dur)

    def _emit_audio_segment(self) -> tuple[AudioSegment, bytes]:
        """Emit accumulated audio as segment."""
        # ... create AudioSegment with current batch_number
        pass

    def _emit_video_segment(self) -> tuple[VideoSegment, bytes]:
        """Emit accumulated video as segment."""
        # ... create VideoSegment with SAME batch_number
        pass
```

### Data Flow with Audio-Driven Segmentation

```
                    GStreamer Pipeline
                          │
        ┌─────────────────┴─────────────────┐
        │                                   │
   Video buffers                      Audio buffers
        │                                   │
        ↓                                   ↓
 push_video()                         push_audio()
        │                                   │
        ↓                                   ↓
 _pending_video_buffers              _pending_audio_buffers
        │                                   │
        └─────────────┬─────────────────────┘
                      │
                      ↓
            handle_level_message()
                      │
         ┌────────────┴────────────┐
         │                         │
    Silence detected?         Max duration?
         │                         │
         └────────────┬────────────┘
                      │ YES
                      ↓
        ┌─────────────┴─────────────┐
        │                           │
   _emit_video_segment()      _emit_audio_segment()
        │                           │
        ↓                           ↓
   VideoSegment               AudioSegment
   batch=N                    batch=N
   duration=3.2s              duration=3.2s
        │                           │
        └─────────────┬─────────────┘
                      │
                      ↓
              AvSyncManager.push_pair()
              (batch_number matches!)
```

### Benefits of This Approach

| Aspect | Benefit |
|--------|---------|
| **Simple pairing** | Same `batch_number` for matching A/V segments |
| **Same duration** | Video and audio cover identical time ranges |
| **Single emission point** | Both emitted in `handle_level_message()` |
| **Thread safety** | All emission in one callback, no races |
| **Existing A/V sync works** | No changes to `AvSyncManager` needed |

### Video Keyframe Consideration

Since video segments may not start on keyframes (we cut at silence boundaries, not video boundaries), the output muxer needs to handle this:

1. **Include SPS/PPS/IDR** from previous keyframe in segment header
2. Or **re-encode** the first few frames (adds latency)
3. Or **extend segment backward** to include previous keyframe (slight A/V mismatch)

The current implementation already handles SPS/PPS injection (see `segment_buffer.py` line 240-251), so this should work.

### Alternative: PTS-Based Pairing (More Complex)

If audio-driven video segmentation causes issues (e.g., video quality concerns), an alternative is to keep independent video segmentation and match by **timestamp overlap** instead of batch_number:

```python
class AvSyncManager:
    def _find_matching_video(self, audio_segment: AudioSegment):
        """Find video segments overlapping with audio time range."""
        audio_start = audio_segment.t0_ns
        audio_end = audio_start + audio_segment.duration_ns

        matching = []
        for video_seg, video_data in self._video_buffer:
            video_start = video_seg.t0_ns
            video_end = video_start + video_seg.duration_ns
            if video_start < audio_end and video_end > audio_start:
                matching.append((video_seg, video_data))
        return matching
```

This is more complex because:
- One audio segment may span multiple video segments
- Need to stitch video segments together
- Need to handle partial overlaps

**Recommendation**: Start with **audio-driven video segmentation** for simplicity. Only switch to PTS-based pairing if video quality issues arise.

---

## References

- [GStreamer Level Element](https://gstreamer.freedesktop.org/documentation/level/index.html)
- [GStreamer Bus](https://gstreamer.freedesktop.org/documentation/application-development/basics/bus.html)
- [GstBus API](https://gstreamer.freedesktop.org/documentation/gstreamer/gstbus.html)
- [Clocks and Synchronization](https://gstreamer.freedesktop.org/documentation/application-development/advanced/clocks.html)
