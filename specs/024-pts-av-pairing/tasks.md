# Task List: PTS-Based A/V Pairing Implementation

**Feature**: `024-pts-av-pairing`
**Branch**: `024-pts-av-pairing`
**Created**: 2026-01-10
**Status**: Ready for Implementation

---

## Phase 1: Setup & Design Review

- [x] T001 Review feature specification and accept requirements
- [x] T002 Review implementation plan and architecture decisions
- [x] T003 Constitution check passed (Principle VIII - TDD, Principle VI - A/V Sync, Principle I - Real-Time First, Principle II - Testability)

---

## Phase 2: Foundational Data Structures (TDD)

### AudioBufferEntry Tests
- [ ] T004 [P] **[US3]** Write unit tests for AudioBufferEntry.t0_ns property at `/Users/leonardofu/dev/back-end/live-broadcast-dubbing-cloud/apps/media-service/tests/unit/test_av_sync_pts_matching.py` [S]
- [ ] T005 [P] **[US3]** Write unit tests for AudioBufferEntry.end_ns property at `/Users/leonardofu/dev/back-end/live-broadcast-dubbing-cloud/apps/media-service/tests/unit/test_av_sync_pts_matching.py` [S]
- [ ] T006 [P] **[US3]** Write unit tests for AudioBufferEntry.should_evict() method at `/Users/leonardofu/dev/back-end/live-broadcast-dubbing-cloud/apps/media-service/tests/unit/test_av_sync_pts_matching.py` [S]
- [ ] T007 **[US3]** Implement AudioBufferEntry dataclass in `/Users/leonardofu/dev/back-end/live-broadcast-dubbing-cloud/apps/media-service/src/media_service/sync/av_sync.py` with fields: audio_segment, audio_data, paired_video_pts, insertion_time_ns [S]
- [ ] T008 **[US3]** Implement AudioBufferEntry.t0_ns property in `/Users/leonardofu/dev/back-end/live-broadcast-dubbing-cloud/apps/media-service/src/media_service/sync/av_sync.py` [S]
- [ ] T009 **[US3]** Implement AudioBufferEntry.end_ns property in `/Users/leonardofu/dev/back-end/live-broadcast-dubbing-cloud/apps/media-service/src/media_service/sync/av_sync.py` [S]
- [ ] T010 **[US3]** Implement AudioBufferEntry.should_evict() method in `/Users/leonardofu/dev/back-end/live-broadcast-dubbing-cloud/apps/media-service/src/media_service/sync/av_sync.py` [S]
- [ ] T011 **[US3]** Verify all AudioBufferEntry tests pass at `/Users/leonardofu/dev/back-end/live-broadcast-dubbing-cloud/apps/media-service/tests/unit/test_av_sync_pts_matching.py` [S]

### VideoBufferEntry Tests
- [ ] T012 [P] **[US6]** Write unit tests for VideoBufferEntry.t0_ns property at `/Users/leonardofu/dev/back-end/live-broadcast-dubbing-cloud/apps/media-service/tests/unit/test_av_sync_pts_matching.py` [S]
- [ ] T013 [P] **[US6]** Write unit tests for VideoBufferEntry.end_ns property at `/Users/leonardofu/dev/back-end/live-broadcast-dubbing-cloud/apps/media-service/tests/unit/test_av_sync_pts_matching.py` [S]
- [ ] T014 [P] **[US6]** Write unit tests for VideoBufferEntry.should_fallback() method at `/Users/leonardofu/dev/back-end/live-broadcast-dubbing-cloud/apps/media-service/tests/unit/test_av_sync_pts_matching.py` [S]
- [ ] T015 **[US6]** Implement VideoBufferEntry dataclass in `/Users/leonardofu/dev/back-end/live-broadcast-dubbing-cloud/apps/media-service/src/media_service/sync/av_sync.py` with fields: video_segment, video_data, insertion_time_ns [S]
- [ ] T016 **[US6]** Implement VideoBufferEntry.t0_ns property in `/Users/leonardofu/dev/back-end/live-broadcast-dubbing-cloud/apps/media-service/src/media_service/sync/av_sync.py` [S]
- [ ] T017 **[US6]** Implement VideoBufferEntry.end_ns property in `/Users/leonardofu/dev/back-end/live-broadcast-dubbing-cloud/apps/media-service/src/media_service/sync/av_sync.py` [S]
- [ ] T018 **[US6]** Implement VideoBufferEntry.should_fallback() method in `/Users/leonardofu/dev/back-end/live-broadcast-dubbing-cloud/apps/media-service/src/media_service/sync/av_sync.py` with 10-second default timeout [S]
- [ ] T019 **[US6]** Verify all VideoBufferEntry tests pass at `/Users/leonardofu/dev/back-end/live-broadcast-dubbing-cloud/apps/media-service/tests/unit/test_av_sync_pts_matching.py` [S]

