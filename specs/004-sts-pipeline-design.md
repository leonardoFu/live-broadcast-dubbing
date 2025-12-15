# STS Pipeline Design (Flexible, Async, Testable)

## 1. Goal

Define a **Speech → Text → Speech (STS)** design that supports live-stream dubbing as described in `specs/001-spec.md`, while making ASR / Translate / TTS:
- **Abstract and replaceable** (swappable providers/implementations)
- **Async-first** (can be concurrent without losing ordering guarantees)
- **Easy to integrate** as an importable (in-process) Python module (primary) and in offline runs (secondary)
- **Easy to test** with deterministic stubs (e.g., mock ASR returns static text)
- **Traceable** with clear inputs/outputs and trackable intermediate assets

## 2. Non-Goals

- Define the GStreamer/MediaMTX streaming pipelines (see `specs/001-spec.md` and `specs/003-gstreamer-stream-worker.md`).
- Choose specific vendors/models for ASR/MT/TTS.
- Solve all audio DSP details (time-stretching, separation, mixing); only define STS boundaries and required artifacts.

## 3. Design Principles

- **Contracts over implementations**: all components conform to the same minimal interface and can be replaced without changing the pipeline orchestration.
- **Determinism for tests**: the same inputs yield the same outputs under stubs; real providers are isolated behind contracts.
- **Traceable lineage**: every output references its input(s) and records provenance (component name/version, timestamps, parameters).
- **Streaming-friendly**: works on short fragments with ordering, retries, and backpressure.
- **Failure-tolerant**: partial outputs are still recorded; fallbacks are explicit and testable.

## 4. Pipeline Model

An STS “pipeline” is a composition of independent components connected by typed inputs/outputs.

### 4.1 Standard Stages

The default logical stages:
1. **ASR**: audio → transcript (and optionally word-level timestamps)
2. **Translate** (optional): transcript → translated transcript
3. **TTS**: text → synthesized speech audio

Stages are optional and replaceable. For example:
- ASR + TTS (same-language “voice replacement”)
- ASR + Translate + TTS (cross-language dubbing)
- Translate omitted (pass-through source text)

### 4.2 Ordering & Concurrency Model (Live Fragments)

- Inputs arrive as **audio fragments** (e.g., 1–2s chunks).
- The pipeline MAY process multiple fragments concurrently.
- For a given `stream_id`, the pipeline MUST provide:
  - **Ordered output emission** by `sequence_number` (even if processed out of order).
  - **At-least-once stage execution** with idempotency support via stable IDs (see §5).
  - **Configurable maximum in-flight fragments** for backpressure.

## 5. Data Contracts (Inputs, Outputs, Assets)

### 5.1 Core Identifiers

All artifacts MUST carry:
- `stream_id`: logical stream/session identifier
- `sequence_number`: monotonically increasing fragment index within stream
- `asset_id`: globally unique identifier for the artifact
- `parent_asset_ids`: references to upstream assets used to create this artifact
- `created_at`: timestamp
- `component`: name of the component that produced it (e.g., `asr`, `translate`, `tts`)
- `component_instance`: a provider identifier (e.g., “provider-A”, “mock-asr-v1”)

### 5.2 Input: Audio Fragment

Minimum fields:
- `stream_id`, `sequence_number`
- `audio_format` (e.g., codec/PCM description)
- `sample_rate_hz`, `channels`
- `start_time_ms`, `end_time_ms` (relative to stream timeline)
- `payload_ref` (reference to bytes in-memory or to a stored asset)

### 5.3 Output: STS Result (Per Fragment)

The pipeline returns a single top-level result object per fragment that links all intermediate assets:
- `input_audio_fragment_asset`
- `asr_transcript_asset` (optional if ASR skipped)
- `translated_text_asset` (optional if translate skipped)
- `tts_audio_asset` (optional if TTS skipped)
- `final_text` (the text that was spoken in synthesized audio, if any)
- `status`: `success | partial | failed | skipped`
- `errors`: structured list (stage, error_type, retryable, message)

### 5.4 Trackable Intermediate Assets

The system MUST be able to record and retrieve (at minimum for tests/debugging):
- Raw input fragment audio reference
- ASR transcript (with optional timestamps and confidence metadata)
- Translation text (with source/target language metadata)
- Synthesized speech audio reference

Recommended optional assets:
- Normalized/cleaned text (before TTS)
- Alignment/time-stretch metadata (requested duration, achieved duration)
- Per-stage timing metrics (queue time, processing time)

### 5.5 Asset Store Expectations

The design assumes an “asset store” abstraction that supports:
- Writing assets with stable IDs and metadata
- Reading assets by ID
- Listing by `stream_id` and `sequence_number`
- Retaining assets long enough for debugging and tests

Default operational policy:
- Persist intermediate assets to a **local filesystem** location for every run (for observation/debugging).
- Apply **time-based retention** (e.g., keep last N hours/days) with a **batch cleanup** capability to purge old runs.

