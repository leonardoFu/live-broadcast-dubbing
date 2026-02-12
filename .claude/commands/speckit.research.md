---
description: Technical research using Context7 and Claude knowledge to resolve unknowns before implementation planning.
handoffs:
  - label: Build Technical Plan
    agent: speckit.plan
    prompt: Create a plan based on this research
    send: true
---

## User Input

```text
$ARGUMENTS
```

You **MUST** consider the user input before proceeding (if not empty).

## Goal

Conduct technical research before implementation planning. Resolve all NEEDS CLARIFICATION items, validate technology choices, and document findings in a reusable research cache.

## Execution Steps

### 1. Setup

Run `.specify/scripts/bash/setup-plan.sh --json` from repo root **once** and parse JSON for:
- `FEATURE_SPEC`: Path to spec.md
- `IMPL_PLAN`: Path to plan.md
- `SPECS_DIR`: Feature directory (FEATURE_DIR)
- `BRANCH`: Current branch name

Output file: `research.md` in SPECS_DIR.

For single quotes in args like "I'm Groot", use escape syntax: e.g 'I'\''m Groot' (or double-quote if possible: "I'm Groot").

### 2. Explore Codebase for Current Status

Before researching external technologies, understand the existing codebase context:

**Discovery Tasks** (use Glob, Grep, and Read tools):
- **Project structure**: Identify key directories, entry points, and module organization
- **Existing patterns**: Find similar features already implemented that can serve as reference
- **Tech stack in use**: Detect current libraries, frameworks, and versions from package.json/requirements.txt/go.mod etc.
- **Integration points**: Locate existing API clients, database connections, external service integrations
- **Testing patterns**: Identify test structure, mocking strategies, and coverage expectations

**Document findings**:
- Current architecture relevant to this feature
- Existing code that will be modified or extended
- Patterns to follow for consistency
- Potential conflicts or dependencies

### 3. Analyze Libraries/APIs & Identify Risks

Evaluate each library and API the feature will use:

**For each library/API, assess**:
- **Version compatibility**: Does it work with existing dependencies?
- **Maturity & maintenance**: Is it actively maintained? Last release date?
- **Documentation quality**: Are docs comprehensive? Examples available?
- **Community adoption**: Usage statistics, GitHub stars, npm downloads
- **Known issues**: Open bugs, security vulnerabilities, deprecation warnings

**Risk Categories**:

| Risk Level | Criteria | Action |
|------------|----------|--------|
| 🔴 HIGH | Unmaintained, security issues, breaking changes planned | Find alternative or document mitigation |
| 🟡 MEDIUM | Limited docs, small community, complex API | Research thoroughly, prepare fallbacks |
| 🟢 LOW | Well-documented, widely adopted, stable | Proceed with standard research |

**Ambiguity Flags** - Document any of these:
- Unclear API behavior for edge cases
- Multiple ways to achieve same goal (which is canonical?)
- Version-specific features or breaking changes
- Missing TypeScript types or incomplete type definitions
- Conflicting documentation across sources

### 4. Solution Analysis & Recommendation

Evaluate potential solutions before committing to an approach:

**Solution Evaluation Framework**:

For each viable approach, analyze:

| Criteria | Weight | Approach A | Approach B | Approach C |
|----------|--------|------------|------------|------------|
| Complexity | 20% | [1-5 score] | [1-5 score] | [1-5 score] |
| Maintainability | 25% | [1-5 score] | [1-5 score] | [1-5 score] |
| Performance | 20% | [1-5 score] | [1-5 score] | [1-5 score] |
| Codebase Fit | 25% | [1-5 score] | [1-5 score] | [1-5 score] |
| Risk Level | 10% | [1-5 score] | [1-5 score] | [1-5 score] |

**Key Questions to Answer**:
- Does this solution align with existing codebase patterns?
- What's the simplest implementation that meets requirements?
- What are the trade-offs we're accepting?
- What would make us revisit this decision?

**Recommendation Format**:
```
RECOMMENDED: [Approach Name]
RATIONALE: [2-3 sentences explaining why]
TRADE-OFFS: [What we're giving up]
ALTERNATIVES: [Brief note on why others were rejected]
```

### 5. Analyze Research Requirements

Load `FEATURE_SPEC` and extract:
- **Technologies mentioned**: Libraries, frameworks, tools referenced in spec
- **Integration points**: External services, APIs, databases
- **Architectural decisions**: Patterns needing validation (caching, queuing, etc.)
- **Unknowns**: Any TBD, TODO, questions, or NEEDS CLARIFICATION markers

### 6. Research Strategy

Apply the appropriate research strategy based on topic type:

