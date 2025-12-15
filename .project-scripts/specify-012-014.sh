#!/usr/bin/env bash
set -euo pipefail

# Wrapper script to generate the "missing specs bundle" (012–014) as
# THREE SEPARATE Codex runs (one per spec file).
#
# Each run:
# - invokes `/prompts:speckit.specify`
# - instructs Codex to only write ONE spec file
# - forbids any other operations (no commands, no branches, no non-spec edits)

repo_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"

codex_yolo_flag=()
if codex --help 2>/dev/null | grep -q -- "--yolo"; then
  codex_yolo_flag=(--yolo)
else
  codex_yolo_flag=(--dangerously-bypass-approvals-and-sandbox)
fi

run_one() {
  local name="$1"
  local prompt="$2"

  echo "==> Generating ${name}" >&2
  printf '%s\n' "$prompt" | codex "${codex_yolo_flag[@]}" exec -C "$repo_root" -
}

common_constraints="$(cat <<'PROMPT'
SPEC FILES ONLY — NO EXTRA OPERATIONS:
- Only create/update Markdown spec files under `specs/`.
- Do NOT run shell commands (no `git`, no `make`, no `docker`, no `curl`, no installs).
- Do NOT create branches, commits, or checklists. Do NOT write under `.specify/` or `.codex/`.
- Do NOT change any non-spec file (no `deploy/`, no `apps/`, no `Makefile`).

Repo decisions to align with:
- Stream identity is path-based: `live/<streamId>/in` and `live/<streamId>/out`
- Orchestrator service name: `stream-orchestration` (HTTP hook receiver)
- One worker per stream; stop on not-ready after a grace period (default 30s)
- Worker: STS in-process, internal audio PCM S16LE @ 48kHz stereo, initial buffering target 10s, codec copy for video, backpressure stalls output and alerts
- Recording disabled in v0 (MediaMTX record: no)
- Dev access is unauthenticated ("everyone") and ops/security hardening is deferred
- Observability logs should be persisted to filesystem in dev; do not log frame-by-frame; log per-fragment operations and errors
- On cached asset partial/corruption: delete; write via temp file + atomic rename; keep same `runId` for now (and add `instanceId` per process)
PROMPT
)"

prompt_012="$(cat <<PROMPT
/prompts:speckit.specify

${common_constraints}

Target spec file: \`specs/012-egress-forwarder.md\`
Only create/update \`specs/012-egress-forwarder.md\`. Do not touch any other file.

Task:
Write a spec for the egress forwarder as a separate per-stream process managed by \`stream-orchestration\`.
- Input: pull \`rtsp://mediamtx:8554/live/<streamId>/out\` (codec copy)
- Output: push to 3rd-party RTMP destination (optional; can be disabled in dev)
- Multi-destination: v0 supports a single destination; allow list later
- Forwarding failures must be isolated (must not stall or crash the worker pipeline)

Include (at minimum):
- Goal / Non-goals
- Interfaces (input/output URLs), configuration knobs and defaults
- Lifecycle (start/stop), retry/backoff, restart limits, and failure modes
- Observability (logs + metrics fields and what they mean)
- Acceptance criteria
PROMPT
)"

prompt_013="$(cat <<PROMPT
/prompts:speckit.specify

${common_constraints}

Target spec file: \`specs/013-configuration-and-defaults.md\`
Only create/update \`specs/013-configuration-and-defaults.md\`. Do not touch any other file.

Task:
Write a single source of truth spec for configuration and defaults across:
- MediaMTX
- \`stream-orchestration\`
- \`stream-worker\`
- egress forwarder

Include (at minimum):
- Full set of env vars/flags per component (name, type, default, required/optional)
- Recommended dev defaults (including worker buffering=10s, grace period=30s)
- Minimal required config to run locally (no recording, unauth dev)
- Validation rules (what happens on invalid/missing config)
- Observability impact (what config affects logging/metrics)
- Acceptance criteria
PROMPT
)"

prompt_014="$(cat <<PROMPT
/prompts:speckit.specify

${common_constraints}

Target spec file: \`specs/014-asset-store-and-run-bundles.md\`
Only create/update \`specs/014-asset-store-and-run-bundles.md\`. Do not touch any other file.

Task:
Write a spec that reconciles STS pipeline asset expectations with observability:
- Default is metadata-only capture; media capture is opt-in
- Define filesystem layout conventions for run bundles and per-run manifests
- Manifest schema MUST be JSON (include an example)
- Partial/corrupt asset behavior: temp file + atomic rename; delete partials; cleanup on start
- Correlation: \`streamId\`, \`runId\` (stream-session), and per-process \`instanceId\`

Include (at minimum):
- Goal / Non-goals
- Directory layout (paths) and naming conventions
- Manifest schema (required fields) + example manifest JSON
- Retention/purge rules (even if simple for v0)
- Observability fields emitted when writing assets/manifests
- Acceptance criteria
PROMPT
)"

run_one "specs/012-egress-forwarder.md" "$prompt_012"
run_one "specs/013-configuration-and-defaults.md" "$prompt_013"
run_one "specs/014-asset-store-and-run-bundles.md" "$prompt_014"