## 6. Component Contracts (Abstract, Async, Replaceable)

Each stage is a component with a narrow interface that can be implemented by:
- A real provider (remote or local)
- A stub/mock for tests
- A “composite” component (e.g., translate+glossary enforcement)

### 6.1 Common Component Behavior

All components MUST:
- Be callable asynchronously (non-blocking to the pipeline orchestrator)
- Accept a request object that includes stable IDs and required context
- Return either:
  - A success response with a produced asset (and metadata), or
  - A failure response with a structured error (retryable vs non-retryable)

All components SHOULD:
- Be pure with respect to the pipeline (no hidden dependencies on global state)
- Produce deterministic outputs in stub mode

### 6.2 ASR Component Contract

```
Input:  AudioFragment
Output: TranscriptAsset
Required metadata: language (detected or specified), optional word timings
```

### 6.3 Translate Component Contract

```
Input:  TranscriptAsset (or TextAsset)
Output: TextAsset
Required metadata: source_language, target_language
```

### 6.4 TTS Component Contract

```
Input:  TextAsset (+ desired voice/style context)
Output: AudioAsset (synth speech)
Required metadata: sample_rate_hz, channels, duration_ms (actual)
```

## 7. Pipeline Orchestration Requirements

### 7.1 Configuration (Per Stream)

Pipeline configuration SHOULD be provided per stream/session, including:
- Desired target language (or pass-through)
- Voice selection parameters (at a business level: “voice profile”)
- Stage enable/disable flags
- Concurrency/backpressure limits

Language/voice configuration is **fixed for the lifetime of a created worker** and does not change mid-stream. It is provided at worker creation time via runtime configuration (e.g., environment/config file).

### 7.2 Error Handling & Fallbacks

The pipeline MUST define behavior per stage failure:
- If ASR fails: mark fragment `failed` and allow downstream to skip; optionally emit empty text.
- If Translate fails: fall back to source transcript (pass-through) if configured.
- If TTS fails: mark fragment `partial` and emit no synth audio.

The pipeline MUST expose enough information for the caller (stream worker) to apply the higher-level audio fallbacks defined in `specs/001-spec.md` (e.g., pass-through original audio).

### 7.3 Idempotency and Retries

- A stage retry MUST NOT create a new logical asset for the same `(stream_id, sequence_number, stage)` unless explicitly configured.
- The orchestrator MUST be able to resume a fragment from stored intermediate assets (skip completed stages).

## 8. Testing Strategy (Composable, Stub-Friendly)

### 8.1 What “Functional Test” Means Here

A functional test composes a pipeline from components and verifies:
- The pipeline returns the expected **STS Result** object shape and statuses
- Intermediate assets are produced with correct lineage (`parent_asset_ids`)
- Ordering guarantees hold under concurrent execution
- Failures and fallbacks produce expected `partial/failed` results

### 8.2 Recommended Test Fixtures

- Small deterministic audio fragments (e.g., “hello world” samples)
- Pre-generated transcripts/translations for stub components
- Golden expected result metadata (IDs may be normalized for assertions)

### 8.3 Stub/Mock Components (Examples)

These stubs should be provided for tests and local validation:
- **MockASRStaticText**: ignores audio content and returns a configured transcript string.
- **MockTranslateIdentity**: returns input text unchanged (optionally changes language metadata).
- **MockTranslateDictionary**: maps known phrases to target phrases deterministically.
- **MockTTSFixedTone**: returns a deterministic synthetic audio placeholder of requested duration.
- **MockTTSFromFixture**: returns a preloaded audio fixture by `sequence_number`.

### 8.4 Composition Examples (Test Cases)

```
Case A: ASR(mock static) → Translate(identity) → TTS(fixture)
Expected: success, all intermediate assets present, final_text matches expected

Case B: ASR(mock static) → Translate(fail) → TTS(fixture), with translate fallback enabled
Expected: partial/success (per policy), translated_text references source transcript, errors include translate failure

Case C: 10 fragments, concurrency=4, inject slow TTS on fragment #3
Expected: outputs emitted in sequence_number order, no missing fragments, timing metrics recorded
```

## 9. Integration with Stream Worker (Boundary)

The stream worker (see `specs/003-gstreamer-stream-worker.md`) calls the STS pipeline per audio fragment and receives:
- A synthesized audio asset reference (if available)
- A complete STS Result with traceable intermediate assets and errors

The worker remains responsible for:
- Chunking strategy and timestamps
- Audio separation/mixing and A/V sync
- Applying higher-level fallbacks when STS output is partial/failed

## 10. Success Criteria

- The STS pipeline can be assembled from interchangeable ASR/Translate/TTS components without changing orchestration behavior.
- For a live stream, the system emits one STS Result per fragment with stable IDs and retrievable intermediate assets.
- A functional test suite can validate pipeline behavior using only deterministic stubs (no network, no external services).
- Under concurrent execution, outputs are emitted in correct fragment order for each stream.
