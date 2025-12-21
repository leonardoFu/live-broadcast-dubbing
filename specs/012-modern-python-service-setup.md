# Modern Python Service Setup (Strict Typing)

## 1. Goal

Document a minimal, modern Python service setup for this repo that:
- Uses strict type checking end-to-end (mypy `strict=true`).
- Standardizes formatting/linting/testing commands for contributors.
- Keeps the stack CPU-friendly while supporting the MediaMTX + GStreamer worker flow.

## 2. Non-Goals

- Selecting a specific web framework or API surface.
- Adding GPU/runtime variants (CPU-only baseline).
- Defining MediaMTX or GStreamer pipelines (covered in `specs/002-mediamtx.md` and `specs/003-gstreamer-stream-worker.md`).

## 3. Project Layout Touchpoints

- `pyproject.toml`: houses ruff and mypy strict settings (target Python 3.10).
- `Makefile`: canonical dev commands (`fmt`, `lint`, `typecheck`, `test`).
- `deploy/`: Docker assets for MediaMTX + worker (see `specs/001-1-docker-repo-setup.md`).
- `specs/003-gstreamer-stream-worker.md`: worker behavior; this setup ensures the Python side is type-safe.

## 4. Tooling & Policies

- **Formatting**: `ruff format .`
- **Linting**: `ruff check .`
- **Type checking**: `mypy --strict` (already configured with strict options; keep `ignore_missing_imports=true` until stubs are added).
- **Testing**: `pytest -q`
- **Targets**: Python `3.10.x`; ensure docker images and local venvs match.

## 5. Dependency Management

- Prefer `requirements-dev.txt` / `pyproject.toml` as the source of truth; avoid ad-hoc `pip freeze`.
- Keep optional heavy deps (e.g., separation models) behind extras or flags; default image remains CPU-only.
- Pin only when needed for compatibility (e.g., `numpy<2.0`).

## 6. Local Development Workflow

1) Create/activate a venv: `python3 -m venv .venv && source .venv/bin/activate`
2) Install deps: `pip install -r requirements-dev.txt`
3) Run format/lint/type/test before commits:
   - `make fmt`
   - `make lint`
   - `make typecheck`
   - `make test`
4) For Docker baseline (MediaMTX + worker): `make dev` (see `specs/001-1-docker-repo-setup.md`).

## 7. Type-Checking Policy

- All new Python files MUST be typed and pass `mypy --strict`.
- Avoid `type: ignore` unless accompanied by a brief comment; remove unused ignores.
- Keep `ignore_missing_imports=true` temporarily for third-party libs without stubs; prefer adding stubs over time.

## 8. CI Recommendations (future)

- Single job running `make lint typecheck test`.
- Cache pip/venv directories to speed up runs.
- Fail fast on lint/type errors; run tests after static checks.

## 9. Success Criteria

- Fresh clone: `pip install -r requirements-dev.txt && make lint typecheck test` passes on CPU-only macOS/Linux.
- Docker baseline runs MediaMTX + worker using CPU-only images.
- Contributors rely on the documented commands with consistent results (no per-developer tooling drift).
