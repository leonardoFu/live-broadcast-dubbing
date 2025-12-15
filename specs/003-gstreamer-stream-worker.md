# Unified Worker Spec (Python: GStreamer + STS, MediaMTX ↔ MediaMTX)

This spec defines the **unified worker** referenced by `specs/001-spec.md` and intended to interoperate with `specs/002-mediamtx.md` (MediaMTX ingress/egress).

Primary goals:
- Pull an input stream from **MediaMTX** (RTSP)
- **Demux** into video and audio
- Run **STS** in-process for real-time dubbing
- **Remux** dubbed audio with original video
- Publish processed output back to **MediaMTX** (RTMP)
- Be easy to test locally with strong observability (logs + metrics)

Non-goals:
- Documenting ASR/MT/TTS model internals; see `specs/001-spec.md` and `specs/sources/*`
- Production orchestration (worker autoscaling/lifecycle); see `specs/002-mediamtx.md`

---

## 1. Interfaces (URLs, Codecs, Timing)

### 1.1 Input (MediaMTX → Worker)

- **Preferred input:** RTSP over TCP
- Example: `rtsp://mediamtx:8554/live/<streamId>/in`

Constraints (v1):
- Video: H.264 (passthrough)
- Audio: AAC-LC (decode to PCM inside the worker)

### 1.2 STS (in-process)

STS runs as an in-process module inside the worker.

Required worker behavior:
- Maintain **per-stream FIFO ordering** for audio fragments
- Track **in-flight** fragments and apply timeouts/fallbacks
- Do not log raw audio payloads by default (see Constitution “Secrets & Logs”)

Recommended in-process API boundary (v1):
```python
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class FragmentMeta:
    id: str
    stream_id: str
    batch_number: int
    duration_s: float
    sample_rate: int
    channels: int


@dataclass(frozen=True)
class StsResult:
    dubbed_pcm_s16le: bytes
    warnings: list[str]


class StsBackend:
    def process_fragment(self, meta: FragmentMeta, pcm_s16le: bytes) -> StsResult:  # pragma: no cover (spec)
        raise NotImplementedError
```

### 1.3 Output (Worker → MediaMTX)

- **Publish:** RTMP
- Example: `rtmp://mediamtx:1935/live/<streamId>/out`
- Container: FLV (`flvmux`) containing:
  - video: H.264 (copy)
  - audio: AAC (encoded by worker)

---

## 2. High-Level Dataflow

```
RTSP (MediaMTX)
  |
  v
[GStreamer input pipeline]
  - video: depay + parse  -> python -> appsrc(video)
  - audio: depay + decode -> python -> chunker -> STS (in-process) -> PCM -> mixer -> appsrc(audio)
  |
  v
[GStreamer output pipeline]
  - flvmux -> rtmpsink (MediaMTX)
```

Key principle: **timestamps are the contract**. The worker preserves/derives PTS for:
- Video buffers (passthrough, offset as needed)
- Audio buffers (constructed from fragment timeline, offset as needed)

---

## 3. GStreamer Pipelines (Element Graphs)

### 3.1 Input (RTSP pull → appsinks)

Use one `rtspsrc` with dynamic pads and branch by payload type.

Reference (conceptual):
```gst
rtspsrc location=rtsp://mediamtx:8554/live/<streamId>/in protocols=tcp latency=200 name=src \
  src. ! queue ! rtph264depay ! h264parse config-interval=-1 ! appsink name=vsink sync=false \
  src. ! queue ! rtpmp4gdepay ! aacparse ! avdec_aac ! audioconvert ! audioresample \
       ! audio/x-raw,format=S16LE,rate=48000,channels=2 \
       ! appsink name=asink sync=false
```

Notes:
- Pick a single internal PCM rate for processing (recommend `48000` stereo for “broadcast-like” sources).
- Set `latency=` high enough to avoid jitter underflows in Docker (start at 200–500ms; tune).

### 3.2 Output (appsrcs → flvmux → RTMP push)

