# Clarification Questions - Fragment Length Increase (6s → 30s)

**Feature ID**: 021-fragment-length-30s
**Clarification Session**: 2026-01-11
**Agent**: Clarify Agent
**Status**: Complete (5/5 questions resolved)

## Overview

This document records the clarification questions and user decisions made during the specification phase. These decisions resolved ambiguities in the original spec and are now encoded in the main specification document.

## Questions and Answers

### Q1: STS Processing Timeout

**Category**: Non-Functional Requirements - Timeout Configuration
**Priority**: Critical (P1)

**Question**: Which timeout value should be used given 30s fragments may take 25-35s to process?

**Context**: The spec contained conflicting timeout values:
- FR-008: `StreamSession.timeout_ms MUST default to 60000 (60 seconds)`
- Current codebase: `StreamInitPayload.timeout_ms le=30000` (max 30 seconds)
- Processing time table: "Total: ~25-35s (Within 60s timeout)"
- Current validation constraint would reject a 60-second timeout

**Options Presented**:
| Option | Description | Tradeoffs |
|--------|-------------|-----------|
| A | 60000ms (60s) timeout, update validation to le=120000 | Safer margin for 30s fragments (~25-35s processing), allows slow models |
| B | 45000ms (45s) timeout, update validation to le=60000 | Tighter timeout, faster failure detection, may cause timeouts under load |
| C | Keep 30000ms (30s) timeout unchanged | Risky - processing time (25-35s) is at or exceeds timeout limit |

**User Answer**: Option A - 60s timeout (60000ms) with le=120000 validation max

**Impact**:
- FR-008: Updated to 60000ms default
- FR-009: Confirmed FRAGMENT_TIMEOUT = 60 seconds
- FR-013: Updated validation constraint to le=120000

---

### Q2: Validation Constraint Upper Bounds

**Category**: Validation - Configuration Constraints
**Priority**: High (P2)

**Question**: Should chunk_duration_ms validation allow values above 30 seconds?

**Context**: The spec updated `StreamConfigPayload.chunk_duration_ms` to `le=30000`, but uncertainty remained about whether higher values should be permitted for future flexibility.

Current codebase:
```python
chunk_duration_ms: int = Field(
    default=6000,
    ge=100,
    le=10000,  # Current maximum is 10 seconds
    description="Expected fragment duration in milliseconds",
)
```

**Options Presented**:
| Option | Description | Tradeoffs |
|--------|-------------|-----------|
| A | le=30000 (exactly 30s max) | Strict enforcement, prevents accidental misconfiguration |
| B | le=60000 (60s max) | Allows future flexibility for even longer fragments |
| C | le=120000 (120s max) | Maximum flexibility, matches timeout_ms upper bound |

**User Answer**: Option A - le=30000 (exactly 30s max)

**Impact**:
- FR-012: Confirmed le=30000 constraint
- Prevents configuration errors
- Future fragment duration increases require new specification

---

### Q3: Memory Constraint Handling

**Category**: Edge Cases - Resource Management
**Priority**: Medium (P2)

**Question**: What should happen when memory usage is high with 30s buffers (9MB→45MB increase)?

**Context**: The spec mentioned in Edge Cases: "What happens when memory is constrained with 30s buffers? System monitors memory usage and may need to adjust max_inflight"

Memory impact:
- In-flight Fragments (max 3): ~9MB total → ~45MB total (5x increase)

However, there was **no specification for actual system behavior** when memory is constrained.

**Options Presented**:
| Option | Description | Tradeoffs |
|--------|-------------|-----------|
| A | No automatic handling - let system fail if OOM occurs | Simple, relies on container memory limits, provides clear failure signal |
| B | Reduce max_inflight dynamically (3→2→1) based on memory pressure | Self-healing but adds complexity, may not be needed if memory limits are adequate |
| C | Log warning when memory high, but take no action | Observability without behavior change, allows manual intervention |

**User Answer**: Option A - No automatic handling - rely on container limits

**Impact**:
- Edge Cases section updated to reflect no automatic handling
- Deployment strategy relies on container memory limits
- Simplified implementation (no dynamic max_inflight adjustment)
- Clear OOM signals for capacity planning

---

