# E2E Infrastructure Validation Checklist: Dual Docker-Compose E2E Test Infrastructure

**Purpose**: Comprehensive validation of requirements quality for dual docker-compose E2E test infrastructure covering infrastructure configuration, test coverage, integration contracts, and resilience across all scenario classes.

**Created**: 2026-01-01

**Feature**: [spec.md](../spec.md) | [plan.md](../plan.md)

**Scope**: All dimensions (infrastructure + tests + contracts + resilience) with mandatory gating checks for high-risk areas (networking, STS validation, isolation, timeouts) and complete scenario class coverage (primary, exception, recovery, non-functional).

---

## Docker Compose Infrastructure Requirements

### Configuration Completeness

- [ ] CHK001 - Are all required services explicitly defined in `apps/media-service/docker-compose.e2e.yml`? [Completeness, Spec §FR-003]
- [ ] CHK002 - Are all required services explicitly defined in `apps/sts-service/docker-compose.e2e.yml`? [Completeness, Spec §FR-004]
- [ ] CHK003 - Are container names specified to avoid conflicts with other docker-compose environments? [Clarity, Spec §AD-1]
- [ ] CHK004 - Are restart policies explicitly defined for all services (e.g., `restart: "no"` for test environments)? [Completeness]
- [ ] CHK005 - Are docker-compose versions specified consistently across both files? [Consistency]

### Port Exposure Requirements

- [ ] CHK006 - Are all required ports explicitly exposed in media-service composition (8080, 8554, 1935, 9997)? [Completeness, Spec §FR-006]
- [ ] CHK007 - Is STS service port 3000 explicitly exposed in sts-service composition? [Completeness, Spec §FR-007]
- [ ] CHK008 - Are port mappings configurable via environment variables to avoid conflicts? [Completeness, Spec §FR-008]
- [ ] CHK009 - Are default port values sensible and documented in `.env.e2e.example` files? [Clarity, Spec §FR-028]
- [ ] CHK010 - Is the port exposure strategy consistent between both docker-compose files? [Consistency]

### Networking Requirements

- [ ] CHK011 - Is the networking mode (bridge) explicitly specified or documented as default? [Clarity, Spec §AD-2]
- [ ] CHK012 - Are internal service communication URLs using container names (e.g., `rtsp://mediamtx:8554`) correctly specified? [Completeness, Spec §AD-2]
- [ ] CHK013 - Are external service communication URLs using `host.docker.internal` or `localhost` correctly specified? [Completeness, Spec §FR-005, §AD-2]
- [ ] CHK014 - Is the `extra_hosts` configuration for `host.docker.internal` documented in media-service composition? [Completeness, Plan §Networking]
- [ ] CHK015 - Are networking requirements consistent across Linux and macOS (host.docker.internal support)? [Consistency, Plan §Research Task 6]

### Volume & Storage Requirements

- [ ] CHK016 - Are all required docker volumes defined in both compositions (segments-data, model-cache)? [Completeness, Spec §Docker Compose]
- [ ] CHK017 - Are volume mount paths explicitly specified for all services? [Completeness]
- [ ] CHK018 - Is the model cache volume strategy documented to persist across test runs? [Clarity, Plan §Test Fixtures]
- [ ] CHK019 - Are volume cleanup requirements defined in pytest teardown procedures? [Gap, Spec §FR-034]
- [ ] CHK020 - Are volume permissions and ownership requirements specified? [Gap]

### Health Check Requirements

- [ ] CHK021 - Are health check commands defined for all services (MediaMTX, media-service, sts-service)? [Completeness, Spec §FR-009]
- [ ] CHK022 - Are health check intervals, timeouts, and retry limits explicitly specified? [Completeness, Spec §Docker Compose]
- [ ] CHK023 - Is the health check `start_period` for STS service sufficient for model loading (30s+)? [Clarity, Spec §Docker Compose, Plan §Research Task 3]
- [ ] CHK024 - Are health check endpoints documented and validated (/health, /v3/paths/list)? [Completeness, Plan §Contracts]
- [ ] CHK025 - Can health check success be objectively measured in pytest fixtures? [Measurability, Spec §FR-032]

