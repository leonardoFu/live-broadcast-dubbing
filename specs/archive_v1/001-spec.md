
# Live Stream STS Processing & Republish Spec

## 1. Goal

Build a live streaming pipeline that:
- Ingests a live stream via **MediaMTX**
- Processes audio in real time using **STS (Speech → Text → Speech)**
- Preserves original video
- Replaces spoken audio with dubbed audio while keeping background sound
- Republishes the processed stream to a **3rd-party RTMP endpoint**

---

## 2. High-Level Architecture

**Note**: This system deploys as **two separate services** for optimal cost and performance. See `specs/015-deployment-architecture.md` for the full two-service deployment architecture (EC2 + RunPod).

```
[Source Stream]
      |
      v
(MediaMTX Ingest: /live/<streamId>/in) — EC2
      |
      v
[Stream Worker (Python: GStreamer)]       — EC2
  - Demux audio/video
  - Audio chunking
  - Speech/background separation
  - STS Client (calls RunPod STS API)
  - Audio remix
  - Remux A/V
      |                              |
      |                              | (HTTPS to RunPod)
      |                              v
      |                        [STS Service API] — RunPod (GPU)
      |                          - ASR (Whisper)
      |                          - Translation (MT)
      |                          - TTS (Synthesis)
      |                              |
      |                              | (dubbed audio)
      |<─────────────────────────────┘
      v
(MediaMTX Processed Path: /live/<streamId>/out) — EC2
      |
      v
[Egress Forwarder (managed by stream-orchestration)] — EC2
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

### 3.3 Stream Worker (GStreamer + STS Client)

**Deployment**: Runs on EC2 instance (CPU-only, no GPU required)

Responsibilities:
- Pull stream from MediaMTX
- Split audio and video using GStreamer
- Perform speech/background separation (CPU-based)
- Call remote STS Service API on RunPod for GPU processing
- Remix background audio with dubbed audio
- Remux audio with original video
- Push processed stream back to MediaMTX

Design principles:
- Video passthrough whenever possible (H.264)
- Audio decoded to PCM for processing
- Maintain A/V sync using timestamps
- Lightweight CPU operations only (audio processing, mixing)

Implementation spec:
- `specs/003-gstreamer-stream-worker.md`

---

### 3.4 STS Service (Remote API on RunPod)

**Deployment**: Runs on RunPod.io GPU pods for optimal GPU performance and cost

The STS Service is a standalone HTTP/REST API service deployed on RunPod.io that executes GPU-intensive operations (code planned under `apps/sts-service/`).

API contract (see `specs/015-deployment-architecture.md` for details):
- Endpoint: `POST /api/v1/sts/process`
- Input: audio fragment (PCM S16LE, base64-encoded) + config (languages, voice)
- Output: dubbed audio (PCM S16LE, base64-encoded) + metadata

Fragment metadata:
- `fragment_id`: unique identifier
- `stream_id`: stream identifier
- `sequence_number`: monotonic ordering
- `duration_ms`: fragment duration
- `sample_rate`: audio sample rate
- `channels`: audio channels

Audio format (v1):
- PCM S16LE (bytes, base64-encoded), plus `sampleRate` + `channels`

---

## 4. Audio Processing Pipeline

### 4.1 Chunking
- Chunk size: 1–2 seconds
- Optional overlap: 100–200 ms

### 4.2 STS Flow (Remote API Call)
1. Worker chunks audio and prepares fragment for API call
2. Worker sends fragment to RunPod STS Service via HTTPS
3. STS Service processes on GPU:
   - Resample PCM to 16 kHz (ASR path)
   - Whisper transcription (GPU)
   - Translation (GPU)
   - TTS synthesis (GPU)
   - Time-stretch to match duration
4. STS Service returns dubbed PCM audio to worker
5. Worker remixes dubbed audio with background

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
- STS processing (Whisper + TTS)
- Audio separation inference
- Buffering

Expected added latency:
- 3–8 seconds

Knobs:
- Chunk duration
- Max in-flight fragments
- TTS model choice

---

## 8. Failure Handling

### STS Failures / Overload
Policy:
- Prefer continuity: keep republishing even when STS is degraded.
- Use a circuit breaker: if STS is repeatedly failing/slow, temporarily disable STS and use fallbacks.

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

**Stream Infrastructure (EC2)**:
- One Stream Worker per input stream
- Scale by running more EC2 instances for additional concurrent streams
- Each worker independently calls the STS Service API

**STS Service (RunPod)**:
- Vertical scaling: Use larger GPU instances (A5000, A6000) for faster processing
- Horizontal scaling: Deploy multiple RunPod pods behind a load balancer
- On-demand scaling: Start/stop pods based on stream activity

Per-stream FIFO ordering is preserved within each worker.

---

## 10. Observability

Metrics:
- Fragment processing latency
- Queue depth
- A/V sync delta
- STS breaker state + fallback counts
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

For a single “how to run it” doc that connects MediaMTX hooks, worker milestones, and validation commands, see `specs/009-end-to-end-workflow.md`.
