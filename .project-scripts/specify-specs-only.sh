#!/usr/bin/env bash
set -euo pipefail

#
# Run Speckit "specify" in spec-only mode.
#
# Goals:
# - Use Codex CLI with "YOLO" approvals (no prompts)
# - Trigger `/prompts:speckit.specify`
# - Instruct Codex to ONLY create/update spec markdown files under `specs/`
# - No git/branching, no code changes, no docker/make commands, no checklist files
#
# Notes:
# - Codex CLI versions differ. Newer versions do NOT have `--yolo`; this script
#   uses `--dangerously-bypass-approvals-and-sandbox` as the equivalent.
#

repo_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"

usage() {
  cat <<'EOF'
Usage:
  ./.project-scripts/specify-specs-only.sh [--bundle] [--file <spec-path>] [--] [feature description...]

Examples:
  # Create the recommended missing specs bundle (012/013/014)
  ./.project-scripts/specify-specs-only.sh --bundle

  # Create/update one specific spec file
  ./.project-scripts/specify-specs-only.sh --file specs/012-egress-forwarder.md \
    "Define the egress forwarder that pulls live/<streamId>/out and pushes to 3rd-party RTMP"

Flags:
  --bundle            Generate the default spec bundle: 012/013/014
  --file <path>       Target a single spec file (must be under ./specs/)
  -h, --help          Show help

Behavior:
  Runs: `codex exec --dangerously-bypass-approvals-and-sandbox`
  Sends an initial message that starts with: `/prompts:speckit.specify ...`
  and explicitly instructs: "SPEC FILES ONLY; NO EXTRA OPERATIONS".
EOF
}

mode="bundle"
spec_file=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --bundle)
      mode="bundle"
      shift
      ;;
    --file)
      mode="single"
      spec_file="${2:-}"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    --)
      shift
      break
      ;;
    *)
      break
      ;;
  esac
done

feature_description="${*:-}"

if [[ "$mode" == "single" ]]; then
  if [[ -z "$spec_file" ]]; then
    echo "error: --file requires a path" >&2
    exit 2
  fi
  if [[ "$spec_file" != specs/* ]]; then
    echo "error: --file must be under ./specs/ (got: $spec_file)" >&2
    exit 2
  fi
  if [[ -z "$feature_description" ]]; then
    echo "error: missing feature description for --file $spec_file" >&2
    exit 2
  fi
fi

codex_yolo_flag=()
if codex --help 2>/dev/null | grep -q -- "--yolo"; then
  codex_yolo_flag=(--yolo)
else
  codex_yolo_flag=(--dangerously-bypass-approvals-and-sandbox)
fi

if [[ "$mode" == "bundle" ]]; then
  bundle_prompt="${SPECKIT_SPECIFY_BUNDLE_PROMPT:-}"
  if [[ -z "$bundle_prompt" ]]; then
    bundle_prompt="$(cat <<'PROMPT'
/prompts:speckit.specify

SPEC FILES ONLY — NO EXTRA OPERATIONS:
- Only create/update Markdown spec files under `specs/`.
- Do NOT run shell commands (no `git`, no `make`, no `docker`, no `curl`, no installs).
- Do NOT create branches, commits, or checklists. Do NOT write under `.specify/` or `.codex/`.
- Do NOT change any non-spec file (no `deploy/`, no `apps/`, no `Makefile`).

Task:
Create these new spec files (kebab-case, stable headings, concise sections, fenced code blocks for commands/pipelines):
1) `specs/012-egress-forwarder.md`
2) `specs/013-configuration-and-defaults.md`
3) `specs/014-asset-store-and-run-bundles.md`

The specs MUST align with the existing decisions already captured in this repo:
- Stream identity is path-based: `live/<streamId>/in` and `live/<streamId>/out`
- Orchestrator service name: `stream-orchestration` (HTTP hook receiver)
- One worker per stream; stop on not-ready after a grace period (default 30s)
- Worker: STS in-process, internal audio PCM S16LE @ 48kHz stereo, initial buffering target 10s, codec copy for video, backpressure stalls output and alerts
- Recording disabled in v0 (MediaMTX record: no)
- Dev access is unauthenticated ("everyone") and ops/security hardening is deferred
- Observability logs should be persisted to filesystem in dev; do not log frame-by-frame; log per-fragment operations and errors
- On cached asset partial/corruption: delete; write via temp file + atomic rename; keep same `runId` for now (and add `instanceId` per process)

For each new spec, include (at minimum):
- Goal / Non-goals
- Interfaces (URLs/paths), config knobs and defaults
- Failure handling + backoff policy
- Observability (logs + metrics fields)
- Acceptance criteria

`specs/012-egress-forwarder.md` specifics:
- Define the forwarder as a separate per-stream process managed by `stream-orchestration`
- Input: pull from `rtsp://mediamtx:8554/live/<streamId>/out` (codec copy)
- Output: push to 3rd-party RTMP destination (optional; can be disabled in dev)
- Clarify whether multi-destination is supported (start with single destination in v0; allow list later)
- Must not stall or crash the worker pipeline; forwarding failure is isolated

`specs/013-configuration-and-defaults.md` specifics:
- Define the full set of env vars/flags across: MediaMTX, stream-orchestration, stream-worker, egress-forwarder
- Include recommended dev defaults and a “minimal required to run locally” section

`specs/014-asset-store-and-run-bundles.md` specifics:
- Reconcile STS pipeline asset expectations with observability spec (default metadata-only; media capture opt-in)
- Define filesystem layout conventions for run bundles and a manifest schema (JSON)

Do not add code. Only add/update those spec markdown files.
PROMPT
)"
  fi

  printf '%s\n' "$bundle_prompt" | codex "${codex_yolo_flag[@]}" exec -C "$repo_root" -
else
  cat <<PROMPT | codex "${codex_yolo_flag[@]}" exec -C "$repo_root" -
/prompts:speckit.specify

SPEC FILES ONLY — NO EXTRA OPERATIONS:
- Only create/update Markdown spec files under \`specs/\`.
- Do NOT run shell commands (no \`git\`, no \`make\`, no \`docker\`, no \`curl\`, no installs).
- Do NOT create branches, commits, or checklists. Do NOT write under \`.specify/\` or \`.codex/\`.
- Do NOT change any non-spec file (no \`deploy/\`, no \`apps/\`, no \`Makefile\`).

Target spec file: \`$spec_file\`

Feature description:
$feature_description

Please create/update ONLY \`$spec_file\`, and do not touch any other files.
PROMPT
fi