### Environment Variable Requirements

- [ ] CHK026 - Are all service endpoints configurable via environment variables? [Completeness, Spec §FR-027]
- [ ] CHK027 - Are environment variable defaults provided using `${VAR:-default}` syntax? [Completeness, Spec §FR-028]
- [ ] CHK028 - Is the complete set of required environment variables documented in `.env.e2e.example`? [Completeness, Plan §Contracts]
- [ ] CHK029 - Are environment variable names consistent across both compositions? [Consistency]
- [ ] CHK030 - Are sensitive values (if any) excluded from docker-compose files with clear documentation? [Security, Gap]

---

## Test Coverage & Scenario Requirements

### Primary Flow Requirements

- [ ] CHK031 - Are acceptance criteria defined for full pipeline E2E test (fixture → STS → output)? [Completeness, Spec §US-1]
- [ ] CHK032 - Is the expected segment count (5 segments @ 6s each) explicitly specified? [Clarity, Spec §FR-016]
- [ ] CHK033 - Are processing time limits quantified (180s max for 30s fixture)? [Measurability, Spec §FR-014, §SC-001]
- [ ] CHK034 - Are output stream validation criteria explicitly defined (codecs, duration, A/V sync)? [Completeness, Spec §FR-023 to §FR-026]
- [ ] CHK035 - Is the dual validation strategy (Socket.IO events + audio fingerprinting) clearly documented? [Clarity, Spec §FR-024, Clarification Q4]

### Service Discovery & Communication Requirements

- [ ] CHK036 - Are service connectivity requirements specified for all inter-service communication? [Completeness, Spec §US-2]
- [ ] CHK037 - Are Socket.IO connection establishment requirements defined with timeout limits? [Completeness, Spec §FR-005]
- [ ] CHK038 - Are health check validation requirements specified before test execution? [Completeness, Spec §FR-032]
- [ ] CHK039 - Is the expected health check pass time quantified (within 30 seconds)? [Measurability, Spec §SC-006]
- [ ] CHK040 - Are requirements defined for validating all exposed ports are accessible? [Coverage, Spec §US-2]

### Real STS Processing Requirements

- [ ] CHK041 - Are ASR accuracy validation requirements specified with expected transcript content? [Completeness, Spec §FR-019, §FR-016a]
- [ ] CHK042 - Are translation validation requirements defined for target language output (Spanish)? [Completeness, Spec §FR-020]
- [ ] CHK043 - Are TTS output validation requirements specified (dubbed audio vs. original)? [Completeness, Spec §FR-021]
- [ ] CHK044 - Are fragment:processed event field requirements documented (transcript, translated_text, dubbed_audio)? [Completeness, Spec §FR-022]
- [ ] CHK045 - Is the expected ASR variance tolerance defined for counting phrase transcripts? [Clarity, Spec §FR-016a]

### Test Fixture Requirements

- [ ] CHK046 - Are test fixture specifications complete (duration, codecs, sample rate, content)? [Completeness, Spec §FR-016]
- [ ] CHK047 - Is the counting phrase audio content specification unambiguous ("One, two, three... thirty" at ~1 number/second)? [Clarity, Spec §FR-016a, Clarification Q2]
- [ ] CHK048 - Are test fixture validation requirements defined (properties check before pipeline tests)? [Completeness, Spec §US-4]
- [ ] CHK049 - Are fixture publishing requirements specified (ffmpeg command, RTSP URL format)? [Completeness, Spec §FR-017]
- [ ] CHK050 - Are cleanup requirements for ffmpeg processes explicitly defined? [Completeness, Spec §FR-018]

### Output Validation Requirements

- [ ] CHK051 - Are ffprobe inspection requirements specified for all output validation? [Completeness, Spec §FR-023]
- [ ] CHK052 - Are audio fingerprinting validation requirements defined with specific comparison algorithm? [Clarity, Spec §FR-024, Plan §Research Task 4]
- [ ] CHK053 - Are A/V sync validation requirements quantified with PTS delta threshold (<120ms)? [Measurability, Spec §FR-025]
- [ ] CHK054 - Are output duration validation requirements specified with tolerance (+/- 500ms)? [Measurability, Spec §FR-026]
- [ ] CHK055 - Is the dual validation approach (events + fingerprint) consistently applied? [Consistency, Spec §FR-024]

