# 013 — Configuration and Defaults

Status: Draft  
Last updated: 2025-12-15

This document is the single source of truth for runtime configuration and defaults across:

- MediaMTX
- `stream-orchestration` (HTTP hook receiver)
- `stream-worker`
- Egress forwarder

It aligns to these repo decisions:

- Stream identity is path-based: `live/<streamId>/in` and `live/<streamId>/out`.
- One worker per stream; stop on `not-ready` after a grace period (default `30s`).
- Worker: STS in-process; internal audio is PCM S16LE @ 48kHz stereo; initial buffering target `10s`; video is codec-copied; backpressure stalls output and alerts.
- Recording is disabled in v0 (`record: no`).
- Dev access is unauthenticated (“everyone”); ops/security hardening is deferred.
- Observability: logs persisted to filesystem in dev; do not log frame-by-frame; log per-fragment operations and errors.
- Cached asset partial/corruption: delete; write via temp file + atomic rename; keep same `runId` for now; add `instanceId` per process.

## 1. Configuration Model

### 1.1 Sources and Precedence

Each component MUST support configuration via environment variables. CLI flags are optional; if present, they MUST override environment variables.

Precedence (highest to lowest):

1. CLI flags (if implemented)
2. Environment variables
3. Component config file (only where the component natively requires it; e.g., MediaMTX YAML)
4. Built-in defaults in this spec

### 1.2 Types and Conventions

- **Boolean**: `true|false` (case-insensitive accepted at parse time; normalized to lowercase).
- **Duration**: Go-style duration strings (e.g., `250ms`, `10s`, `2m`, `1h`). Invalid duration strings are rejected.
- **Integer**: base-10. Range validation is component-specific.
- **String**: trimmed; empty strings are treated as “unset” unless explicitly allowed.

### 1.3 Identifiers

- `streamId`: ASCII string used in the path `live/<streamId>/{in,out}`.
  - Allowed: `A-Z a-z 0-9 _ -` (recommended).
  - Disallowed: `/`, `..`, whitespace, URL-escaped path separators.
- `runId`: logical run identifier for correlated logs/events; v0 keeps a stable `runId` per component start (override allowed).
- `instanceId`: per-process identifier (auto-generated if unset); included in logs and any emitted events.

## 2. Common Observability Configuration (All Components)

These environment variables apply to **every** component in v0.

| Name | Type | Default | Required | Notes / Validation |
|---|---:|---|---:|---|
| `LOG_LEVEL` | string | `info` | optional | One of: `debug`, `info`, `warn`, `error`. Invalid → start fails. |
| `LOG_FORMAT` | string | `json` | optional | One of: `json`, `text`. Invalid → start fails. |
| `LOG_DIR` | string | `./.local/logs` | optional | MUST be writable in dev. If not writable → start fails. |
| `LOG_STDOUT` | bool | `true` | optional | If `false`, logs go only to files. |
| `LOG_FILE_BASENAME` | string | `<component>` | optional | Final filename is implementation-defined but MUST include `runId` and `instanceId`. |
| `RUN_ID` | string | auto | optional | If set, MUST be non-empty and <= 64 chars. |
| `INSTANCE_ID` | string | auto | optional | If set, MUST be non-empty and <= 64 chars. |

Logging requirements (behavioral, not knobs):

- Do not log per-frame.
- Do log per-fragment lifecycle (ingest fragment → STS started → STS completed → mux/publish) and any errors.

## 3. MediaMTX Configuration

MediaMTX configuration is primarily via YAML. Environment variables MAY be used by the deployment to template the YAML, but this spec defines the required effective settings.

### 3.1 Effective Defaults (v0)

- Recording MUST be disabled (`record: no`).
- Two path patterns MUST exist:
  - `live/*/in`: ingest endpoint for publishers.
  - `live/*/out`: publish endpoint for `stream-worker` output.
- Dev access control: unauthenticated (no auth).
- Hooks: send “ready/not-ready” signals to `stream-orchestration`.

### 3.2 Minimal MediaMTX YAML (v0)

