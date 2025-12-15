# Repository Guidelines

## Project Structure & Module Organization

- `specs/`: Product/architecture specs. Start here before implementing changes.
- `.specify/`: Spec templates and shared “memory” used to generate/maintain specs.
- `.codex/`: Local agent prompts/workflows for this repo.

Planned runtime components (not all may exist yet):
- `apps/sts-service/`: Speech→Text→Speech service referenced by `specs/001-spec.md`.
- `apps/stream-worker/`: GStreamer-based stream worker that pulls from MediaMTX, processes audio, and republishes.
- `infra/` or `deploy/`: Container/runtime configuration (e.g., MediaMTX, compose files).

## Build, Test, and Development Commands

This repository currently contains specifications and templates only; build/test scripts may be added as implementation lands. When adding a runnable component, provide a minimal local workflow and document it here (examples):

- `make dev`: Run the service locally (preferred entrypoint if you add a Makefile).
- `docker compose up`: Start dependent services (e.g., MediaMTX) for local integration.
- `make test` / `npm test` / `pytest`: Run the module’s test suite.

## Coding Style & Naming Conventions

- Specs: keep headings stable, prefer short sections, and use fenced code blocks for pipelines/commands.
- Paths: use kebab-case for spec filenames (e.g., `specs/002-audio-pipeline.md`).
- If you introduce code, add a formatter/linter early and make it runnable via a single command (e.g., `make fmt`, `make lint`).

## Testing Guidelines

- Add tests alongside each module (e.g., `apps/<module>/tests/`), and keep integration tests separate (e.g., `tests/integration/`).
- Prefer deterministic tests; avoid requiring live RTMP endpoints. Mock STS events (`fragment:data`, `fragment:processed`) where possible.

## Commit & Pull Request Guidelines

- Git history is not established yet; use Conventional Commits (`feat:`, `fix:`, `chore:`, `docs:`) going forward.
- PRs should link the relevant spec (e.g., `specs/001-spec.md`) and describe: local run steps, latency/AV-sync impact, and any config changes.
- Do not commit secrets (RTMP stream keys, API tokens). Add `.env.example` when introducing new required env vars.