### Pytest Fixture Lifecycle Requirements

- [ ] CHK056 - Is the pytest fixture scope (session) explicitly documented with justification? [Clarity, Spec §FR-031, Clarification Q5]
- [ ] CHK057 - Are unique stream name requirements per test clearly specified? [Completeness, Spec §FR-031a]
- [ ] CHK058 - Are fixture cleanup requirements defined even on test failure (SIGINT, SIGTERM)? [Completeness, Spec §FR-034]
- [ ] CHK059 - Are log collection requirements specified for test failure debugging? [Completeness, Spec §FR-033]
- [ ] CHK060 - Is the session-scoped model loading cost amortization strategy documented? [Clarity, Plan §Test Strategy, Clarification Q5]

---

## Integration Contract Requirements

### Socket.IO Protocol Requirements

- [ ] CHK061 - Are fragment:data event payload requirements completely specified? [Completeness, Spec §Dependencies, Spec 016]
- [ ] CHK062 - Are fragment:processed event payload requirements completely specified? [Completeness, Spec §FR-022]
- [ ] CHK063 - Is the Socket.IO connection path (`/socket.io`) explicitly configured? [Clarity, Spec §Docker Compose]
- [ ] CHK064 - Are event sequence requirements defined (order, count validation)? [Completeness, Spec §US-3]
- [ ] CHK065 - Are Socket.IO monitoring requirements for E2E tests clearly documented? [Completeness, Plan §Test Strategy]

### MediaMTX Integration Requirements

- [ ] CHK066 - Are RTSP ingest URL format requirements specified? [Completeness, Spec §FR-010]
- [ ] CHK067 - Are RTMP output URL format requirements specified? [Completeness, Spec §FR-010]
- [ ] CHK068 - Are MediaMTX API endpoint requirements documented (/v3/paths/list)? [Completeness, Spec §Docker Compose]
- [ ] CHK069 - Is stream naming convention documented (unique per test: `/live/{test_name}/in`)? [Clarity, Spec §FR-031a]
- [ ] CHK070 - Are stream cleanup requirements between tests defined? [Gap, Spec §FR-031a]

### Prometheus Metrics Requirements

- [ ] CHK071 - Are metrics endpoint requirements specified (/metrics on port 8080)? [Completeness, Spec §Docker Compose]
- [ ] CHK072 - Are required metric names documented (worker_audio_fragments_total, worker_av_sync_delta_ms)? [Completeness, Plan §Data Model]
- [ ] CHK073 - Are metrics parsing requirements for test validation defined? [Completeness, Plan §Test Strategy]
- [ ] CHK074 - Can metrics-based success criteria be objectively measured? [Measurability, Plan §Data Model]
- [ ] CHK075 - Are metrics collection requirements consistent across all test types? [Consistency]

### Environment Configuration Contracts

- [ ] CHK076 - Are media-service environment variable contracts documented in JSON schema? [Completeness, Plan §API Contracts]
- [ ] CHK077 - Are sts-service environment variable contracts documented in JSON schema? [Completeness, Plan §API Contracts]
- [ ] CHK078 - Are environment variable override requirements for pytest defined? [Completeness, Spec §FR-029]
- [ ] CHK079 - Are CI/CD environment customization requirements specified? [Completeness, Spec §US-7]
- [ ] CHK080 - Can environment configuration be validated before test execution? [Measurability, Spec §FR-030]

---

## Exception & Error Handling Requirements

### Service Failure Scenarios

- [ ] CHK081 - Are requirements defined for STS service unreachable scenario? [Completeness, Spec §Edge Cases]
- [ ] CHK082 - Are retry and backoff requirements specified for service connection failures? [Clarity, Spec §Edge Cases]
- [ ] CHK083 - Are error message requirements defined for test failure diagnostics? [Completeness, Spec §Edge Cases]
- [ ] CHK084 - Are requirements specified for MediaMTX RTSP disconnection mid-test? [Completeness, Spec §Edge Cases]
- [ ] CHK085 - Are docker-compose startup failure requirements defined (port conflicts)? [Completeness, Spec §Edge Cases]