| Topic Type | Strategy | Tools |
|------------|----------|-------|
| Library/Framework API | Context7 ONLY | `mcp__context7__resolve-library-id`, `mcp__context7__query-docs` |
| Best practices | Claude Knowledge | Direct synthesis from training data |
| Tech comparison | Context7 + Claude | Both approaches combined |
| Latest trends (2025+) | WebSearch | For current information |
| Implementation examples | Context7 | Code snippets from official docs |

### 7. Execute Research

**Context7 Research** (max 3 calls per library):

1. First resolve the library ID:
   ```
   mcp__context7__resolve-library-id(libraryName: "<library>", query: "<what you need>")
   ```

2. Then query the documentation:
   ```
   mcp__context7__query-docs(libraryId: "<resolved-id>", query: "<specific question>")
   ```

**CRITICAL**: Preserve Context7 code snippets **verbatim**. Do not paraphrase or modify example code.

**Claude Knowledge**: Use for industry best practices, common pitfalls, architectural patterns, and design decisions where official documentation is not required.

**WebSearch** (when needed): Use query format `<technology> best practices 2025` for current information.

### 8. Structure Output

Create/update `research.md` in SPECS_DIR with this structure:

```markdown
# Technical Research: [Feature Name]

## Executive Summary
[2-3 sentences summarizing key findings and recommendations]

## Codebase Analysis

### Current State
[Summary of existing architecture relevant to this feature]

### Existing Patterns to Follow
[List of patterns, conventions, and code references to maintain consistency]

### Files to Modify/Extend
| File | Purpose | Changes Needed |
|------|---------|----------------|
| [path] | [what it does] | [what needs to change] |

### Dependencies & Conflicts
[Any existing code that may conflict or require coordination]

## Libraries & APIs Assessment

### [Library/API Name]
- **Version**: [current/required]
- **Risk Level**: 🟢/🟡/🔴
- **Maintenance Status**: [active/maintenance mode/deprecated]
- **Last Release**: [date]

#### Compatibility Notes
[Version compatibility with existing stack]

#### Known Issues
[Relevant bugs, limitations, or gotchas]

#### Ambiguities Identified
[Unclear aspects that need resolution]

## Solution Recommendation

### Recommended Approach
[Name and brief description]

### Rationale
[Why this approach was chosen]

### Trade-offs Accepted
[What we're giving up with this choice]

### Alternatives Considered
| Alternative | Pros | Cons | Why Rejected |
|-------------|------|------|--------------|
| [approach] | [benefits] | [drawbacks] | [reason] |

### Risk Mitigation
[How we'll handle identified risks]

## Technologies Researched

### [Technology Name]

#### Quick Setup (Context7 Verified)
[Complete working examples from official docs - preserve verbatim]

#### Key Configurations
[Important configuration options and their defaults]

#### Integration Patterns
[How to integrate with other components in the stack]

#### Common Issues & Solutions
[Known pitfalls and their resolutions]

#### Best Practices (Claude Synthesis)
[Industry best practices and recommendations]

#### Source Attribution
- Context7 Library ID: [id]
- Topics queried: [list]
- Snippet count: [n]

## Decision Matrix

| Decision | Choice | Rationale | Alternatives Considered |
|----------|--------|-----------|------------------------|
| [decision point] | [chosen option] | [why] | [other options evaluated] |

## Resolved Clarifications

| Original Unknown | Resolution | Source |
|------------------|------------|--------|
| [TBD/TODO item] | [answer] | [Context7/Claude/WebSearch] |

## Next Steps
- [ ] Run `/speckit.plan` to create implementation plan
```

### 9. Completion Report

After saving `research.md`, report:
- **Research file**: Absolute path to research.md
- **Feature spec**: Path to spec.md
- **Branch**: Current branch name
- **Codebase exploration**: Files analyzed, patterns identified, existing code to extend
- **Libraries assessed**: List with risk levels (🟢/🟡/🔴) and any ambiguities found
- **Recommended solution**: Brief summary of chosen approach and key trade-offs
- **Technologies researched**: List with Context7 IDs, topics, and snippet counts
- **Decisions made**: Summary of key choices with rationale
- **Sources used**: Count of Context7 libraries, web searches, Claude synthesis items
- **Confidence level**: HIGH (all unknowns resolved), MEDIUM (some deferred), or LOW (significant gaps)
- **Suggested next command**: `/speckit.plan`

## Operating Rules

- **Preserve Context7 code verbatim**: Never paraphrase or modify code examples from documentation
- **Always attribute sources**: Every finding must indicate whether it came from Context7, Claude knowledge, or web search
- **Focus on actionable content**: Document practical guidance, not summaries
- **Cache is additive**: If research.md exists, append new findings rather than overwriting
- **Max 3 Context7 queries per library**: Be efficient with API calls
- **Resolve all unknowns**: Every NEEDS CLARIFICATION, TBD, or TODO should have a resolution or explicit deferral reason