Reference (conceptual):
```gst
appsrc name=video_src is-live=true format=time do-timestamp=false block=true \
  ! queue leaky=downstream max-size-time=2000000000 \
  ! h264parse config-interval=-1 \
  ! mux. \
appsrc name=audio_src is-live=true format=time do-timestamp=false block=true \
  caps=audio/x-raw,format=S16LE,rate=48000,channels=2,layout=interleaved \
  ! queue leaky=downstream max-size-time=2000000000 \
  ! audioconvert ! audioresample \
  ! voaacenc bitrate=128000 \
  ! aacparse \
  ! mux. \
flvmux name=mux streamable=true \
  ! rtmpsink location=rtmp://mediamtx:1935/live/<streamId>/out sync=false
```

Notes:
- `sync=false` on `rtmpsink` avoids sink clock selection surprises; the pipeline clock is still used for timestamps.
- `max-size-time` on queues provides bounded buffering; tune together with the expected STS latency.

---

## 4. Audio Chunking + STS Handoff (Worker Logic)

### 4.1 Chunking model

Default (v1):
- Chunk duration: **1.0s**
- Overlap: **0ms** (add later)
- Format inside worker: PCM S16LE @ 48kHz stereo

Implementation sketch:
- `asink` delivers PCM buffers with PTS and duration.
- Accumulate PCM into a “chunk” until `chunk_duration_ns >= target`.
- Emit chunk with metadata:
  - `fragment.id` (uuid)
  - `streamId`
  - `batchNumber` (monotonic)
  - `t0_ns` (start PTS in input timeline)
  - `duration_ns`

### 4.2 STS input/output format (v1)

Since STS runs in-process, the worker uses a simple, test-friendly format:
- Input to STS: PCM S16LE bytes + `sampleRate` + `channels` + `duration`
- Output from STS: PCM S16LE bytes with the same `sampleRate` + `channels` and an effective duration that matches `duration`

Optional (dev-only) artifacting:
- If you want to persist “what STS saw / produced” for debugging, write WAVs (or MP4/AAC) to disk behind an explicit flag.
- Do not log or persist raw audio by default.

### 4.3 Background + dubbed remixing

Worker responsibilities (from `specs/001-spec.md`):
- Run speech/background separation on the original PCM chunk to obtain `background_pcm`.
- Receive dubbed speech as `dubbed_pcm` (from STS).
- Mix:
```text
out_pcm = bg_gain * background_pcm + dub_gain * dubbed_pcm
```

Guards:
- Apply hard limiting/normalization to avoid clipping.
- If STS times out, default to original audio pass-through.

---

## 5. A/V Sync Strategy (Practical, Measurable)

### 5.1 Core approach

Because audio is processed asynchronously, the worker introduces delay. To keep sync:

- Choose an **output timeline origin** `t_out0` when the first buffers arrive.
- Maintain an `av_offset_ns` such that:
  - `video_out_pts = video_in_pts + av_offset_ns`
  - `audio_out_pts = audio_chunk_t0_ns + av_offset_ns`

Set `av_offset_ns` to a fixed “initial buffering” value (e.g., 2–5 seconds) so the worker can:
- hold a small video buffer while waiting for dubbed audio
- avoid negative/rewinding timestamps

v0 decision: use **10s** initial buffering to improve STS stability/quality, accepting higher latency.

### 5.2 Drift measurement + correction

Emit metrics (see §7) for:
- `av_sync_delta_ms = (audio_out_pts - video_out_pts)` sampled periodically

Correction policy (v1, simple):
- If absolute delta exceeds a threshold (e.g., 80–120ms), adjust `av_offset_ns` slowly (slew) rather than hard jumps.

---

## 6. Python Implementation Reference (GObject Introspection)

The worker is written in Python using `gi.repository`:
- `Gst`, `GObject`, `GLib`
- an in-process `StsBackend` implementation (see §1.2)

### 6.1 Minimal worker CLI (proposed)

```sh
python -m stream_worker \
  --stream-id demo \
  --input-rtsp rtsp://localhost:8554/live/demo/in \
  --output-rtmp rtmp://localhost:1935/live/demo/out \
  --sts-mode inprocess \
  --chunk-ms 1000 \
  --log-json
```