### Test Fixture Error Scenarios

- [ ] CHK086 - Are requirements defined for missing test fixture file scenario? [Completeness, Spec §Edge Cases]
- [ ] CHK087 - Are requirements specified for test fixture with no audio track? [Completeness, Spec §Edge Cases]
- [ ] CHK088 - Are validation requirements defined for malformed test fixture properties? [Coverage, Gap]
- [ ] CHK089 - Are requirements specified for ffmpeg publish failure scenarios? [Coverage, Gap]
- [ ] CHK090 - Is fixture file format validation required before pipeline tests? [Gap]

### STS Processing Error Scenarios

- [ ] CHK091 - Are timeout requirements for STS fragment processing explicitly defined (30s)? [Completeness, Spec §FR-014, Clarification Q3]
- [ ] CHK092 - Are passthrough fallback requirements clearly specified for timeout scenarios? [Completeness, Spec §AD-8, Clarification Q3]
- [ ] CHK093 - Are requirements defined for STS processing very slow (>30s per fragment)? [Completeness, Spec §Edge Cases, Clarification Q3]
- [ ] CHK094 - Are warning log requirements specified for passthrough fallback activation? [Clarity, Spec §AD-8]
- [ ] CHK095 - Can graceful degradation behavior be objectively validated in tests? [Measurability, Spec §AD-8]

### Output Stream Error Scenarios

- [ ] CHK096 - Are requirements defined for RTMP publish failure scenario? [Completeness, Spec §Edge Cases]
- [ ] CHK097 - Are requirements specified for A/V sync exceeding threshold (>120ms)? [Coverage, Gap]
- [ ] CHK098 - Are requirements defined for output stream duration mismatch (>500ms variance)? [Coverage, Gap]
- [ ] CHK099 - Are validation requirements specified for corrupted or incomplete output? [Gap]
- [ ] CHK100 - Are requirements defined for audio fingerprint comparison failure scenarios? [Gap]

### Docker Infrastructure Error Scenarios

- [ ] CHK101 - Are requirements defined for docker volume permission errors? [Gap]
- [ ] CHK102 - Are requirements specified for health check timeout failures? [Completeness, Spec §Edge Cases]
- [ ] CHK103 - Are requirements defined for network name conflict scenarios? [Completeness, Spec §Edge Cases]
- [ ] CHK104 - Are log collection requirements specified when docker-compose fails to start? [Completeness, Spec §FR-033]
- [ ] CHK105 - Are requirements defined for insufficient system resources (CPU, RAM)? [Gap]

---

## Recovery & Cleanup Requirements

### Test Interruption Recovery

- [ ] CHK106 - Are cleanup requirements defined for SIGINT (Ctrl+C) interruption? [Completeness, Spec §FR-034]
- [ ] CHK107 - Are cleanup requirements defined for SIGTERM signal handling? [Completeness, Spec §FR-034]
- [ ] CHK108 - Are orphaned process cleanup requirements specified (ffmpeg, docker-compose)? [Completeness, Spec §FR-018]
- [ ] CHK109 - Are orphaned volume cleanup requirements defined? [Gap, Spec §FR-034]
- [ ] CHK110 - Can cleanup success be objectively verified in pytest teardown? [Measurability, Spec §FR-034]

### Session-Scoped Fixture Cleanup

- [ ] CHK111 - Are cleanup requirements for session-scoped fixtures explicitly defined? [Completeness, Spec §FR-031, Plan §Test Strategy]
- [ ] CHK112 - Are stream cleanup requirements between function-scoped tests specified? [Completeness, Spec §FR-031a]
- [ ] CHK113 - Are docker-compose down requirements documented in session teardown? [Completeness, Plan §Test Fixtures]
- [ ] CHK114 - Are model cache preservation requirements across test runs documented? [Clarity, Plan §Test Fixtures]
- [ ] CHK115 - Are requirements defined for partial cleanup on test suite failure? [Gap]