This is a minimal reference configuration; deployments may add non-conflicting keys.

```yaml
# mediamtx.yml (reference)
logLevel: info

api: yes
apiAddress: :9997

rtsp: yes
rtspAddress: :8554

rtmp: yes
rtmpAddress: :1935

hls: no
webrtc: no

paths:
  # Ingest path(s)
  'live/*/in':
    source: publisher
    record: no
    # Hook pattern: invoke orchestration hook receiver.
    # Implementation note: MediaMTX hooks are command-based; deployments commonly use curl.
    runOnReady: >-
      sh -lc 'curl -sS -X POST "$${ORCH_HOOK_BASE_URL}/hooks/mediamtx/on-ready"
      -H "Content-Type: application/json"
      -d "{\"path\":\"$MTX_PATH\",\"runId\":\"$${RUN_ID:-}\",\"instanceId\":\"$${INSTANCE_ID:-}\"}"'
    runOnNotReady: >-
      sh -lc 'curl -sS -X POST "$${ORCH_HOOK_BASE_URL}/hooks/mediamtx/on-not-ready"
      -H "Content-Type: application/json"
      -d "{\"path\":\"$MTX_PATH\",\"runId\":\"$${RUN_ID:-}\",\"instanceId\":\"$${INSTANCE_ID:-}\"}"'

  # Worker output path(s)
  'live/*/out':
    source: publisher
    record: no
```

### 3.3 MediaMTX Environment Variables (used by deployment templating)

| Name | Type | Default | Required | Notes / Validation |
|---|---:|---|---:|---|
| `MEDIAMTX_CONFIG_PATH` | string | `./mediamtx.yml` | optional | If used by launcher; if file missing → start fails. |
| `MEDIAMTX_API_ADDRESS` | string | `:9997` | optional | Must be valid host:port or :port. |
| `MEDIAMTX_RTSP_ADDRESS` | string | `:8554` | optional | Must be valid host:port or :port. |
| `MEDIAMTX_RTMP_ADDRESS` | string | `:1935` | optional | Must be valid host:port or :port. |
| `ORCH_HOOK_BASE_URL` | string | `http://stream-orchestration:8080` | optional | MUST be set if hooks are enabled in YAML. |

Validation rules:

- If `runOnReady/runOnNotReady` hooks are enabled and `ORCH_HOOK_BASE_URL` is empty → MediaMTX deployment is invalid (fail startup).
- If recording is enabled anywhere under `paths` in v0 → invalid config (fail startup).

Observability impact:

- MediaMTX `logLevel` controls verbosity; v0 defaults to `info`.
- Hook failures MUST not be logged per-frame; only per event (ready/not-ready).

## 4. `stream-orchestration` Configuration

`stream-orchestration` is an HTTP service receiving MediaMTX hooks and managing `stream-worker` lifecycle.

### 4.1 Environment Variables / Flags

| Name / Flag | Type | Default | Required | Notes / Validation |
|---|---:|---|---:|---|
| `ORCH_HTTP_ADDR` / `--http-addr` | string | `0.0.0.0:8080` | optional | Must be valid host:port. |
| `ORCH_GRACE_PERIOD` / `--grace-period` | duration | `30s` | optional | Must be `>= 0s` and `<= 5m`. |
| `ORCH_WORKER_MODE` / `--worker-mode` | string | `process` | optional | One of: `process` (spawn local), `external` (no spawn; emit events only). |
| `ORCH_WORKER_COMMAND` / `--worker-command` | string | `stream-worker` | required (if `process`) | Must resolve on PATH or be absolute; if missing → start fails. |
| `ORCH_WORKER_ARGS_TEMPLATE` / `--worker-args-template` | string | see below | optional | Template supports `{{streamId}}`, `{{runId}}`, `{{instanceId}}`. Invalid template → start fails. |
| `ORCH_MEDIAMTX_HOST` | string | `mediamtx` | optional | Used to build default worker URLs when args template not provided. |
| `ORCH_MEDIAMTX_RTSP_PORT` | int | `8554` | optional | Range `1..65535`. |
| `ORCH_STREAM_ID_FROM_PATH_REGEX` | string | `^live/([^/]+)/(in|out)$` | optional | Must compile; if not → start fails. |
| `ORCH_STATE_DIR` | string | `./.local/state/stream-orchestration` | optional | MUST be writable; if not → start fails. |
| `ORCH_MAX_WORKERS` | int | `0` | optional | `0` means “no limit”; otherwise `>= 1`. |