### 6.2 Bus + pipeline observability (must-have)

Worker must:
- Log all GStreamer bus `ERROR`/`WARNING` with element name, debug string
- Log state transitions (NULL→READY→PAUSED→PLAYING)
- Emit periodic “health” logs (queue depth, in-flight count, last STS RTT)

### 6.3 Appsink/appsrc loop (reference sketch)

```python
"""
Reference skeleton (not production-ready).

Focus:
- RTSP pull (MediaMTX) -> demux -> appsinks
- video passthrough to RTMP (MediaMTX) via appsrc
- audio chunking + in-process STS + push to RTMP via appsrc
- strong bus logging (errors, warnings, state)
"""

from __future__ import annotations

import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Optional

from gi.repository import GLib, Gst

Gst.init(None)


@dataclass
class PcmChunk:
    fragment_id: str
    batch_number: int
    t0_ns: int
    duration_ns: int
    pcm_s16le: bytes


class Chunker:
    def __init__(self, target_ns: int):
        self._target_ns = target_ns
        self._pending = bytearray()
        self._t0_ns: Optional[int] = None
        self._dur_ns = 0

    def push(self, pcm: bytes, pts_ns: int, dur_ns: int) -> Optional[tuple[bytes, int, int]]:
        if self._t0_ns is None:
            self._t0_ns = int(pts_ns)
        self._pending.extend(pcm)
        self._dur_ns += int(dur_ns)
        if self._dur_ns < self._target_ns:
            return None
        out = (bytes(self._pending), int(self._t0_ns), int(self._dur_ns))
        self._pending.clear()
        self._t0_ns = None
        self._dur_ns = 0
        return out


def _log(event: str, **fields) -> None:
    # Replace with structlog/loguru in implementation; keep correlation fields consistent.
    line = " ".join([event] + [f"{k}={v}" for k, v in sorted(fields.items())])
    print(line, flush=True)


def _attach_bus_logging(pipeline: Gst.Pipeline, *, stream_id: str, run_id: str) -> None:
    bus = pipeline.get_bus()
    bus.add_signal_watch()

    def on_message(_bus, msg):
        t = msg.type
        if t == Gst.MessageType.ERROR:
            err, dbg = msg.parse_error()
            _log("gst_error", streamId=stream_id, runId=run_id, error=str(err), debug=str(dbg))
            pipeline.set_state(Gst.State.NULL)
        elif t == Gst.MessageType.WARNING:
            err, dbg = msg.parse_warning()
            _log("gst_warning", streamId=stream_id, runId=run_id, warning=str(err), debug=str(dbg))
        elif t == Gst.MessageType.STATE_CHANGED and msg.src == pipeline:
            old, new, pending = msg.parse_state_changed()
            _log(
                "gst_state",
                streamId=stream_id,
                runId=run_id,
                old=old.value_nick,
                new=new.value_nick,
                pending=pending.value_nick,
            )

    bus.connect("message", on_message)


def build_input_pipeline(rtsp_url: str) -> Gst.Pipeline:
    launch = f"""
        rtspsrc location="{rtsp_url}" protocols=tcp latency=200 name=src
          src. ! queue ! rtph264depay ! h264parse config-interval=-1 ! appsink name=vsink sync=false
          src. ! queue ! rtpmp4gdepay ! aacparse ! avdec_aac ! audioconvert ! audioresample
               ! audio/x-raw,format=S16LE,rate=48000,channels=2,layout=interleaved
               ! appsink name=asink sync=false
    """
    return Gst.parse_launch(launch)  # type: ignore[return-value]


def build_output_pipeline(rtmp_url: str) -> Gst.Pipeline:
    launch = f"""
        appsrc name=video_src is-live=true format=time do-timestamp=false block=true
          ! queue leaky=downstream max-size-time=2000000000
          ! h264parse config-interval=-1
          ! mux.
        appsrc name=audio_src is-live=true format=time do-timestamp=false block=true
          caps=audio/x-raw,format=S16LE,rate=48000,channels=2,layout=interleaved
          ! queue leaky=downstream max-size-time=2000000000
          ! audioconvert ! audioresample
          ! voaacenc bitrate=128000
          ! aacparse
          ! mux.
        flvmux name=mux streamable=true
          ! rtmpsink location="{rtmp_url}" sync=false
    """
    return Gst.parse_launch(launch)  # type: ignore[return-value]


def push_buffer(appsrc: Gst.Element, buf: Gst.Buffer, *, pts_ns: int, dts_ns: int) -> None:
    out = buf.copy()
    out.pts = int(pts_ns)
    out.dts = int(dts_ns)
    appsrc.emit("push-buffer", out)


def main():
    stream_id = "demo"
    run_id = str(uuid.uuid4())
    rtsp_url = "rtsp://localhost:8554/live/demo/in"
    rtmp_url = "rtmp://localhost:1935/live/demo/out"

    in_pipe = build_input_pipeline(rtsp_url)
    out_pipe = build_output_pipeline(rtmp_url)

    _attach_bus_logging(in_pipe, stream_id=stream_id, run_id=run_id)
    _attach_bus_logging(out_pipe, stream_id=stream_id, run_id=run_id)

    vsink = in_pipe.get_by_name("vsink")
    asink = in_pipe.get_by_name("asink")
    video_src = out_pipe.get_by_name("video_src")
    audio_src = out_pipe.get_by_name("audio_src")

    # Keep a fixed initial delay so video can wait for dubbed audio.
    av_offset_ns = 3_000_000_000

    class MockStsBackend:
        def process_fragment(self, _meta, pcm_s16le: bytes) -> bytes:
            return pcm_s16le

    sts_backend = MockStsBackend()
    executor = ThreadPoolExecutor(max_workers=1)

    batch = 0
    chunker = Chunker(target_ns=1_000_000_000)

    def submit_sts_and_push(chunk: PcmChunk) -> None:
        def work():
            fragment_id = chunk.fragment_id
            started = GLib.get_monotonic_time()
            try:
                dubbed = sts_backend.process_fragment(
                    {
                        "id": fragment_id,
                        "streamId": stream_id,
                        "batchNumber": chunk.batch_number,
                        "duration": chunk.duration_ns / 1_000_000_000,
                        "sampleRate": 48000,
                        "channels": 2,
                    },
                    chunk.pcm_s16le,
                )
                status = "processed"
            except Exception as e:  # fallback: continuity over correctness
                _log("sts_error", streamId=stream_id, runId=run_id, fragmentId=fragment_id, error=str(e))
                dubbed = chunk.pcm_s16le
                status = "fallback"
            rtt_ms = (GLib.get_monotonic_time() - started) / 1000.0

            # Push audio on the main loop thread.
            def push():
                out_buf = Gst.Buffer.new_allocate(None, len(dubbed), None)
                out_buf.fill(0, dubbed)
                out_buf.pts = chunk.t0_ns + av_offset_ns
                out_buf.duration = chunk.duration_ns
                audio_src.emit("push-buffer", out_buf)
                _log(
                    "audio_push",
                    streamId=stream_id,
                    runId=run_id,
                    fragmentId=fragment_id,
                    batchNumber=chunk.batch_number,
                    status=status,
                    stsRttMs=round(rtt_ms, 2),
                )
                return False

            GLib.idle_add(push)

        executor.submit(work)

    # Appsink callbacks
    def on_video_sample(appsink):
        sample = appsink.emit("pull-sample")
        buf = sample.get_buffer()
        push_buffer(video_src, buf, pts_ns=buf.pts + av_offset_ns, dts_ns=buf.dts + av_offset_ns)
        return Gst.FlowReturn.OK

    def on_audio_sample(appsink):
        nonlocal batch
        sample = appsink.emit("pull-sample")
        buf = sample.get_buffer()
        ok, info = buf.map(Gst.MapFlags.READ)
        if not ok:
            return Gst.FlowReturn.ERROR
        try:
            pcm = bytes(info.data)
        finally:
            buf.unmap(info)
        maybe = chunker.push(pcm, pts_ns=buf.pts, dur_ns=buf.duration)
        if maybe is None:
            return Gst.FlowReturn.OK
        pcm_chunk, t0_ns, dur_ns = maybe
        batch += 1
        fragment_id = str(uuid.uuid4())
        chunk = PcmChunk(
            fragment_id=fragment_id,
            batch_number=batch,
            t0_ns=t0_ns,
            duration_ns=dur_ns,
            pcm_s16le=pcm_chunk,
        )
        _log(
            "sts_submit",
            streamId=stream_id,
            runId=run_id,
            fragmentId=fragment_id,
            batchNumber=batch,
            durationMs=dur_ns // 1_000_000,
        )
        submit_sts_and_push(chunk)
        return Gst.FlowReturn.OK

    vsink.connect("new-sample", on_video_sample)
    asink.connect("new-sample", on_audio_sample)

    out_pipe.set_state(Gst.State.PLAYING)
    in_pipe.set_state(Gst.State.PLAYING)

    _log("worker_started", streamId=stream_id, runId=run_id, input=rtsp_url, output=rtmp_url)
    GLib.MainLoop().run()

if __name__ == "__main__":
    main()
```

