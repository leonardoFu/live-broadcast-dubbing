# Feature Specification: Python Service Repo Setup

**Feature Branch**: `001-python-service-setup`  
**Created**: 2025-12-21  
**Status**: Draft  
**Input**: User description: "setup the repo with [001-1-docker-repo-setup.md](specs/001-1-docker-repo-setup.md) and [012-modern-python-service-setup.md](specs/012-modern-python-service-setup.md) definition, make it a good local development and deploy python service."

## User Scenarios & Testing *(mandatory)*

<!--
  IMPORTANT: User stories should be PRIORITIZED as user journeys ordered by importance.
  Each user story/journey must be INDEPENDENTLY TESTABLE - meaning if you implement just ONE of them,
  you should still have a viable MVP (Minimum Viable Product) that delivers value.
  
  Assign priorities (P1, P2, P3, etc.) to each story, where P1 is the most critical.
  Think of each story as a standalone slice of functionality that can be:
  - Developed independently
  - Tested independently
  - Deployed independently
  - Demonstrated to users independently
-->

### User Story 1 - Start Local Stack (Priority: P1)

Developers can clone the repo and bring up the baseline stack (Python service + MediaMTX orchestration) on CPU-only macOS/Linux using the documented one-command entrypoint, with health checks confirming services are reachable.

**Why this priority**: Local usability is the first blocker for any contribution and validates the Docker-first baseline from `specs/001-1-docker-repo-setup.md`.

**Independent Test**: On a clean machine with prerequisites installed, run the documented single command and verify service and MediaMTX endpoints respond without manual patching.

**Acceptance Scenarios**:

1. **Given** a fresh clone with prerequisites (container runtime, Python), **When** the one-command start is executed, **Then** the stack starts without editing files and health endpoints report ready status.
2. **Given** the stack is running, **When** a sample stream is published to the documented ingest path, **Then** the stack keeps running and logs confirm ingest and processing without manual container restarts.

---

### User Story 2 - Standard Dev Checks (Priority: P2)

Contributors can run formatting, linting, strict type checks, and tests through consistent commands defined in `specs/012-modern-python-service-setup.md` and get deterministic pass/fail results.

**Why this priority**: Shared quality gates reduce review churn and ensure strict typing is upheld across the service.

**Independent Test**: On any supported machine, executing the documented command set runs format, lint, type, and test tasks without extra flags or manual fixes.

**Acceptance Scenarios**:

1. **Given** a clean environment with dependencies installed, **When** the standard commands are executed, **Then** they complete without missing-tool errors and report clear success/failure status.

---

### User Story 3 - Container Build & Deploy Readiness (Priority: P3)

Maintainers can build and run the Python service image with documented environment inputs, enabling promotion to a runtime environment without guessing configuration.

**Why this priority**: Deployment confidence depends on having a reproducible, CPU-friendly image and clear configuration surface.

**Independent Test**: Building the image with the documented command succeeds on macOS/Linux, and running it with the sample env file keeps the service healthy long enough to exercise smoke checks.

**Acceptance Scenarios**:

1. **Given** a machine with container tooling, **When** the documented build command runs, **Then** the image builds without manual edits and produces tagged output.
2. **Given** the built image and sample env file, **When** the container starts, **Then** it stays healthy and exposes the documented port/configuration surface for downstream integration.

---

### Edge Cases

- Prerequisites missing (container runtime, Python 3.10 baseline): startup commands must fail fast with actionable instructions instead of partial setup.
- Port conflicts on developer machines: documented overrides allow changing ports without editing multiple files and without breaking service discovery.
- Unsupported CPU architecture defaults (e.g., arm64 needing `linux/amd64` images): guidance provided to switch architectures while keeping commands identical.
- Absent secrets/API keys: services refuse to start with clear messaging and `.env.example` placeholders, avoiding silent failures.

### Test Assets (Mock Fixtures)

- **Required assets**: 5–10s sample audio/video clip compatible with MediaMTX ingest (public-domain H.264 + AAC) for smoke publishing; optional small PCM/WAV sample for service-level unit tests.
- **How to provide**: Document a download/generation step and configurable path variable so developers can place assets locally without committing them.
- **Constraints**: Assets must be non-secret, redistributable, and deterministic; tests must pass without external network fetches once assets are present.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Provide a documented one-command entrypoint that starts the local stack (Python service + MediaMTX + orchestration) on CPU-only macOS/Linux, aligned with `specs/001-1-docker-repo-setup.md`.
- **FR-002**: Supply reproducible developer commands for formatting, linting, strict type checking, and tests, consistent with `specs/012-modern-python-service-setup.md`, and ensure they succeed on a fresh install.
- **FR-003**: Deliver a `.env.example` (or equivalent) enumerating all required environment variables for local runs and deployments, with safe defaults and placeholders for secrets.
- **FR-004**: Provide onboarding documentation that lists prerequisites, the single startup command, health checks, and smoke-test steps (including sample stream publish) without referencing implementation-specific tools.
- **FR-005**: Enable container image builds for the Python service using CPU-friendly settings, producing tagged artifacts that run with the same env surface as local development.
- **FR-006**: Ensure local and containerized runs expose clear health/ready signals so developers can verify the service and MediaMTX components are reachable after startup.
- **FR-007**: Allow port and architecture overrides (e.g., `linux/amd64` on Apple Silicon) through documented configuration without editing source files.
- **FR-008**: Keep dependency sources centralized (single requirements manifest) and ensure the documented install flow matches the strict type-checking policy.

### Key Entities *(include if feature involves data)*

- **Local Runtime Stack**: Collection of services required for development (Python service, MediaMTX, orchestration), with expected ports, profiles, and health signals.
- **Environment Configuration**: Set of variables controlling endpoints, auth keys, architecture/profile toggles, and cache locations; must support defaults for CPU-only development.

## Interfaces & Operational Constraints *(if applicable)*

### Interfaces / Protocols

- **Changed interfaces**: Documented ingress/egress paths for MediaMTX (`live/<streamId>/in` and `live/<streamId>/out`) and any health/metrics endpoints exposed by the Python service for smoke checks.
- **Contract documentation**: Reference `specs/001-1-docker-repo-setup.md` and `specs/002-mediamtx.md` for hook and path expectations; include pointers in onboarding docs.
- **Compatibility**: Maintain backward-compatible paths and configs with existing specs; overrides must not break the default workflow described in `specs/001-spec.md`.

### Real-Time / Streaming Constraints

- **Latency budget impact**: Local stack setup must not add extra buffering beyond the baseline defined in streaming specs; smoke tests should confirm ingest-to-egress flow within the expected few-second range.
- **A/V sync risks**: Configuration defaults should preserve the existing sync strategy (passthrough video + remixed audio) and include checks to detect drift during smoke publishing.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: From a fresh clone on macOS or Linux, the documented one-command startup completes and all health checks pass within 10 minutes without editing configuration files.
- **SC-002**: The standard `fmt`, `lint`, `typecheck`, and `test` commands run to completion in under 3 minutes on a typical developer laptop and report zero failures after initial setup.
- **SC-003**: Building the Python service image with the documented command succeeds on CPU-only hosts in under 15 minutes and produces an image that stays healthy for at least 5 minutes using the sample env file.
- **SC-004**: Publishing the sample stream to the documented ingest path results in a reachable processed output path within 2 minutes, demonstrating the end-to-end flow without manual container restarts.