Default `ORCH_WORKER_ARGS_TEMPLATE` (when `process` mode and no template specified):

```text
--stream-id={{streamId}}
--input-url=rtsp://mediamtx:8554/live/{{streamId}}/in
--output-url=rtsp://mediamtx:8554/live/{{streamId}}/out
--buffer-target=10s
--run-id={{runId}}
--instance-id={{instanceId}}
```

### 4.2 Behavioral Defaults

- `on-ready` for `live/<streamId>/in`:
  - Ensure exactly one worker per `streamId`.
  - If no worker is running, start it (or emit “start requested” event in `external` mode).
  - If a worker is running, treat as idempotent and only refresh last-seen readiness timestamp.
- `on-not-ready` for `live/<streamId>/in`:
  - Start a grace timer (default `30s`).
  - If the stream becomes ready again before grace expires, cancel the stop.
  - Otherwise stop the worker for that `streamId`.

### 4.3 Validation Rules and Failure Modes

- Invalid hook payload (missing `path` or invalid `path` format) → HTTP `400`; log one error event.
- If `ORCH_WORKER_MODE=process` and a worker cannot be spawned → log error; keep retrying only when a new `on-ready` arrives (no tight loop).
- If `ORCH_MAX_WORKERS` is reached:
  - `on-ready` → HTTP `429` with a stable error code; log warning.
  - No worker is started.

Observability impact:

- `ORCH_GRACE_PERIOD` affects the timing of stop events and log cadence (one log at not-ready, one at stop/cancel).
- `ORCH_STATE_DIR` SHOULD contain rolling state snapshots useful in dev debugging; do not write per-frame data.

## 5. `stream-worker` Configuration

`stream-worker` pulls `live/<streamId>/in`, processes audio through in-process STS, and publishes `live/<streamId>/out`. Video MUST be codec-copied.

### 5.1 Environment Variables / Flags

| Name / Flag | Type | Default | Required | Notes / Validation |
|---|---:|---|---:|---|
| `WORKER_STREAM_ID` / `--stream-id` | string | (none) | required | Must satisfy `streamId` rules. |
| `WORKER_INPUT_URL` / `--input-url` | string | derived | optional | If unset, derived from `WORKER_MEDIAMTX_HOST/PORT` and `streamId`. |
| `WORKER_OUTPUT_URL` / `--output-url` | string | derived | optional | If unset, derived from `WORKER_MEDIAMTX_HOST/PORT` and `streamId`. |
| `WORKER_MEDIAMTX_HOST` | string | `mediamtx` | optional | Used for derived URLs. |
| `WORKER_MEDIAMTX_RTSP_PORT` | int | `8554` | optional | Range `1..65535`. |
| `WORKER_BUFFER_TARGET` / `--buffer-target` | duration | `10s` | optional | Must be `>= 0s` and `<= 60s`. |
| `WORKER_READY_TIMEOUT` / `--ready-timeout` | duration | `15s` | optional | Time to wait for input to become readable before erroring; `>= 1s`. |
| `WORKER_VIDEO_MODE` / `--video-mode` | string | `copy` | optional | v0 only supports `copy`. Any other value → start fails. |
| `WORKER_AUDIO_PCM_FORMAT` | string | `s16le` | optional | v0 requires `s16le`; if set to other → start fails. |
| `WORKER_AUDIO_SAMPLE_RATE_HZ` | int | `48000` | optional | v0 requires `48000`; if set to other → start fails. |
| `WORKER_AUDIO_CHANNELS` | int | `2` | optional | v0 requires `2`; if set to other → start fails. |
| `WORKER_STS_MODE` / `--sts-mode` | string | `enabled` | optional | One of: `enabled`, `passthrough`, `disabled`. |
| `WORKER_STS_PROVIDER` / `--sts-provider` | string | `mock` | optional | One of: `mock`, `local`, `cloud`. Invalid → start fails. |
| `WORKER_SOURCE_LANG` | string | `en` | optional | BCP-47 or short code; validation is provider-specific. |
| `WORKER_TARGET_LANG` | string | `en` | optional | BCP-47 or short code; validation is provider-specific. |
| `WORKER_TTS_VOICE` | string | `default` | optional | Provider-specific voice name. |
| `WORKER_CACHE_DIR` | string | `./.local/cache/stream-worker` | optional | Must be writable; if not → start fails. |
| `WORKER_CACHE_MAX_BYTES` | int | `1073741824` | optional | `>= 0`. `0` disables cache. |
| `WORKER_BACKPRESSURE_MODE` | string | `stall` | optional | v0 requires `stall`. Any other value → start fails. |
| `WORKER_BACKPRESSURE_MAX_BUFFERED_AUDIO` | duration | `3s` | optional | When exceeded, worker MUST stall output and emit an alert log event; `>= 0s`. |
| `WORKER_FRAGMENT_TARGET_DUR` | duration | `2s` | optional | Logical fragment size for per-fragment logging and STS batching; `>= 250ms` and `<= 10s`. |
| `WORKER_ASSETS_DIR` | string | `./.local/assets/stream-worker` | optional | Used for provider assets/models; must be writable if used. |