---

## 7. Observability (Logs + Metrics)

### 7.1 Structured logs

Minimum fields (every log line):
- `streamId`
- `component=unified-worker`
- `runId` (unique per process start)

Per-fragment fields:
- `fragmentId`
- `batchNumber`
- `t0_ms`, `duration_ms`
- `sts_rtt_ms`

Do not log:
- stream keys / credentials
- raw audio bytes (unless explicitly enabled for short-lived debugging)

### 7.2 Metrics (Prometheus)

Expose `GET /metrics` from the worker (port configurable).

Recommended metrics:
- Counters:
  - `worker_audio_fragments_total{status="processed|fallback"}` (count chunks emitted to output)
  - `worker_fallback_total{reason="timeout|error|overload|invalid_output|breaker_open"}`
  - `worker_gst_bus_errors_total`
  - `worker_gst_bus_warnings_total`
- Gauges:
  - `worker_inflight_fragments`
  - `worker_av_sync_delta_ms`
  - `worker_video_queue_ms`, `worker_audio_queue_ms`
  - `worker_sts_breaker_state` (0=closed, 1=half_open, 2=open)
- Histograms:
  - `worker_sts_rtt_ms`
  - `worker_chunk_end_to_end_latency_ms` (ingest PTS → publish PTS)

### 7.3 GStreamer debugging knobs (dev-only)

