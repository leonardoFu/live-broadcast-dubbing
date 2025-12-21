
# Live Stream Dubbing (Gemini Live) & Republish Spec

## 1. Goal

Build a live streaming pipeline that:
- Ingests a live stream via **MediaMTX**
- Processes audio in real time using **Gemini Live (speech-to-speech streaming)**
- Preserves original video
- Replaces spoken audio with dubbed audio while keeping background sound
- Republishes the processed stream to a **3rd-party RTMP endpoint**

---

## 2. High-Level Architecture

```
[Source Stream]
      |
      v
(MediaMTX Ingest: /live/<streamId>/in)
      |
      v
[Unified Worker (Python: GStreamer + Gemini Live)]
  - Demux audio/video
  - Audio chunking
  - Speech/background separation
  - Gemini Live session (streaming ASR → translation → TTS)
  - Audio remix
  - Remux A/V
      |
      v
(MediaMTX Processed Path: /live/<streamId>/out)
      |
      v
[Egress Forwarder (managed by stream-orchestration)]
      |
      v
[3rd-party RTMP Destination]
```

---

## 3. Components

### 3.1 MediaMTX
Responsibilities:
- Accept ingest (RTMP/RTSP/SRT/WebRTC)
- Provide internal pull endpoint (recommended: RTSP)
- Accept processed stream push
- Publish processed stream to RTMP destination

Suggested paths:
- Ingest: `rtmp://mediamtx/live/<streamId>/in`
- Internal pull: `rtsp://mediamtx:8554/live/<streamId>/in`
- Processed push: `rtmp://mediamtx/live/<streamId>/out`
- Final publish: `rtmp://thirdparty/app/streamKey`

See `specs/002-mediamtx.md` for hooks (worker triggers), recording, ports, and local dev operations.

---

### 3.2 Stream Orchestrator (hook receiver)

Responsibilities:
- Receive MediaMTX `runOnReady` / `runOnNotReady` events for `live/<streamId>/in`
- Start/stop the per-stream worker (or enqueue/dequeue jobs) based on stream identity + policy
- Start/stop an egress forwarder that pulls `live/<streamId>/out` and pushes to the 3rd-party RTMP destination

See `specs/002-mediamtx.md` for the proposed hook contract and configuration template.

---

### 3.3 Unified Worker (GStreamer + Gemini Live)

Responsibilities:
- Pull stream from MediaMTX
- Split audio and video using GStreamer
- Maintain a persistent Gemini Live session for streaming dubbing
- Perform speech/background separation
- Remix background audio with dubbed audio
- Remux audio with original video
- Push processed stream back to MediaMTX

Design principles:
- Video passthrough whenever possible (H.264)
- Audio decoded to PCM for processing
- Maintain A/V sync using timestamps

Implementation spec:
- `specs/003-gstreamer-stream-worker.md`

---

### 3.4 Gemini Live Session (cloud STS)

STS is provided by **Gemini Live** as a cloud streaming session managed by the unified worker (no standalone `apps/sts-service/`).

Internal “fragment” metadata (for logs/metrics and FIFO ordering):
- `id`
- `streamId`
- `batchNumber`
- `duration` (seconds)
- `sampleRate`
- `channels`

Internal audio format (v1):
- PCM S16LE (bytes), plus `sampleRate` + `channels`

---

## 4. Audio Processing Pipeline

### 4.1 Chunking
- Chunk size: 1–2 seconds
- Optional overlap: 100–200 ms

### 4.2 Gemini Live Flow
1. Resample PCM to the Gemini Live-supported format (single internal format inside the worker).
2. Stream audio fragments to a Gemini Live session tagged with `streamId` + `sequenceNumber`.
3. Receive target-language speech responses (audio + aligned text) from Gemini Live.
4. Normalize received audio to worker format and time-stretch to the fragment duration when needed.
5. Return PCM dubbed speech to the mixer with lineage to the input fragment.

### 4.3 Speech/Background Separation
Input: original PCM audio  
Output: background-only PCM

Recommended:
- 2-stem speech separation model
Fallback:
- VAD + spectral gating

### 4.4 Remixing
```
output = background * bg_gain + dubbed * dub_gain
```
Default:
- `bg_gain = 1.0`
- `dub_gain = 1.0`

Optional:
- Sidechain ducking when dubbed speech present

---

## 5. GStreamer Reference Pipelines

### 5.1 Input (RTSP Pull)

Audio branch:
```
rtspsrc ! rtpmp4gdepay ! aacparse ! avdec_aac ! audioconvert ! audioresample ! appsink
```

Video branch (passthrough):
```
rtspsrc ! rtph264depay ! h264parse ! queue
```

### 5.2 Output (RTMP Push)

```
appsrc (video) ! h264parse ! mux.
appsrc (audio) ! audioconvert ! audioresample ! voaacenc ! aacparse ! mux.
flvmux name=mux streamable=true ! rtmpsink location=rtmp://mediamtx/live/<streamId>/out
```

Worker details (Python + observability + sync strategy):
- `specs/003-gstreamer-stream-worker.md`

---

## 6. Timing & Sync

- Use GStreamer pipeline clock
- `appsrc` configured with:
  - `is-live=true`
  - `format=GST_FORMAT_TIME`
- Audio PTS derived from fragment timeline
- Video PTS preserved or aligned

---

## 7. Latency

Primary contributors:
- Gemini Live round trip time (streaming ASR/translation/TTS)
- Audio separation inference
- Buffering

Expected added latency:
- 3–8 seconds

Knobs:
- Chunk duration
- Max in-flight fragments
- Gemini Live session parameters (e.g., voice configuration)

---

## 8. Failure Handling

### Gemini Live Failures / Overload
Policy:
- Prefer continuity: keep republishing even when Gemini Live is degraded.
- Use a circuit breaker: if Gemini Live is repeatedly failing/slow, temporarily disable Gemini Live and use fallbacks.

Fallback options (configurable):
1. Pass through original audio (default)
2. Background-only audio
3. Ducked original audio (aggressive ducking when dub is present)
4. Repeat last dubbed chunk (use sparingly)
5. Silence (last resort)

### Separation Failure
- Mix dubbed over original audio
- Or skip dub for fragment

### A/V Drift
- Monitor audio-video PTS delta
- Correct via audio time-stretch

---

## 9. Scaling

- One Stream Worker per input stream
- Gemini Live sessions are managed per worker/stream (scale by running more workers)
- Preserve per-stream FIFO ordering

---

## 10. Observability

Metrics:
- Fragment processing latency
- Queue depth
- A/V sync delta
- Gemini Live breaker state + fallback counts
- Output publish status

Logs:
- `streamId`, `fragment.id`, `batchNumber`
- Optional rolling audio dumps for debugging

---

## 11. Incremental Build Plan

1. Video passthrough + dubbed audio only
2. Add background separation and remix
3. Add overlap + crossfade
4. Add fallback modes
5. Quality tuning (ducking, normalization)

---

## 12. End-to-end workflow

For a single “how to run it” doc that connects MediaMTX hooks, worker milestones, and validation commands, see `specs/006-end-to-end-workflow.md`.