### Q4: A/V Offset Calculation

**Category**: A/V Synchronization - Offset Configuration
**Priority**: Critical (P1)

**Question**: Should av_offset_ns be exactly 30s (fragment duration) or higher to account for processing time (25-35s)?

**Context**: The spec showed an ambiguity in the A/V offset value:
- User Story 3 title: "updated from 6 seconds to **30+ seconds**"
- FR-010: "av_offset_ns MUST default to 30_000_000_000 (**30 seconds**)"
- Processing time: 25-35 seconds

If av_offset is exactly 30s but processing takes 35s, the video pipeline might not wait long enough.

**Options Presented**:
| Option | Description | Tradeoffs |
|--------|-------------|-----------|
| A | 30_000_000_000 (exactly 30s) | Matches fragment duration, simpler mental model, may cause sync issues if processing >30s |
| B | 35_000_000_000 (35s) | Covers worst-case processing time (35s), adds 5s safety margin |
| C | 60_000_000_000 (60s) | Matches timeout value, maximum safety, but adds unnecessary latency |

**User Answer**: Option B - 35_000_000_000 (35s)

**Impact**:
- FR-010: Updated to 35_000_000_000ns (35 seconds)
- FR-011: Updated to apply 35-second offset
- User Story 3: Updated test names and acceptance criteria to reflect 35s
- Files Requiring Updates: Updated av_sync.py and state.py to use 35s

**Rationale**: Separates fragment duration (data size: 30s) from processing latency (time offset: 35s). Ensures dubbed audio arrives before video needs it.

---

### Q5: Partial Segment Handling

**Category**: Edge Cases - Fragment Processing
**Priority**: Medium (P2)

**Question**: Should partial segments (duration <30s) be sent to STS for processing?

**Context**:
- Edge Cases (line 152): "What happens when stream duration is less than 30 seconds? Partial segment emitted with actual duration (minimum 1 second)"
- User Story 1 Acceptance Scenario 4: "stream ends at 45 seconds → one 30s segment and one 15s partial segment are produced"

Unclear whether partial segments should be:
1. Sent to STS for dubbing
2. Discarded and original audio used
3. Handled differently based on duration threshold

**Options Presented**:
| Option | Description | Tradeoffs |
|--------|-------------|-----------|
| A | Yes - send all partial segments ≥1s to STS | Complete dubbing coverage, but short segments may have poor translation quality |
| B | Yes - send partial segments ≥5s to STS, discard <5s | Balance coverage and quality, 5s is reasonable for sentence fragments |
| C | No - discard partial segments, use original audio | Simpler, avoids poor quality translations, but creates inconsistent user experience at stream end |

**User Answer**: Option A - Send all partial segments ≥1s to STS

**Impact**:
- FR-005: Confirmed MIN_SEGMENT_DURATION_NS = 1_000_000_000 (1 second) applies to partial segments
- Edge Cases: Updated to clarify partial segments are sent to STS
- Consistent user experience (all content dubbed, no gap at stream end)

---

## Design Decisions Summary

All clarification answers have been encoded into the spec as **Design Decisions** with full rationale:

1. **Timeout Configuration**: 60s timeout with le=120000 validation max
2. **Chunk Duration Validation**: Strict le=30000 (exactly 30s max)
3. **Memory Constraint Handling**: No automatic handling - rely on container limits
4. **A/V Offset Value**: 35s offset (35_000_000_000ns), not 30s
5. **Partial Segment Processing**: Send all partial segments ≥1s to STS

## Specification Updates

The following sections were updated in `spec.md`:

- **User Story 3**: Updated to reflect 35s offset
- **Edge Cases**: Clarified partial segment and memory handling
- **FR-010, FR-011**: Updated to 35_000_000_000ns for A/V offset
- **FR-012**: Confirmed le=30000 for chunk_duration_ms
- **FR-013**: Updated to le=120000 for timeout_ms
- **Files Requiring Updates**: Updated av_sync file changes to use 35s
- **Design Decisions**: New section added with full rationale for each decision
- **Clarifications**: Session 2026-01-11 Q&A recorded

## Next Steps

The specification is now ready for the **plan** phase. All critical ambiguities have been resolved and decisions are documented.