### Constants & Buffer Type Changes
- [ ] T020 **[US3]** Add constants to AvSyncManager in `/Users/leonardofu/dev/back-end/live-broadcast-dubbing-cloud/apps/media-service/src/media_service/sync/av_sync.py`: VIDEO_SEGMENT_DURATION_NS=6_000_000_000, FALLBACK_TIMEOUT_NS=10_000_000_000 [S]
- [ ] T021 **[US3]** Change _audio_buffer from dict to list[AudioBufferEntry] in AvSyncManager at `/Users/leonardofu/dev/back-end/live-broadcast-dubbing-cloud/apps/media-service/src/media_service/sync/av_sync.py` [S]
- [ ] T022 **[US3]** Change _video_buffer to list[VideoBufferEntry] in AvSyncManager at `/Users/leonardofu/dev/back-end/live-broadcast-dubbing-cloud/apps/media-service/src/media_service/sync/av_sync.py` [S]
- [ ] T023 **[US3]** Add _max_video_pts_seen field to AvSyncManager in `/Users/leonardofu/dev/back-end/live-broadcast-dubbing-cloud/apps/media-service/src/media_service/sync/av_sync.py` initialized to 0 [S]

---

## Phase 3: PTS Overlap Algorithm (TDD)

- [ ] T024 [P] **[US1]** Write unit test test_overlaps_full_containment() at `/Users/leonardofu/dev/back-end/live-broadcast-dubbing-cloud/apps/media-service/tests/unit/test_av_sync_pts_matching.py`: video fully contained in audio [S]
- [ ] T025 [P] **[US1]** Write unit test test_overlaps_partial_start() at `/Users/leonardofu/dev/back-end/live-broadcast-dubbing-cloud/apps/media-service/tests/unit/test_av_sync_pts_matching.py`: video starts before audio, ends inside [S]
- [ ] T026 [P] **[US1]** Write unit test test_overlaps_partial_end() at `/Users/leonardofu/dev/back-end/live-broadcast-dubbing-cloud/apps/media-service/tests/unit/test_av_sync_pts_matching.py`: video starts inside audio, ends after [S]
- [ ] T027 [P] **[US1]** Write unit test test_no_overlap_before() at `/Users/leonardofu/dev/back-end/live-broadcast-dubbing-cloud/apps/media-service/tests/unit/test_av_sync_pts_matching.py`: video completely before audio [S]
- [ ] T028 [P] **[US1]** Write unit test test_no_overlap_after() at `/Users/leonardofu/dev/back-end/live-broadcast-dubbing-cloud/apps/media-service/tests/unit/test_av_sync_pts_matching.py`: video completely after audio [S]
- [ ] T029 [P] **[US1]** Write unit test test_no_overlap_exact_boundary() at `/Users/leonardofu/dev/back-end/live-broadcast-dubbing-cloud/apps/media-service/tests/unit/test_av_sync_pts_matching.py`: strict inequality - exact boundaries do NOT overlap [S]
- [ ] T030 **[US1]** Implement _overlaps() method in AvSyncManager at `/Users/leonardofu/dev/back-end/live-broadcast-dubbing-cloud/apps/media-service/src/media_service/sync/av_sync.py` using formula: video.t0_ns < audio.end_ns and audio.t0_ns < video.end_ns [M]
- [ ] T031 **[US1]** Verify all PTS overlap tests pass at `/Users/leonardofu/dev/back-end/live-broadcast-dubbing-cloud/apps/media-service/tests/unit/test_av_sync_pts_matching.py` [S]