Derived defaults:

- If `WORKER_INPUT_URL` is unset: `rtsp://<WORKER_MEDIAMTX_HOST>:<WORKER_MEDIAMTX_RTSP_PORT>/live/<streamId>/in`
- If `WORKER_OUTPUT_URL` is unset: `rtsp://<WORKER_MEDIAMTX_HOST>:<WORKER_MEDIAMTX_RTSP_PORT>/live/<streamId>/out`

### 5.2 Cache Integrity Rules (v0)

- Cached writes MUST use “temp file + fsync (where available) + atomic rename” semantics.
- On read:
  - If a cached asset is partial/corrupt, delete it and regenerate.
  - Corruption is defined as: decode/parse failure, checksum mismatch (if used), or unexpected EOF.
- Cache keys MUST include provider, source/target language, voice, and any model identifiers to avoid cross-contamination.

### 5.3 Validation Rules and Failure Modes

- Missing `WORKER_STREAM_ID` → start fails.
- Invalid URL syntax for `WORKER_INPUT_URL`/`WORKER_OUTPUT_URL` → start fails.
- If `WORKER_STS_MODE=enabled`:
  - Provider `mock` requires no additional config; it produces deterministic placeholder output.
  - Provider `local` MAY require `WORKER_ASSETS_DIR` to exist/writable; if not, start fails.
  - Provider `cloud` MUST fail fast at startup if required cloud credentials are missing (credential names are provider-specific and out of scope for v0).
- If backpressure thresholds are exceeded:
  - Worker MUST stall output (not drop video/audio silently).
  - Worker MUST emit an “alert” log event once per incident (no per-frame spam), including `streamId`, `runId`, `instanceId`, and current buffered durations.

Observability impact:

- `WORKER_FRAGMENT_TARGET_DUR` affects log volume (per fragment) and STS batch cadence.
- `WORKER_BUFFER_TARGET` affects startup latency and the timing of the first fragment logs.

## 6. Egress Forwarder Configuration

The egress forwarder republishes `live/<streamId>/out` to one or more external destinations (e.g., RTMP endpoints). In v0, it is optional and disabled by default.

### 6.1 Environment Variables / Flags

