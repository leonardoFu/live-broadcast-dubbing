# 014 — Asset Store and Run Bundles

## Goal
Define a filesystem-backed “run bundle” format that reconciles STS pipeline asset expectations with observability:

- Default to **metadata-only capture** (always-on manifests + structured logs).
- Allow **opt-in media capture** (audio snippets, intermediate artifacts) without changing pipeline semantics.
- Provide stable correlation keys across logs and files: `streamId`, `runId` (stream-session), `instanceId` (process).

## Non-goals
- Security hardening, authn/z, encryption at rest, or multi-tenant isolation (deferred).
- Cross-host replication, object storage, or remote uploads (v0 is local filesystem).
- Deterministic, lossless capture of *all* media in real time (media capture is best-effort and can be throttled).
- Recording the full input/output streams (recording disabled in v0; MediaMTX `record: no`).

## Terms
- `streamId`: Path-based stream identity. Input path `live/<streamId>/in`, output path `live/<streamId>/out`.
- `runId`: A single stream session (from worker start for a stream until stop).
- `instanceId`: Per-process ID (unique per worker process lifetime; stable across all runs handled by that process).
- Fragment: The worker’s processing unit for audio (e.g., ~N seconds of PCM) that is transcribed/translated/synthesized.

## Capture policy (metadata-first)
The worker MUST always emit:

- A per-run manifest (`manifest.json`) with fragment-level metadata, errors, and summary counters.
- Structured log events for per-fragment operations and asset writes (no frame-by-frame logging).

Media capture is opt-in and MUST be explicitly enabled by configuration (exact config keys are implementation-defined in v0). When disabled, the worker MUST NOT write audio/video media assets; it MAY still write small text/json artifacts that are required for debugging (e.g., per-fragment STT results) as long as they are considered “metadata”.

Recommended capture modes (informative):

- `metadata`: default; manifest + logs + optional per-fragment JSON/text outputs.
- `media`: additionally write selected audio artifacts (PCM/WAV segments, synthesized audio segments).
- `debug`: additionally write verbose internal traces; may be large; not intended for always-on use.

## Asset store root
All run bundles live under a single configured root directory:

- `assetStoreRoot`: absolute path inside the worker runtime filesystem.

Requirements:

- The root MUST be on a local filesystem that supports atomic rename within the same directory.
- The root MUST be writable by the worker.
- Dev environments SHOULD mount it to persist across restarts (observability persistence requirement).

## Directory layout and naming conventions
Run bundles are organized by `streamId` and `runId`:

```text
<assetStoreRoot>/
  streams/
    <streamId>/
      runs/
        <runId>/
          manifest.json
          manifest.history/
            <ts>-<seq>.json
          assets/
            fragments/
              <fragmentId>/
                stt.json
                tts.json
                timing.json
                in.pcm               (opt-in; S16LE 48k stereo)
                in.wav               (opt-in; derived from in.pcm)
                out.wav              (opt-in; synthesized segment)
            alerts/
              <ts>-<kind>.json
          logs/
            worker.log              (optional file sink; implementation-defined)
          tmp/
            .tmp.<random>.<name>    (ephemeral; cleaned on start)
```

### Path safety
- `<streamId>` MUST be treated as a path segment, not an arbitrary path; it MUST NOT allow `..` traversal.
- If `streamId` can contain characters outside `[A-Za-z0-9._-]`, it MUST be encoded into a filesystem-safe form (implementation-defined; must be reversible).
- `<runId>` SHOULD be unique and sortable (e.g., `YYYYMMDDThhmmssZ-<rand>`). It MUST be safe as a path segment.

### `fragmentId`
- MUST be unique within a run.
- SHOULD be monotonic and sortable to make timelines easy to browse.
- Suggested format (informative): `<seq>-<startMs>-<endMs>` where `seq` is zero-padded.

## Manifest (JSON) requirements
Each run MUST have a single canonical manifest at:

- `<assetStoreRoot>/streams/<streamId>/runs/<runId>/manifest.json`

The manifest MUST be valid JSON and MUST conform to the schema rules below.