---

## Phase 4: Sorted Audio Buffer with Bisect (TDD)

- [ ] T032 [P] **[US3]** Write unit test test_insert_maintains_sorted_order() at `/Users/leonardofu/dev/back-end/live-broadcast-dubbing-cloud/apps/media-service/tests/unit/test_av_sync_pts_matching.py`: insertions maintain PTS order [M]
- [ ] T033 [P] **[US3]** Write unit test test_insert_out_of_order_arrivals() at `/Users/leonardofu/dev/back-end/live-broadcast-dubbing-cloud/apps/media-service/tests/unit/test_av_sync_pts_matching.py`: out-of-order audio correctly sorted [M]
- [ ] T034 [P] **[US3]** Write unit test test_find_overlapping_audio() at `/Users/leonardofu/dev/back-end/live-broadcast-dubbing-cloud/apps/media-service/tests/unit/test_av_sync_pts_matching.py`: query returns all overlapping audio entries [M]
- [ ] T035 [P] **[US3]** Write unit test test_find_best_overlap_when_multiple() at `/Users/leonardofu/dev/back-end/live-broadcast-dubbing-cloud/apps/media-service/tests/unit/test_av_sync_pts_matching.py`: selects audio with maximum overlap amount [M]
- [ ] T036 [P] **[US3]** Write unit test test_buffer_eviction_with_watermark() at `/Users/leonardofu/dev/back-end/live-broadcast-dubbing-cloud/apps/media-service/tests/unit/test_av_sync_pts_matching.py`: audio evicted below safe watermark [M]
- [ ] T037 **[US3]** Implement _insert_audio() method in AvSyncManager at `/Users/leonardofu/dev/back-end/live-broadcast-dubbing-cloud/apps/media-service/src/media_service/sync/av_sync.py` using bisect.bisect_left() for O(n) insertion [M]
- [ ] T038 **[US3]** Implement _find_overlapping_audio() method in AvSyncManager at `/Users/leonardofu/dev/back-end/live-broadcast-dubbing-cloud/apps/media-service/src/media_service/sync/av_sync.py` returning list[AudioBufferEntry] [M]
- [ ] T039 **[US3]** Implement _select_best_overlap() method in AvSyncManager at `/Users/leonardofu/dev/back-end/live-broadcast-dubbing-cloud/apps/media-service/src/media_service/sync/av_sync.py` using overlap_amount() calculation [M]
- [ ] T040 **[US3]** Verify all sorted buffer tests pass at `/Users/leonardofu/dev/back-end/live-broadcast-dubbing-cloud/apps/media-service/tests/unit/test_av_sync_pts_matching.py` [M]

---

## Phase 5: Safe Eviction Watermark (TDD)