| Name / Flag | Type | Default | Required | Notes / Validation |
|---|---:|---|---:|---|
| `EGRESS_ENABLED` / `--enabled` | bool | `false` | optional | If `false`, process may be omitted entirely. |
| `EGRESS_INPUT_BASE_URL` / `--input-base-url` | string | `rtsp://mediamtx:8554` | required (if enabled) | Must be valid URL base. |
| `EGRESS_RULES_JSON` / `--rules-json` | string | (none) | required (if enabled) | JSON string; invalid JSON → start fails. |
| `EGRESS_BACKPRESSURE_MODE` | string | `stall` | optional | v0 requires `stall`. Any other value → start fails. |
| `EGRESS_MAX_DESTINATION_FAILURES` | int | `3` | optional | `>= 1`. After exceeded, stop forwarding that destination and emit alert. |
| `EGRESS_RETRY_BACKOFF` | duration | `5s` | optional | `>= 0s` and `<= 1m`. |

`EGRESS_RULES_JSON` schema (v0):

```json
{
  "version": 1,
  "rules": [
    {
      "streamId": "example",
      "destinations": [
        { "name": "primary", "url": "rtmp://example.com/app/streamKey" }
      ]
    }
  ]
}
```

Rules:

- Each `streamId` maps to `live/<streamId>/out` as the input stream.
- If `EGRESS_ENABLED=true` and there is no matching rule for an observed `streamId`, the forwarder MUST skip it and log one warning event (no repeated spam).

Observability impact:

- Destination failures MUST be logged per incident with backoff-aware cadence, not per packet/frame.

## 7. Recommended Dev Defaults (Cross-Component)

These defaults are recommended for local development (v0):

- `WORKER_BUFFER_TARGET=10s`
- `ORCH_GRACE_PERIOD=30s`
- `LOG_FORMAT=json`
- `LOG_LEVEL=info` (use `debug` only when diagnosing a specific issue)
- Log persistence enabled via `LOG_DIR=./.local/logs` and `LOG_STDOUT=true`
- MediaMTX recording disabled (`record: no`)
- Unauthenticated dev access (no auth)

## 8. Minimal Required Configuration to Run Locally (v0)

Local runs SHOULD require only:

- MediaMTX with:
  - RTSP enabled (internal transport for worker/forwarder).
  - RTMP enabled (optional; for common broadcaster ingest).
  - Paths `live/*/in` and `live/*/out` with `record: no`.
  - Hooks wired to `stream-orchestration`.
- `stream-orchestration` reachable by MediaMTX at `ORCH_HOOK_BASE_URL`.
- Worker spawning enabled (`ORCH_WORKER_MODE=process`) or an external equivalent that ensures one worker per stream.

Suggested minimal environment (example only; not a required file format):

```text
# stream-orchestration
ORCH_HTTP_ADDR=0.0.0.0:8080
ORCH_GRACE_PERIOD=30s
ORCH_WORKER_MODE=process
ORCH_WORKER_COMMAND=stream-worker

# stream-worker (when launched by orchestrator, values are passed as flags)
WORKER_BUFFER_TARGET=10s
WORKER_STS_PROVIDER=mock

# shared
LOG_DIR=./.local/logs
LOG_LEVEL=info
LOG_FORMAT=json
```

## 9. Validation Rules (Summary)

All components MUST validate configuration at startup and fail fast with a non-zero exit code on invalid configuration, including:

- Invalid durations, ports, URLs, enums.
- Unwritable required directories (`LOG_DIR`, component state/cache directories).
- v0-incompatible settings (e.g., video mode not `copy`, audio format not S16LE/48kHz/2ch, recording enabled).

Runtime validation:

- Hook endpoints MUST return `4xx` on invalid payloads and MUST not crash.
- Backpressure incidents MUST be observable via alert logs and MUST stall output rather than silently dropping.

## 10. Acceptance Criteria

- This spec enumerates configuration for MediaMTX, `stream-orchestration`, `stream-worker`, and the egress forwarder, including name, type, default, and required/optional semantics.
- Dev defaults include worker buffering target `10s` and orchestrator grace period `30s`, with recording disabled and unauthenticated dev access.
- Minimal local configuration is described without requiring recording or authentication.
- Validation behavior is defined for missing/invalid config and v0-incompatible settings.
- Observability impacts of configuration (log level/format, fragment sizing, grace period, backpressure) are documented and avoid frame-by-frame logging.
