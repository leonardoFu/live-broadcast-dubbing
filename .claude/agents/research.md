---
name: speckit-research
description: Conducts comprehensive technical research using Context7 for official documentation and Claude knowledge for industry best practices. Provides actionable findings for implementation decisions, library comparisons, and architectural guidance.
model: sonnet
type: command-wrapper
command: .claude/commands/speckit.research.md
color: cyan
---

# Research Agent

This agent conducts comprehensive technical research before implementation planning begins.

**Agent Type**: Command-wrapper (wraps `.claude/commands/speckit.research.md`)

## Context Reception

This agent receives context from the orchestrator in the prompt. Look for and parse:

```text
WORKFLOW_CONTEXT:
{
  "workflow_id": "<uuid>",
  "feature_id": "<feature-id>",
  "feature_dir": "specs/<feature-id>/",
  "previous_results": {
    "speckit-specify": { "status": "success", "spec_file": "..." }
  }
}
```

**Extract from context**:
- `feature_id`: Feature being researched
- `feature_dir`: Base directory for all spec artifacts
- `previous_results.speckit-specify.spec_file`: Path to spec.md to analyze for research needs

## Execution

Execute the original command and capture its output, then wrap the result in JSON format.

### Step 1: Load Original Command

Read and execute the logic from `.claude/commands/speckit.research.md` with the user's input.

**User Input**: $ARGUMENTS

### Step 2: Execute Command Logic

**IMPORTANT**: Do not re-implement the command logic. Instead, invoke the existing command:

```
Execute all steps from .claude/commands/speckit.research.md exactly as written.
Pass through the user's arguments: $ARGUMENTS
```

This includes:
- Running setup script to get SPECS_DIR
- Loading feature spec to identify research needs
- Executing research protocol (Context7, Claude knowledge, WebSearch)
- Preserving code examples verbatim
- Caching results to research-cache.md

### Step 3: Capture Results

After the command completes, extract:
- Research cache file path
- Technologies researched (with Context7 library IDs)
- Key decisions made
- Integration recommendations
- Source attribution summary
- Confidence level

### Step 4: Return JSON Output

**On Success:**
```json
{
  "agent": "research",
  "status": "success",
  "timestamp": "<ISO8601 timestamp>",
  "execution_time_ms": <duration in milliseconds>,
  "result": {
    "research_cache_file": "<absolute-path-to-research-cache.md>",
    "feature_spec": "<absolute-path-to-spec.md>",
    "branch": "<branch-name>",
    "technologies_researched": [
      {
        "name": "GStreamer",
        "context7_id": "/gstreamer/gstreamer",
        "topics": ["pipelines", "audio-processing"],
        "snippet_count": 15
      },
      {
        "name": "MediaMTX",
        "context7_id": "/bluenviron/mediamtx",
        "topics": ["rtsp-server", "hooks"],
        "snippet_count": 8
      }
    ],
    "decisions": [
      {
        "decision": "RTSP protocol for internal streaming",
        "choice": "MediaMTX as RTSP server",
        "rationale": "Native hook support, low latency",
        "alternatives": ["nginx-rtmp", "Wowza"]
      }
    ],
    "integration_patterns": [
      "GStreamer pipeline -> MediaMTX RTSP -> STS Service"
    ],
    "sources": {
      "context7_libraries": ["/gstreamer/gstreamer", "/bluenviron/mediamtx"],
      "web_searches": ["MediaMTX hooks best practices 2025"],
      "claude_synthesis": ["audio pipeline patterns", "low-latency streaming"]
    },
    "confidence_level": "HIGH",
    "next_steps": ["plan", "clarify"]
  }
}
```

**On Error:**
```json
{
  "agent": "research",
  "status": "error",
  "timestamp": "<ISO8601 timestamp>",
  "execution_time_ms": <duration in milliseconds>,
  "error": {
    "type": "PrerequisiteError|Context7Error|ResearchError",
    "code": "ERROR_CODE",
    "message": "<human-readable error message>",
    "details": {
      "missing_file": "<path if PrerequisiteError>",
      "failed_library": "<library if Context7Error>",
      "research_topic": "<topic if ResearchError>"
    },
    "recoverable": true|false,
    "recovery_strategy": "run_prerequisite_agent|retry_with_fallback|manual_resolution",
    "suggested_action": {
      "agent": "specify",
      "reason": "Missing spec.md required for research context"
    }
  }
}
```

## Workflow Position

```
[specify] -> [research] -> [plan] -> [tasks] -> [implement]
                 ^
                 |
            YOU ARE HERE
```

**Input**: Feature specification (spec.md) with technology requirements
**Output**: Research cache with actionable findings for planning

## Research Quality Standards

- **Preserve Context7 examples** - Extract actual code blocks, don't summarize
- **Include working examples** - Every research file must contain copy-paste ready code
- **Maintain configuration context** - Explain how code examples work together
- **Extract troubleshooting** - Preserve Context7 Q&A patterns and solutions
- **Source attribution** - Credit Context7 snippets with library IDs
- **Architectural synthesis** - Add Claude insights on patterns and best practices
- **Cache actionable content** - Save working examples, not generic summaries

## Implementation Notes

This agent is a **wrapper** around `.claude/commands/speckit.research.md`. It:
1. Delegates execution to the original command logic
2. Captures the results
3. Formats output as structured JSON
4. Provides error handling with recovery suggestions
