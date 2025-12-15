# Audio Transcription Module (ASR Component)

This spec defines the **audio transcription module** as the **ASR component** in the STS pipeline described in `specs/004-sts-pipeline-design.md`, and referenced by the end-to-end system in `specs/001-spec.md`.

It is based on the approach and logic described in `specs/sources/ASR.md` (batch transcription + streaming wrapper, audio quality preprocessing, domain priming, confidence scoring, and utterance shaping), while aligning to the replaceable component contract in `specs/004-sts-pipeline-design.md`.

---

## 1. Goal

Provide a reusable ASR component that can transcribe short **audio fragments** from a live stream into a **timestamped transcript**, suitable for downstream translation and TTS in an STS pipeline.

The component must support:
- **Fragment-level transcription** (process one audio fragment at a time)
- **Streaming-friendly operation** (continuous input, consistent output timestamps)
- **Optional word-level timestamps** and **confidence metadata**
- **Text cleanup** for readability (light, deterministic postprocessing)

---

## 2. Non-Goals

- Defining the stream worker chunking, separation/mixing, or A/V sync logic (see `specs/003-gstreamer-stream-worker.md`).
- Selecting a specific vendor/model/provider for ASR (the component must be replaceable per `specs/004-sts-pipeline-design.md`).
- Guaranteeing perfect punctuation/casing or true named-entity recognition (only lightweight readability improvements are in scope).

---

## 3. Position in the STS Pipeline

Per `specs/004-sts-pipeline-design.md`, the default STS stages are:
1. ASR: audio → transcript
2. Translate (optional): transcript → translated transcript
3. TTS: text → synthesized audio

This spec covers only **Stage 1 (ASR)** and its inputs/outputs.

---

## 4. Component Contract (STS-Aligned)

This section mirrors the intent of `specs/004-sts-pipeline-design.md` while focusing on the ASR-specific payload.

### 4.1 Input: Audio Fragment

Minimum inputs expected by the ASR component:
- `stream_id`
- `sequence_number`
- `start_time_ms`, `end_time_ms` (fragment boundaries in the stream timeline)
- `sample_rate_hz`, `channels`
- `payload_ref` (reference to PCM bytes in-memory or a stored asset)

Operational expectations:
- The fragment audio represents a short window (typically ~1–2 seconds) suitable for low-latency transcription.
- The component must treat the fragment boundaries as the time reference for output timestamps (see §4.3).

### 4.2 Output: Transcript Asset

The ASR component produces a transcript asset that includes:
- `stream_id`, `sequence_number`
- `asset_id`, `parent_asset_ids`, `created_at`
- `component` (must be `asr`), `component_instance` (provider identifier)
- `language` (specified or detected)
- `segments`: ordered list of transcript segments
- `status`: `success | partial | failed`
- `errors` (if any) with `retryable` classification

### 4.3 Segment Format

Each transcript segment must contain:
- `start_time_ms`, `end_time_ms` (absolute in stream timeline)
- `text` (human-readable)
- `confidence` (0.0–1.0 relative score)

Optional fields (recommended when available):
- `words`: list of `{ start_time_ms, end_time_ms, word, confidence? }`
- `no_speech_probability` or similar model signal (for debugging)

Timestamp rule:
- Segment times must be **absolute**: `segment_abs_time = fragment_start_time + segment_rel_time`.

---

## 5. End-to-End ASR Flow (Per Fragment)

This flow follows the same approach and quality intent as `specs/sources/ASR.md`, but is stated as component behavior (not implementation).

### 5.1 Model lifecycle and caching

Requirements:
- The component should avoid re-loading the recognition model for every fragment.
- Model instances should be reused across fragments within a worker lifecycle, keyed by relevant runtime configuration (e.g., model size/quality tier, compute device).

Expected outcome:
- Stable performance across long-running sessions.

### 5.2 Audio preprocessing (quality-oriented)

Before transcription, the component should apply lightweight preprocessing designed for speech clarity and model compatibility:
- Convert audio to the model’s expected numeric representation.
- Normalize amplitude to reduce volume variance across fragments.
- Reduce low-frequency rumble (e.g., high-pass behavior) when it improves recognition.
- Optionally apply mild pre-emphasis / clarity filtering.

Constraints:
- Preprocessing must be deterministic and safe for streaming (no long lookahead requirements).

### 5.3 Domain priming (optional)

The component should support a `domain` input (or per-stream configuration) that biases recognition toward expected vocabulary (e.g., sports, news, interview, general).

Behavior:
- When `domain` is provided, the ASR component should apply a domain-appropriate “context hint” so proper nouns and domain terms are more likely to be recognized.
- When absent, default to a general domain.

### 5.4 Transcription and segmentation

