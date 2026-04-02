# Research: VAD Audio Segmentation

**Feature**: 023-vad-audio-segmentation
**Date**: 2026-01-09
**Status**: Complete

## Research Summary

All technical unknowns have been resolved through research documented in `research-cache.md`. This document summarizes the key decisions and rationale.

## Decision Log

### Decision 1: VAD Implementation Method

**Decision**: Use GStreamer `level` element from gst-plugins-good

**Rationale**:
- Native integration with existing GStreamer pipeline (no additional process/binding required)
- Real-time RMS measurement every 100ms with minimal CPU overhead
- Well-tested in production environments
- No additional Python dependencies needed (already have PyGObject)

**Alternatives Rejected**:
- WebRTC VAD library: Requires separate process or Python binding, adds complexity
- librosa: Designed for offline analysis, not real-time streaming
- Custom FFT-based implementation: Reinventing the wheel, maintenance burden

### Decision 2: RMS Measurement Interval

**Decision**: 100ms (100,000,000 nanoseconds)

**Rationale**:
- Provides ~10 updates per second for responsive silence detection
- Balances CPU efficiency with detection granularity
- Sufficient for 1-second silence detection threshold (10 samples)

**Alternatives Rejected**:
- 50ms: Higher CPU overhead with minimal VAD improvement
- 200ms: May miss short pauses between words

### Decision 3: Message Handling Pattern

**Decision**: Signal-based with `bus.connect("message::element", handler)`

**Rationale**:
- Pythonic and type-specific filtering reduces parsing overhead
- Thread-safe via GLib (messages marshalled to main thread)
- Integrates with existing WorkerRunner pattern
- Cleaner code than manual polling

**Alternatives Rejected**:
- Manual polling with `timed_pop_filtered()`: More code, explicit control not needed
- Watch function: Less Pythonic, older pattern

### Decision 4: Multi-Channel RMS Strategy

**Decision**: Peak (maximum) RMS across all channels

**Rationale**:
- Speech in ANY channel should prevent segment boundary
- Fail-safe approach for stereo/multi-track content
- Simple implementation: `max(channel_rms_values)`

**Alternatives Rejected**:
- Average RMS: May miss single-channel speech in mixed content
- Left channel only: Ignores right channel entirely

### Decision 5: Element Availability Check

**Decision**: Fail-fast at startup with RuntimeError

**Rationale**:
- Prevents silent degradation to non-functional state
- Forces deployment verification
- Clear error message guides operators to install gst-plugins-good

**Alternatives Rejected**:
- Fallback to fixed 6s segments: Silent failure defeats the purpose of VAD
- Log warning only: Allows broken state to persist

### Decision 6: dB Threshold Default

**Decision**: -50 dB RMS

**Rationale**:
- Appropriate for broadcast content (distinguishes speech from ambient noise)
- Tunable via environment variable for different content types
- Conservative default (may need adjustment for specific use cases)

**Alternatives Rejected**:
- -40 dB: Too sensitive, ambient noise may trigger false speech detection
- -60 dB: May miss quiet speech

### Decision 7: Structure Field Access Method

**Decision**: `structure.get_array("rms")` with success check

**Rationale**:
- Pythonic approach with explicit success/failure handling
- Type-safe with (success, value) tuple return
- Handles missing fields gracefully

**Alternatives Rejected**:
- `structure.get_value("rms")` with manual GValueArray iteration: More verbose
- Direct field access: Unsafe, may raise exceptions

## Technical Validation

All research has been validated against:
- Official GStreamer documentation (level element, bus messaging)
- PyGObject API documentation (Gst.Structure, Gst.Message)
- Working C examples from gst-plugins-good repository
- Existing codebase patterns (InputPipeline, bus message handling)

## Confidence Level

**HIGH**

- Complete API documentation available
- Working examples exist for all required patterns
- No gaps in implementation path identified
- All dependencies already present in the project

## Sources

See `research-cache.md` for detailed documentation and code examples.