- [ ] T041 [P] **[US4]** Write unit test test_eviction_watermark_calculation() at `/Users/leonardofu/dev/back-end/live-broadcast-dubbing-cloud/apps/media-service/tests/unit/test_av_sync_pts_matching.py`: safe_eviction_pts = max_video_pts_seen - (3 * VIDEO_SEGMENT_DURATION_NS) [M]
- [ ] T042 [P] **[US4]** Write unit test test_audio_evicted_when_end_below_watermark() at `/Users/leonardofu/dev/back-end/live-broadcast-dubbing-cloud/apps/media-service/tests/unit/test_av_sync_pts_matching.py`: audio.end_ns <= safe_eviction_pts triggers removal [M]
- [ ] T043 [P] **[US4]** Write unit test test_audio_retained_when_end_above_watermark() at `/Users/leonardofu/dev/back-end/live-broadcast-dubbing-cloud/apps/media-service/tests/unit/test_av_sync_pts_matching.py`: audio retained above watermark [M]
- [ ] T044 [P] **[US4]** Write unit test test_eviction_with_out_of_order_video() at `/Users/leonardofu/dev/back-end/live-broadcast-dubbing-cloud/apps/media-service/tests/unit/test_av_sync_pts_matching.py`: handles 18-second out-of-order tolerance [M]
- [ ] T045 **[US4]** Implement _evict_stale_audio() method in AvSyncManager at `/Users/leonardofu/dev/back-end/live-broadcast-dubbing-cloud/apps/media-service/src/media_service/sync/av_sync.py` using safe watermark formula [M]
- [ ] T046 **[US4]** Verify all eviction tests pass at `/Users/leonardofu/dev/back-end/live-broadcast-dubbing-cloud/apps/media-service/tests/unit/test_av_sync_pts_matching.py` [M]

---

## Phase 6: Push Video with PTS Matching (TDD)

- [ ] T047 [P] **[US1]** Write unit test test_push_video_pairs_with_overlapping_audio() at `/Users/leonardofu/dev/back-end/live-broadcast-dubbing-cloud/apps/media-service/tests/unit/test_av_sync_pts_matching.py`: video pairs immediately with buffered audio [M]
- [ ] T048 [P] **[US1]** Write unit test test_push_video_buffers_when_no_overlap() at `/Users/leonardofu/dev/back-end/live-broadcast-dubbing-cloud/apps/media-service/tests/unit/test_av_sync_pts_matching.py`: video buffered when no matching audio [M]
- [ ] T049 [P] **[US1]** Write unit test test_push_video_updates_max_pts_seen() at `/Users/leonardofu/dev/back-end/live-broadcast-dubbing-cloud/apps/media-service/tests/unit/test_av_sync_pts_matching.py`: _max_video_pts_seen updated to max(current, video.end_ns) [M]
- [ ] T050 [P] **[US1]** Write unit test test_push_video_triggers_eviction() at `/Users/leonardofu/dev/back-end/live-broadcast-dubbing-cloud/apps/media-service/tests/unit/test_av_sync_pts_matching.py`: eviction runs after pairing [M]
- [ ] T051 **[US1]** Refactor push_video() method in AvSyncManager at `/Users/leonardofu/dev/back-end/live-broadcast-dubbing-cloud/apps/media-service/src/media_service/sync/av_sync.py` to use PTS matching instead of batch_number [L]
  - Create VideoBufferEntry from segment
  - Update _max_video_pts_seen to video.end_ns
  - Call _find_overlapping_audio()
  - Call _select_best_overlap() if candidates exist
  - Add video.t0_ns to paired_video_pts if audio found
  - Call _evict_stale_audio()
  - Return SyncPair if matched, else buffer video
- [ ] T052 **[US1]** Verify all push_video tests pass at `/Users/leonardofu/dev/back-end/live-broadcast-dubbing-cloud/apps/media-service/tests/unit/test_av_sync_pts_matching.py` [L]

---

## Phase 7: Push Audio with PTS Matching & One-to-Many (TDD)