Behavioral requirements:
- The component must produce a set of **time-bounded segments** for the fragment.
- The component should support speech activity filtering to reduce hallucinations during silence.
- When enabled, the component should produce word-level timestamps.

### 5.5 Per-segment postprocessing

For each segment:
- Remove empty/whitespace-only outputs.
- Produce a `confidence` score in `[0, 1]` derived from the recognizer’s internal confidence signals, suitable for relative ranking/guarding (not a calibrated probability).
- Apply light text cleanup to improve readability (e.g., basic capitalization and punctuation normalization).

Optional domain heuristics:
- Allow deterministic, domain-specific text enhancements (e.g., formatting of common sports terms) without requiring external services.

### 5.6 Utterance shaping (boundary improvements)

To improve downstream latency and naturalness:
- Merge ultra-short segments into the previous segment when the previous segment does not appear “complete” (e.g., lacks terminal punctuation).
- Split overly long segments to a target maximum duration, preferring sentence/punctuation boundaries.

Outcome:
- The segment list is better suited for streaming translation/TTS without waiting too long for a single “giant” utterance.

---

## 6. Streaming Mode (Continuous Operation)

In addition to per-fragment transcription, the module should support a streaming wrapper that:
- Accepts a continuous sequence of audio fragments (or chunked audio blocks) with timestamps.
- Processes fragments asynchronously.
- Emits transcript segments with **absolute stream timestamps** (see §4.3).

Ordering expectations:
- The ASR component should preserve segment order within a fragment.
- Cross-fragment ordering is enforced by the STS orchestrator (see ordering guarantees in `specs/004-sts-pipeline-design.md`), but the ASR module must not emit timestamps that violate the fragment’s time bounds.

Backpressure expectations:
- When overloaded, the streaming wrapper must provide a bounded queue strategy (drop, block, or degrade quality) that is explicit and observable (see §8).

---

## 7. Error Handling and Fallbacks

The component must classify failures to support orchestration policies in `specs/004-sts-pipeline-design.md`:

- **No speech / silence**:
  - Return `success` with `segments=[]` (preferred) or `partial` with a structured warning.
- **Transient failure** (retryable):
  - Return `failed` with `retryable=true` and an error message safe for logs.
- **Non-retryable failure**:
  - Return `failed` with `retryable=false`.

Partial results:
- If some segments are produced but later processing fails, the component may return `partial` with produced segments and an error list.

---

## 8. Observability (Must-Have)

The ASR component should emit structured metrics/log fields usable by the stream worker and pipeline orchestrator:
- `stream_id`, `sequence_number`
- Processing durations: preprocess time, recognition time, postprocess time, total time
- Output summary: segment count, total text length, average confidence
- Error counts by type and retryable flag

Optional (debug-only) artifacts:
- Ability to persist the input audio fragment and/or transcript output as a local debug artifact behind an explicit flag (not default).

---

## 9. Testing Strategy (Deterministic, Stub-Friendly)

This module must be testable without live RTMP endpoints, aligning with `specs/004-sts-pipeline-design.md`.

### 9.1 Functional tests (recommended)

Minimum functional coverage:
- Produces a valid transcript asset for a deterministic speech fragment.
- Produces empty output for silence.
- Produces stable absolute timestamps (segment times fall within `start_time_ms..end_time_ms` with expected offsets).
- Applies utterance shaping rules deterministically (merge/split behavior).

### 9.2 Stub component

Provide a mock ASR implementation that:
- Ignores audio content and returns configured text segments deterministically.
- Supports predictable confidence values and timestamps.

### 9.3 Test fixtures

Recommended fixtures:
- Short, non-secret WAV samples (speech and silence) suitable for deterministic test runs.
- If fixtures cannot be committed, document a local path-based mechanism to supply them (future work; do not require network access by default).

---

## 10. Assumptions and Limitations

- Language handling defaults to a single configured language unless explicitly configured for detection.
- Confidence is a relative indicator derived from recognizer signals; it should not be treated as a calibrated probability.
- “Entity enhancement” is heuristic-only unless a richer NLP component is introduced as a separate, replaceable stage.
- Extremely short fragments can reduce recognition quality; chunking strategy belongs to the stream worker (see `specs/003-gstreamer-stream-worker.md`).

---

## 11. Success Criteria

- The ASR component can transcribe live fragments and produce segment timestamps aligned to the stream timeline for at least 99% of fragments in a stable local test run.
- When given silent/no-speech fragments, the component emits no hallucinated text in at least 99% of cases across the provided test fixtures.
- The module can be replaced by a deterministic stub without changing the STS orchestrator behavior described in `specs/004-sts-pipeline-design.md`.

---

## 12. Reference (Source Design)

The detailed source rationale and reference logic (preprocessing, domain priming, confidence shaping, and streaming wrapper behavior) is captured in:
- `specs/sources/ASR.md`