### Resource State Validation

- [ ] CHK116 - Are requirements defined for validating all containers stopped after teardown? [Gap]
- [ ] CHK117 - Are requirements specified for validating all ports released after teardown? [Gap]
- [ ] CHK118 - Are requirements defined for validating no orphaned ffmpeg processes remain? [Gap]
- [ ] CHK119 - Are log archival requirements specified for failed test debugging? [Completeness, Spec §FR-033]
- [ ] CHK120 - Can resource cleanup be validated before subsequent test runs? [Measurability, Gap]

### Rollback & Recovery Procedures

- [ ] CHK121 - Are rollback requirements defined for docker-compose startup failures? [Gap]
- [ ] CHK122 - Are recovery requirements specified for partial service startup? [Gap]
- [ ] CHK123 - Are requirements defined for resetting test environment to clean state? [Gap]
- [ ] CHK124 - Are manual cleanup procedures documented when automated cleanup fails? [Gap]
- [ ] CHK125 - Are requirements specified for recovering from docker network conflicts? [Gap]

---

## Non-Functional Requirements

### Performance Requirements

- [ ] CHK126 - Are performance targets quantified for full pipeline E2E test (180s max)? [Measurability, Spec §FR-014, §SC-001]
- [ ] CHK127 - Are real STS processing time expectations documented (10-17s per fragment)? [Clarity, Plan §Research Task 3]
- [ ] CHK128 - Are health check pass time requirements specified (within 30s)? [Measurability, Spec §SC-006]
- [ ] CHK129 - Are model loading time requirements documented for STS service (30s+)? [Clarity, Spec §Docker Compose]
- [ ] CHK130 - Are test suite total execution time targets defined (<10 minutes)? [Measurability, Plan §Coverage Enforcement]

### Reliability Requirements

- [ ] CHK131 - Are test reliability targets quantified (95% pass rate over 10 runs)? [Measurability, Spec §SC-007, Plan §Coverage Enforcement]
- [ ] CHK132 - Are deterministic test fixture requirements specified to avoid flakiness? [Completeness, Spec §FR-016a]
- [ ] CHK133 - Are retry requirements defined for transient infrastructure failures? [Gap]
- [ ] CHK134 - Are stability requirements specified for session-scoped fixtures? [Gap]
- [ ] CHK135 - Can reliability metrics be objectively measured in CI/CD? [Measurability, Spec §SC-007]

### Resource Requirements

- [ ] CHK136 - Are minimum system resource requirements documented (4 CPU cores, 8GB RAM)? [Completeness, Spec §Assumptions]
- [ ] CHK137 - Are docker volume size requirements specified for model cache? [Gap]
- [ ] CHK138 - Are network bandwidth requirements documented for RTSP/RTMP streaming? [Gap]
- [ ] CHK139 - Are disk space requirements specified for test fixtures and logs? [Gap]
- [ ] CHK140 - Are resource limit configurations documented in docker-compose files? [Gap]

### Observability Requirements

- [ ] CHK141 - Are logging requirements specified for all services (log levels, formats)? [Completeness, Spec §Docker Compose]
- [ ] CHK142 - Are metrics collection requirements defined for test validation? [Completeness, Plan §Data Model]
- [ ] CHK143 - Are log capture requirements specified for test failure debugging? [Completeness, Spec §FR-033]
- [ ] CHK144 - Are container log retention requirements documented? [Gap]
- [ ] CHK145 - Can debugging information be easily collected from failed tests? [Measurability, Spec §FR-033]

### Portability Requirements

- [ ] CHK146 - Are cross-platform requirements specified (Linux vs. macOS)? [Completeness, Plan §Research Task 6]
- [ ] CHK147 - Are host.docker.internal compatibility requirements documented? [Completeness, Plan §Research Task 6]
- [ ] CHK148 - Are CI/CD environment requirements specified? [Completeness, Spec §US-7]
- [ ] CHK149 - Are docker version requirements documented (Docker Engine, Compose v2)? [Completeness, Plan §Dependencies]
- [ ] CHK150 - Are Python version requirements specified (3.10.x)? [Completeness, Plan §Technical Context]

