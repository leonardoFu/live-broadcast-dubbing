---
description: Conduct comprehensive technical research using Context7 for official documentation and Claude knowledge for best practices.
handoffs:
  - label: Create Plan
    agent: speckit.plan
    prompt: Use research findings to create implementation plan
    send: true
  - label: Update Spec
    agent: speckit.specify
    prompt: Update spec with research findings
---

## User Input

```text
$ARGUMENTS
```

You **MUST** consider the user input before proceeding (if not empty).

## Outline

1. **Setup**: Run `.specify/scripts/bash/setup-plan.sh --json` from repo root and parse JSON for FEATURE_SPEC, SPECS_DIR, BRANCH. Output file will be `research-cache.md` in SPECS_DIR.

2. **Load Context**: Read FEATURE_SPEC (spec.md) to understand feature requirements and technology needs.

3. **Execute Research Protocol**: Follow the research workflow below.

4. **Cache Results**: Save research findings to `research-cache.md` in SPECS_DIR.

5. **Report**: Output summary and next steps.

## Research Protocol

### Step 1: Analyze Research Requirements

Extract from the feature spec:
- **Technologies mentioned**: Libraries, frameworks, tools referenced
- **Integration points**: External services, APIs, protocols
- **Architectural decisions**: Patterns, structures needing validation
- **Unknowns**: Areas marked as "TBD", "TODO", or questions

### Step 2: Determine Research Strategy

Use this decision matrix for each research topic:

| Topic Type | Strategy | Tools |
|------------|----------|-------|
| Library/Framework API | Context7 ONLY | `mcp__plugin_context7_context7__resolve-library-id`, `mcp__plugin_context7_context7__query-docs` |
| Best practices, patterns | Claude Knowledge | Direct knowledge synthesis |
| Technology comparison | Context7 + Claude | Both for comprehensive view |
| Latest trends (2025) | WebSearch | `WebSearch` for recent developments |
| Implementation examples | Context7 | Code snippets from official docs |
| Conceptual/architectural | Context7 | Guides and architectural docs |

### Step 3: Execute Research

For each research topic:

1. **Context7 Research** (for libraries/frameworks):
   ```
   mcp__plugin_context7_context7__resolve-library-id(libraryName: "<library>", query: "<what you need>")
   mcp__plugin_context7_context7__query-docs(
     libraryId: "<resolved-id>",
     query: "<specific-topic>"
   )
   ```

   **CRITICAL**: Preserve Context7 code snippets exactly - do not summarize working examples.

2. **Claude Knowledge Synthesis**:
   - Industry best practices
   - Common pitfalls and solutions
   - Architectural patterns
   - Integration recommendations

3. **WebSearch** (when needed for latest info):
   ```
   WebSearch(query: "<technology> best practices 2025")
   ```

### Step 4: Extract and Structure Findings

For each technology researched, capture:

```markdown
## [Technology Name]

### Quick Setup (Context7 Verified)
```[language]
[Complete, working code examples from Context7]
```

### Key Configurations
- **Configuration 1**: [Purpose and code]
- **Configuration 2**: [Purpose and code]

### Integration Patterns
[How this technology integrates with others in the stack]

### Common Issues & Solutions
- **Issue**: [From Context7 Q&A or known pitfalls]
  **Solution**: [Working fix with code]

### Best Practices (Claude Synthesis)
- [Practice 1 with rationale]
- [Practice 2 with rationale]

### Source Attribution
- Context7: [library-id] - [snippet count] snippets
- Claude Knowledge: [topics synthesized]
- WebSearch: [queries if used]
```

## Output Format

Save to `research-cache.md` in SPECS_DIR:

```markdown
# Technical Research: [Feature Name]

**Generated**: [ISO8601 timestamp]
**Feature Spec**: [path to spec.md]
**Branch**: [branch name]

## Executive Summary

[2-3 sentences summarizing key findings and recommendations]

## Technologies Researched

### 1. [Technology A]
[Structured findings per Step 4]

### 2. [Technology B]
[Structured findings per Step 4]

## Integration Recommendations

[How the researched technologies work together]

## Decision Matrix

| Decision | Choice | Rationale | Alternatives Considered |
|----------|--------|-----------|------------------------|
| [Decision 1] | [Choice] | [Why] | [What else evaluated] |

## Research Metadata

- **Context7 Libraries**: [list with IDs]
- **WebSearch Queries**: [list if used]
- **Research Duration**: [time taken]
- **Confidence Level**: HIGH | MEDIUM | LOW
```

## Key Rules

- **Preserve Context7 code examples verbatim** - they are tested and working
- **Always attribute sources** - Context7 vs Claude Knowledge vs WebSearch
- **Focus on actionable content** - code snippets, configurations, not summaries
- **Cache is additive** - new research appends, doesn't overwrite
- **7-day freshness** - flag stale sections for refresh