- [ ] T053 [P] **[US2]** Write unit test test_push_audio_pairs_with_overlapping_video() at `/Users/leonardofu/dev/back-end/live-broadcast-dubbing-cloud/apps/media-service/tests/unit/test_av_sync_pts_matching.py`: audio finds all overlapping buffered videos [M]
- [ ] T054 [P] **[US2]** Write unit test test_push_audio_buffers_when_no_overlap() at `/Users/leonardofu/dev/back-end/live-broadcast-dubbing-cloud/apps/media-service/tests/unit/test_av_sync_pts_matching.py`: audio buffered when no matching videos [M]
- [ ] T055 [P] **[US2]** Write unit test test_push_audio_one_to_many_pairing() at `/Users/leonardofu/dev/back-end/live-broadcast-dubbing-cloud/apps/media-service/tests/unit/test_av_sync_pts_matching.py`: single audio pairs with multiple videos [M]
- [ ] T056 [P] **[US2]** Write unit test test_push_audio_sorted_insertion() at `/Users/leonardofu/dev/back-end/live-broadcast-dubbing-cloud/apps/media-service/tests/unit/test_av_sync_pts_matching.py`: audio maintains sorted order in buffer [M]
- [ ] T057 [P] **[US2]** Write unit test test_audio_reused_for_multiple_videos() at `/Users/leonardofu/dev/back-end/live-broadcast-dubbing-cloud/apps/media-service/tests/unit/test_av_sync_pts_matching.py`: acceptance scenario from spec [M]
- [ ] T058 [P] **[US2]** Write unit test test_audio_reference_counting() at `/Users/leonardofu/dev/back-end/live-broadcast-dubbing-cloud/apps/media-service/tests/unit/test_av_sync_pts_matching.py`: paired_video_pts set grows correctly [M]
- [ ] T059 **[US2]** Refactor push_audio() method signature in AvSyncManager at `/Users/leonardofu/dev/back-end/live-broadcast-dubbing-cloud/apps/media-service/src/media_service/sync/av_sync.py` to return list[SyncPair] | None instead of SyncPair | None [L]
- [ ] T060 **[US2]** Refactor push_audio() method implementation at `/Users/leonardofu/dev/back-end/live-broadcast-dubbing-cloud/apps/media-service/src/media_service/sync/av_sync.py` to support one-to-many pairing [L]
  - Create AudioBufferEntry from segment
  - Find ALL overlapping videos in _video_buffer using _overlaps()
  - Add video.t0_ns to entry.paired_video_pts for each match
  - Create SyncPair for each matching video
  - Remove matched videos from _video_buffer (reverse iteration)
  - Call _insert_audio() to add entry to sorted buffer
  - Call _evict_stale_audio()
  - Return list of SyncPairs or None if empty
- [ ] T061 **[US2]** Verify all push_audio tests pass at `/Users/leonardofu/dev/back-end/live-broadcast-dubbing-cloud/apps/media-service/tests/unit/test_av_sync_pts_matching.py` [L]

---

## Phase 8: Timeout-Based Fallback (TDD)

- [ ] T062 [P] **[US6]** Write unit test test_video_timeout_triggers_fallback() at `/Users/leonardofu/dev/back-end/live-broadcast-dubbing-cloud/apps/media-service/tests/unit/test_av_sync_pts_matching.py`: video > 10s old triggers fallback [M]
- [ ] T063 [P] **[US6]** Write unit test test_check_timeouts_returns_timed_out_videos() at `/Users/leonardofu/dev/back-end/live-broadcast-dubbing-cloud/apps/media-service/tests/unit/test_av_sync_pts_matching.py`: check_timeouts() identifies all expired videos [M]
- [ ] T064 [P] **[US6]** Write unit test test_fallback_audio_has_correct_pts() at `/Users/leonardofu/dev/back-end/live-broadcast-dubbing-cloud/apps/media-service/tests/unit/test_av_sync_pts_matching.py`: fallback AudioSegment has video's t0_ns and duration_ns [M]
- [ ] T065 **[US6]** Implement check_timeouts() method in AvSyncManager at `/Users/leonardofu/dev/back-end/live-broadcast-dubbing-cloud/apps/media-service/src/media_service/sync/av_sync.py` [L]
  - Accept get_original_audio callback and optional current_time_ns
  - Iterate _video_buffer and identify entries where should_fallback() returns True
  - Create fallback AudioSegment with t0_ns=video.t0_ns, duration_ns=video.duration_ns
  - Call get_original_audio() to fetch fallback audio data
  - Create SyncPair for each timed-out video
  - Remove timed-out videos from _video_buffer (reverse iteration)
  - Return list of SyncPairs