Recommended environment variables for deep debug (do not enable by default in prod):
```sh
# Bus logs come from the worker; element-level logs come from GStreamer.
export GST_DEBUG=2
export GST_DEBUG_NO_COLOR=1

# Dump pipeline graphs (dot) on state changes and errors.
export GST_DEBUG_DUMP_DOT_DIR=/tmp/gst-dot

# Optional tracers (availability depends on your GStreamer build).
# export GST_TRACERS=latency(flags=pipeline);stats
```

---

## 8. Local Test Workflow

### 8.1 MediaMTX only (baseline)

Use `specs/002-mediamtx.md` to run MediaMTX and publish a test stream to `live/<streamId>/in`.

Sanity checks:
```sh
ffplay rtsp://localhost:8554/live/test-stream/in
ffplay rtmp://localhost:1935/live/test-stream/in
```

### 8.2 Worker “bypass mode” (no STS)

First milestone is a worker that republish-remuxes:
- pull `live/<streamId>/in` via RTSP
- push same A/V to `live/<streamId>/out` via RTMP

This isolates MediaMTX + GStreamer correctness before adding STS latency.

### 8.3 Mock STS (for deterministic tests)

Implement a mock `StsBackend` that returns either:
- pass-through PCM, or
- a deterministic tone synthesized to the requested `duration`

This enables deterministic local tests without running Whisper/TTS (and without any worker↔STS network).