---

## Documentation & Traceability Requirements

### Specification Completeness

- [ ] CHK151 - Are all functional requirements (FR-001 to FR-034) complete and unambiguous? [Completeness, Spec §Requirements]
- [ ] CHK152 - Are all success criteria (SC-001 to SC-008) measurable and testable? [Measurability, Spec §Success Criteria]
- [ ] CHK153 - Are all architecture decisions (AD-1 to AD-8) documented with rationale? [Completeness, Spec §Architecture Decisions]
- [ ] CHK154 - Are all edge cases documented with clear expected behavior? [Completeness, Spec §Edge Cases]
- [ ] CHK155 - Are all assumptions validated and documented? [Completeness, Spec §Assumptions]

### Requirements Traceability

- [ ] CHK156 - Are all user stories (US-1 to US-7) mapped to specific test files? [Traceability, Plan §Test Strategy]
- [ ] CHK157 - Are all functional requirements mapped to acceptance scenarios? [Traceability, Spec §User Scenarios]
- [ ] CHK158 - Are all test priorities (P1, P2, P3) aligned with user story priorities? [Consistency, Plan §Test Implementation Phases]
- [ ] CHK159 - Are all architecture decisions traceable to specific requirements? [Traceability, Spec §Architecture Decisions]
- [ ] CHK160 - Are all clarification answers (Q1-Q5) incorporated into requirements? [Traceability, Spec §Clarifications]

### Contract Documentation

- [ ] CHK161 - Are all API contracts documented in contracts/ directory? [Completeness, Plan §API Contracts]
- [ ] CHK162 - Are all environment variable schemas complete (media-service-env.json, sts-service-env.json)? [Completeness, Plan §API Contracts]
- [ ] CHK163 - Are health check endpoint contracts documented with expected responses? [Completeness, Plan §API Contracts]
- [ ] CHK164 - Are Socket.IO event contracts consistent with spec 016? [Consistency, Spec §Dependencies]
- [ ] CHK165 - Are stream URL format requirements consistently documented? [Consistency, Plan §Data Model]

### Implementation Guidance

- [ ] CHK166 - Are quickstart.md prerequisites completely specified? [Completeness, Plan §Quickstart Guide]
- [ ] CHK167 - Are troubleshooting procedures documented for common failure scenarios? [Completeness, Plan §Quickstart Guide]
- [ ] CHK168 - Are debugging procedures specified for test failures? [Completeness, Plan §Quickstart Guide]
- [ ] CHK169 - Are extension points documented for adding new E2E tests? [Completeness, Plan §Quickstart Guide]
- [ ] CHK170 - Are development workflow commands documented (make targets, pytest commands)? [Gap]

### Dependency Documentation

- [ ] CHK171 - Are all external service dependencies documented with versions? [Completeness, Plan §Dependencies]
- [ ] CHK172 - Are all Python library dependencies documented with version constraints? [Completeness, Plan §Dependencies]
- [ ] CHK173 - Are all infrastructure dependencies documented (Docker, ffmpeg)? [Completeness, Plan §Dependencies]
- [ ] CHK174 - Are cross-spec dependencies clearly referenced (specs 003, 005, 006, 008, 016, 017, 018)? [Completeness, Spec §Dependencies]
- [ ] CHK175 - Are out-of-scope items clearly documented to prevent scope creep? [Completeness, Spec §Out of Scope]

---

## Notes

- Check items off as completed: `[x]`
- Add comments or findings inline with reference to spec/plan sections
- Link to relevant resources or documentation when issues discovered
- Items are numbered sequentially (CHK001-CHK175) for easy reference
- Priority focus areas: Networking (CHK011-CHK015), STS Validation (CHK041-CHK045, CHK091-CHK095), Test Isolation (CHK056-CHK060, CHK111-CHK115), Timeouts (CHK091-CHK095, CHK126-CHK130)
- All items test requirements quality (completeness, clarity, consistency, measurability, coverage) - NOT implementation correctness