- [ ] T066 **[US6]** Verify all timeout tests pass at `/Users/leonardofu/dev/back-end/live-broadcast-dubbing-cloud/apps/media-service/tests/unit/test_av_sync_pts_matching.py` [L]

---

## Phase 9: Drift Detection & Correction Compatibility (TDD)

- [ ] T067 [P] **[US5]** Write unit test test_drift_detection_with_pts_matching() at `/Users/leonardofu/dev/back-end/live-broadcast-dubbing-cloud/apps/media-service/tests/unit/test_av_sync_pts_matching.py`: sync_delta_ns calculated after PTS pair creation [M]
- [ ] T068 [P] **[US5]** Write unit test test_slew_correction_with_variable_audio() at `/Users/leonardofu/dev/back-end/live-broadcast-dubbing-cloud/apps/media-service/tests/unit/test_av_sync_pts_matching.py`: correction works with variable-length segments [M]
- [ ] T069 [P] **[US5]** Write contract test test_drift_metrics_exposed() at `/Users/leonardofu/dev/back-end/live-broadcast-dubbing-cloud/apps/media-service/tests/unit/test_av_sync.py`: Prometheus metrics track drift correctly [M]
- [ ] T070 **[US5]** Verify _create_pair() correctly updates sync_delta_ns for PTS-paired segments at `/Users/leonardofu/dev/back-end/live-broadcast-dubbing-cloud/apps/media-service/src/media_service/sync/av_sync.py` (no changes needed) [S]
- [ ] T071 **[US5]** Verify needs_correction() method works with PTS-based pairing at `/Users/leonardofu/dev/back-end/live-broadcast-dubbing-cloud/apps/media-service/src/media_service/sync/av_sync.py` (no changes needed) [S]
- [ ] T072 **[US5]** Verify all drift detection tests pass at `/Users/leonardofu/dev/back-end/live-broadcast-dubbing-cloud/apps/media-service/tests/unit/test_av_sync_pts_matching.py` [M]

---

## Phase 10: Fallback Integration (TDD)

- [ ] T073 [P] **[US6]** Write integration test test_flush_fallback_with_pts_buffer() at `/Users/leonardofu/dev/back-end/live-broadcast-dubbing-cloud/apps/media-service/tests/integration/test_av_sync_integration.py`: flush_with_fallback pairs buffered videos with original audio [L]
- [ ] T074 [P] **[US6]** Write integration test test_circuit_breaker_fallback_with_vad() at `/Users/leonardofu/dev/back-end/live-broadcast-dubbing-cloud/apps/media-service/tests/integration/test_av_sync_integration.py`: end-to-end fallback with VAD segments [L]
- [ ] T075 **[US6]** Update flush_with_fallback() method in AvSyncManager at `/Users/leonardofu/dev/back-end/live-broadcast-dubbing-cloud/apps/media-service/src/media_service/sync/av_sync.py` to work with list[VideoBufferEntry] (minimal changes expected) [M]
- [ ] T076 **[US6]** Verify all fallback integration tests pass at `/Users/leonardofu/dev/back-end/live-broadcast-dubbing-cloud/apps/media-service/tests/integration/test_av_sync_integration.py` [L]

---

## Phase 11: Existing Test Compatibility

- [ ] T077 **[US1]** Review all existing tests in test_av_sync.py at `/Users/leonardofu/dev/back-end/live-broadcast-dubbing-cloud/apps/media-service/tests/unit/test_av_sync.py` [M]
- [ ] T078 **[US1]** Update assertions in test_av_sync.py to work with PTS-based matching instead of batch_number [L]
  - Replace batch_number assertions with PTS range overlap checks
  - Verify buffering behavior matches PTS logic
  - Update video/audio pairing expectations