### Manifest update model
- The worker SHOULD update the manifest incrementally as fragments are processed.
- Each update MUST be written atomically (temp file + fsync + atomic rename).
- The worker MAY also snapshot prior versions under `manifest.history/` (recommended for debugging; optional in v0).

### Required fields
The manifest MUST include at least:

- `schemaVersion` (string): version of this manifest format (e.g., `"1.0"`).
- `streamId` (string)
- `runId` (string)
- `instanceId` (string)
- `createdAt` (RFC3339 string)
- `updatedAt` (RFC3339 string)
- `streamPaths` (object):
  - `in` (string): `live/<streamId>/in`
  - `out` (string): `live/<streamId>/out`
- `pipeline` (object):
  - `pcm` (object):
    - `sampleRateHz` (number): `48000`
    - `channels` (number): `2`
    - `format` (string): `"s16le"`
  - `bufferingTargetSec` (number): default `10`
  - `videoMode` (string): `"copy"` (codec copy)
- `capture` (object):
  - `mode` (string): `"metadata"` | `"media"` | `"debug"`
  - `mediaEnabled` (boolean)
- `fragments` (array): may be empty; see below for per-fragment minimum.
- `counters` (object): numeric counters (e.g., fragments processed, bytes written); may be empty.
- `errors` (array): may be empty.

Per-fragment entries in `fragments` MUST include at least:

- `fragmentId` (string)
- `seq` (number)
- `time` (object):
  - `startMs` (number)
  - `endMs` (number)
- `status` (string): `"received"` | `"processing"` | `"processed"` | `"failed"`
- `assets` (array): list of assets written for that fragment; may be empty.

Each asset entry in a fragment’s `assets` array MUST include at least:

- `kind` (string): e.g., `stt-json`, `tts-json`, `timing-json`, `in-pcm`, `in-wav`, `out-wav`, `alert-json`
- `path` (string): bundle-relative path under the run directory
- `bytes` (number)
- `sha256` (string) OR `integrity` (object) with at least one checksum field (implementation-defined); checksums are strongly recommended for media assets
- `writtenAt` (RFC3339 string)

Errors in `errors` MUST include at least:

- `at` (RFC3339 string)
- `scope` (string): `run` | `fragment` | `asset`
- `message` (string)
- `fragmentId` (string, optional)
- `assetPath` (string, optional)

### Example manifest JSON
```json
{
  "schemaVersion": "1.0",
  "streamId": "demo-123",
  "runId": "2025-12-15T10-11-12Z-k7m2r9",
  "instanceId": "worker-01HZY2Q8Z0X7Y8T9J2NQ9ZQ0W5",
  "createdAt": "2025-12-15T10:11:12.345Z",
  "updatedAt": "2025-12-15T10:12:03.210Z",
  "streamPaths": {
    "in": "live/demo-123/in",
    "out": "live/demo-123/out"
  },
  "pipeline": {
    "pcm": { "sampleRateHz": 48000, "channels": 2, "format": "s16le" },
    "bufferingTargetSec": 10,
    "videoMode": "copy"
  },
  "capture": { "mode": "metadata", "mediaEnabled": false },
  "counters": {
    "fragmentsReceived": 3,
    "fragmentsProcessed": 2,
    "assetsWritten": 5,
    "bytesWritten": 18234
  },
  "fragments": [
    {
      "fragmentId": "0001-10000-15000",
      "seq": 1,
      "time": { "startMs": 10000, "endMs": 15000 },
      "status": "processed",
      "latency": {
        "sttMs": 420,
        "translateMs": 0,
        "ttsMs": 610,
        "totalMs": 1215
      },
      "assets": [
        {
          "kind": "stt-json",
          "path": "assets/fragments/0001-10000-15000/stt.json",
          "bytes": 901,
          "sha256": "6a1a5a4b4c3d7c2f08cdbb8f7c6d3cde4e6c7bda0fd9e6a4a4d7c2c9e2b1a0f1",
          "writtenAt": "2025-12-15T10:11:58.101Z"
        },
        {
          "kind": "timing-json",
          "path": "assets/fragments/0001-10000-15000/timing.json",
          "bytes": 312,
          "sha256": "9a0d8f1a2b3c4d5e6f77889900aabbccddeeff00112233445566778899aabbcc",
          "writtenAt": "2025-12-15T10:11:58.120Z"
        }
      ]
    }
  ],
  "errors": []
}
```