Reference mock (tone backend):
```python
#!/usr/bin/env python3
from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class FragmentMeta:
    id: str
    stream_id: str
    batch_number: int
    duration_s: float
    sample_rate: int
    channels: int


class MockToneStsBackend:
    def process_fragment(self, meta: FragmentMeta, _pcm_s16le: bytes) -> bytes:
        n = int(meta.sample_rate * meta.duration_s)
        t = np.arange(n, dtype=np.float32) / float(meta.sample_rate)
        tone = 0.1 * np.sin(2.0 * math.pi * 440.0 * t)
        tone_i16 = (tone * 32767.0).astype(np.int16)
        if meta.channels == 2:
            tone_i16 = np.repeat(tone_i16[:, None], 2, axis=1).reshape(-1)
        return tone_i16.tobytes()

if __name__ == "__main__":
    # Demo: 1s @ 48kHz stereo
    m = FragmentMeta(id="x", stream_id="demo", batch_number=1, duration_s=1.0, sample_rate=48000, channels=2)
    out = MockToneStsBackend().process_fragment(m, b"")
    print(len(out))
```

### 8.4 End-to-end quickstart (dev)

Assuming MediaMTX is running locally (see `specs/002-mediamtx.md`, or use `make dev` with `deploy/docker-compose.yml`):

For a single “how to run it” flow across MediaMTX + hooks + worker milestones, see `specs/009-end-to-end-workflow.md`.

1) Publish a test stream to `live/<streamId>/in` (choose FFmpeg or GStreamer from `specs/002-mediamtx.md`)
2) Run the worker (reference skeleton):
```sh
# save the snippet in §6.3 as stream_worker.py
python stream_worker.py
```
3) Inspect output:
```sh
ffplay rtmp://localhost:1935/live/test-stream/out
```

In implementation, replace (2) with the real entrypoint and ensure all args are configurable via env/flags.

---

## 9. Failure Handling (Operational Defaults)

Timeouts (suggested):
- STS per-fragment budget: 5–8s (soft) and 10–12s (hard kill / fallback)
- Max in-flight fragments: 3–5 (backpressure; v0 decision: stall output and alert when limit is hit)

Fallbacks:
- STS error/timeout/overload → choose one (configurable):
  - `pass-through` (default): original audio chunk
  - `background-only`: separation output only (if available)
  - `ducked-original`: original audio with aggressive ducking when dub is present
  - `last-good-dub`: repeat last successfully synthesized dub chunk for continuity (use sparingly)
  - `silence`: emit silence of matching duration (last resort)
- Invalid STS output (wrong duration, wrong sample rate/channels, NaNs/clipping) → sanitize (trim/pad/limit) then fallback if still invalid
- Missing video buffers → continue audio (do not stall) but log as degraded
- GStreamer pipeline error → exit non-zero (so orchestration can restart)

Circuit breaker (recommended):
- Open the breaker (disable STS temporarily) when any of the following holds:
  - `N` consecutive STS failures (example: 5)
  - STS latency p95 exceeds a threshold for `T` seconds (example: > 6s for 30s)
  - in-flight queue exceeds a hard limit (example: > 5 chunks)
- While open: continue republishing with the configured fallback (default pass-through).
- Half-open after cooldown (example: 30s): allow 1 chunk through; close on success, re-open on failure.

---

## 10. Acceptance Criteria

- Worker pulls `rtsp://mediamtx:8554/live/<streamId>/in` and publishes `rtmp://mediamtx:1935/live/<streamId>/out`
- Video remains H.264 passthrough (no re-encode), verified by codec inspection
- Audio is replaced by processed audio from STS (or mock STS) without audible gaps
- A/V sync delta remains bounded (target: < 120ms steady-state)
- Logs include stream + fragment correlation ids, and do not include secrets/audio payloads by default
- Metrics endpoint provides at least: STS RTT histogram, in-flight gauge, A/V sync gauge, bus error counter

---

## 11. Open Questions (Confirm Before Implementation)

Resolved decisions (v0):

1) **STS execution model:** run STS in-process (threads), not a subprocess.
2) **Internal audio format:** standardize on `48kHz stereo`.
3) **Initial buffering target:** `10s` initial buffering.
4) **Video passthrough constraints:** “codec copy” is sufficient.
5) **Backpressure policy:** stall output and alert (do not drop audio chunks).