- [ ] T079 **[US1]** Run all existing tests to ensure backward compatibility at `/Users/leonardofu/dev/back-end/live-broadcast-dubbing-cloud/apps/media-service/tests/unit/test_av_sync.py` [M]
- [ ] T080 **[US1]** Verify test coverage meets 95% minimum at `/Users/leonardofu/dev/back-end/live-broadcast-dubbing-cloud/apps/media-service/src/media_service/sync/av_sync.py` [M]

---

## Phase 12: Integration Testing with VAD Segments

- [ ] T081 [P] **[US1]** Write integration test test_pts_matching_with_vad_segments() at `/Users/leonardofu/dev/back-end/live-broadcast-dubbing-cloud/apps/media-service/tests/integration/test_av_sync_integration.py`: end-to-end pairing with real VAD-generated audio [L]
- [ ] T082 [P] **[US1]** Write integration test test_variable_length_audio_pairing() at `/Users/leonardofu/dev/back-end/live-broadcast-dubbing-cloud/apps/media-service/tests/integration/test_av_sync_integration.py`: 1-15s audio with 6s videos [L]
- [ ] T083 [P] **[US2]** Write integration test test_one_to_many_pairing_full_flow() at `/Users/leonardofu/dev/back-end/live-broadcast-dubbing-cloud/apps/media-service/tests/integration/test_av_sync_integration.py`: 12-15s audio pairs with 2-3 video segments [L]
- [ ] T084 [P] **[US6]** Write integration test test_timeout_fallback_integration() at `/Users/leonardofu/dev/back-end/live-broadcast-dubbing-cloud/apps/media-service/tests/integration/test_av_sync_integration.py`: timeout and fallback workflow [L]
- [ ] T085 **[US1]** Verify all integration tests pass at `/Users/leonardofu/dev/back-end/live-broadcast-dubbing-cloud/apps/media-service/tests/integration/test_av_sync_integration.py` [L]

---

## Phase 13: Performance & Edge Cases

- [ ] T086 [P] **[US1]** Write performance test test_pairing_latency() at `/Users/leonardofu/dev/back-end/live-broadcast-dubbing-cloud/apps/media-service/tests/unit/test_av_sync_pts_matching.py`: verify pairing completes within 10ms [M]
- [ ] T087 [P] **[US3]** Write edge case test test_exact_boundary_no_overlap() at `/Users/leonardofu/dev/back-end/live-broadcast-dubbing-cloud/apps/media-service/tests/unit/test_av_sync_pts_matching.py`: strict inequality validation [M]
- [ ] T088 [P] **[US3]** Write edge case test test_very_short_audio_segment() at `/Users/leonardofu/dev/back-end/live-broadcast-dubbing-cloud/apps/media-service/tests/unit/test_av_sync_pts_matching.py`: 1-second audio pairing [M]
- [ ] T089 [P] **[US2]** Write edge case test test_maximum_duration_audio() at `/Users/leonardofu/dev/back-end/live-broadcast-dubbing-cloud/apps/media-service/tests/unit/test_av_sync_pts_matching.py`: 15-second audio with 2-3 videos [M]
- [ ] T090 [P] **[US3]** Write edge case test test_out_of_order_segment_arrival() at `/Users/leonardofu/dev/back-end/live-broadcast-dubbing-cloud/apps/media-service/tests/unit/test_av_sync_pts_matching.py`: both audio and video arriving out-of-order [M]
- [ ] T091 **[US3]** Verify all performance and edge case tests pass at `/Users/leonardofu/dev/back-end/live-broadcast-dubbing-cloud/apps/media-service/tests/unit/test_av_sync_pts_matching.py` [M]

---