## Atomic write, partial/corrupt handling, and startup cleanup
All assets and manifests MUST be written using a temp file and atomic rename:

- Write to `<runDir>/tmp/.tmp.<random>.<targetFilename>` in the same filesystem.
- Flush file contents and metadata (implementation-defined; fsync strongly recommended).
- Atomically rename to the final destination path.

Rules:

- If a write fails, the worker MUST delete the temp file.
- If a target asset is detected to be partial or corrupt (size mismatch, checksum mismatch, invalid JSON), the worker MUST delete the final asset path and treat it as missing.
- The worker MUST perform startup cleanup for each run directory it touches:
  - Delete any files under `tmp/` (including stale `.tmp.*`).
  - Optionally delete orphaned zero-byte assets and/or assets failing integrity checks when referenced by the manifest.

Rationale: ensures readers never observe partially written files; avoids “cached asset partial/corruption” issues by construction.

## Retention / purge rules (v0)
Retention is intentionally simple in v0:

- Default retention window: keep run bundles for the last **7 days** (configurable).
- Purge policy: best-effort deletion on worker startup and periodically (implementation-defined), excluding:
  - The currently active run directory.
  - Runs updated within the last retention window.

Deletion order guidance (informative):

1. Delete `assets/` first (largest).
2. Delete `logs/`.
3. Delete `manifest.history/`.
4. Delete `manifest.json` last.

If purge fails (permissions, in-use files), emit an error log event and continue; do not crash the worker.

## Observability: fields emitted on asset/manifest writes
When writing an asset or manifest, the worker MUST emit one structured log event per write attempt (not per frame), with at least:

- `event`: `"asset_write"` or `"manifest_write"`
- `streamId`, `runId`, `instanceId`
- `fragmentId` (optional; required for per-fragment assets)
- `assetKind` (for `asset_write`)
- `path` (absolute or bundle-relative; must be consistent)
- `bytes` (written; 0 on failure if unknown)
- `sha256` (if computed)
- `status`: `"ok"` | `"error"`
- `error`: object on failure (message + code/class)
- `ts`: RFC3339 timestamp

Additional recommended fields (informative):

- `durationMs` (time spent writing)
- `io`: `{ "tempPath": "...", "finalPath": "...", "atomicRename": true }`
- `integrity`: `{ "checked": true, "result": "ok" | "mismatch" }`
- `pipelineStage`: e.g., `fragment:data`, `fragment:processed`
- `backpressure`: `{ "stalled": true, "reason": "asset_store_slow" }` when output stalls and alerts fire

## Interaction with worker lifecycle
- One worker handles exactly one `streamId` at a time.
- A run bundle is created at worker start for that `streamId` and closed when the worker exits.
- If the worker enters “not-ready” and remains not-ready beyond the grace period (default 30s), the worker stops; the manifest SHOULD be updated with a terminal status and error reason before exit (best-effort).
- The `runId` stays stable for the run bundle lifetime; do not rotate `runId` on partial failures.
- `instanceId` stays stable for the process lifetime; include it in every log line and manifest.

## Acceptance criteria
- A run always produces `manifest.json` containing `streamId`, `runId`, `instanceId`, `streamPaths.in/out`, and PCM format details (S16LE 48kHz stereo).
- Default behavior writes metadata only; media assets are never written unless capture mode enables them.
- All writes (assets + manifest) use temp file + atomic rename; partial temp files are deleted on failure and cleaned on startup.
- On detecting a corrupt/partial asset, the worker deletes it and records an error in `manifest.json` and structured logs.
- Every asset/manifest write emits a single structured log event containing `streamId`, `runId`, `instanceId`, plus `fragmentId` when applicable.
- Purge removes old run bundles according to the v0 retention rule without deleting the currently active run.