## Phase 14: Logging & Observability

- [ ] T092 **[US1]** Add DEBUG level logging for segment pairing decisions in push_video() at `/Users/leonardofu/dev/back-end/live-broadcast-dubbing-cloud/apps/media-service/src/media_service/sync/av_sync.py`: log when pairs created or videos buffered [M]
- [ ] T093 **[US2]** Add DEBUG level logging for one-to-many pairing in push_audio() at `/Users/leonardofu/dev/back-end/live-broadcast-dubbing-cloud/apps/media-service/src/media_service/sync/av_sync.py`: log count of videos paired [M]
- [ ] T094 **[US4]** Add DEBUG level logging for audio eviction in _evict_stale_audio() at `/Users/leonardofu/dev/back-end/live-broadcast-dubbing-cloud/apps/media-service/src/media_service/sync/av_sync.py`: log removed entries and watermark [M]
- [ ] T095 **[US6]** Add INFO level logging for fallback triggers in check_timeouts() at `/Users/leonardofu/dev/back-end/live-broadcast-dubbing-cloud/apps/media-service/src/media_service/sync/av_sync.py`: log timeout events [M]
- [ ] T096 **[US3]** Implement audio_buffer_size property in AvSyncManager at `/Users/leonardofu/dev/back-end/live-broadcast-dubbing-cloud/apps/media-service/src/media_service/sync/av_sync.py` returning len(_audio_buffer) [S]
- [ ] T097 **[US3]** Implement video_buffer_size property in AvSyncManager at `/Users/leonardofu/dev/back-end/live-broadcast-dubbing-cloud/apps/media-service/src/media_service/sync/av_sync.py` returning len(_video_buffer) [S]

---

## Phase 15: Final Verification & Polish

- [ ] T098 **[US1]** Run full test suite: `make media-test` at `/Users/leonardofu/dev/back-end/live-broadcast-dubbing-cloud/` [L]
- [ ] T099 **[US1]** Run coverage report: `make media-test-coverage` and verify >= 95% at `/Users/leonardofu/dev/back-end/live-broadcast-dubbing-cloud/` [M]
- [ ] T100 **[US1]** Run linting and formatting: `make fmt && make lint` at `/Users/leonardofu/dev/back-end/live-broadcast-dubbing-cloud/` [M]
- [ ] T101 **[US1]** Run type checking: `make typecheck` at `/Users/leonardofu/dev/back-end/live-broadcast-dubbing-cloud/` [M]
- [ ] T102 **[US1]** Verify no regression in pipeline latency [M]
- [ ] T103 **[US1]** Code review checklist: PTS matching algorithm correctness, buffer management, edge cases, logging, constitution compliance [L]
- [ ] T104 **[US1]** Update docstrings in AvSyncManager and helper methods at `/Users/leonardofu/dev/back-end/live-broadcast-dubbing-cloud/apps/media-service/src/media_service/sync/av_sync.py` [M]
- [ ] T105 **[US1]** Final acceptance testing with real E2E pipeline [L]

---

## Summary

**Total Tasks**: 105
**Estimated Complexity**: 44 Small + 36 Medium + 25 Large
**Parallelizable Tasks [P]**: 47 tasks
**Dependencies**: All foundational tasks must complete before matching/buffer implementation
**Critical Path**: Phase 2 → Phase 3 → Phase 4 → Phase 6 → Phase 7

### Success Criteria

- All 105 tasks completed
- Test coverage >= 95% on av_sync.py
- All existing tests pass with updated PTS-based assertions
- Integration tests validate VAD segment pairing
- No regression in pipeline latency (<10ms per pair)
- Zero constitution violations (TDD, A/V sync discipline, real-time first)
- All edge cases from spec handled correctly
- Code review approved
- E2E pipeline produces synchronized output

---

**Generated**: 2026-01-10
**Next Steps**: Begin Phase 2 - Implement data structures with TDD
