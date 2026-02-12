# Third-Party Bug Investigation

## Overview

When a bug traces to a 3rd-party library or the boundary between your code and a dependency, you can't just "fix at the source" — you don't own the source. But the systematic process still applies. The root cause still exists; it's just in a different place.

**Core principle:** Determine whether the bug is in YOUR usage or in THE LIBRARY before choosing a fix strategy. The wrong diagnosis leads to fragile workarounds around code that was actually correct, or wasted time debugging your code when the library is broken.

## The Boundary Question

Every 3rd-party bug investigation starts here:

```
Is the bug in MY code, in THE LIBRARY, or at THE BOUNDARY?

MY CODE:       I'm calling the API wrong, missing config, wrong version combo
THE BOUNDARY:  Undocumented behavior, edge case, version incompatibility
THE LIBRARY:   Actual bug in the dependency's code
```

You MUST answer this before choosing a fix strategy.

## Research Tools

Use these tools to investigate 3rd-party issues. Each serves a different purpose:

### Context7 — Library Documentation

**Purpose:** Read the library's actual documentation for correct API usage, configuration, and known behavior.

```
# Step 1: Resolve the library ID
mcp__context7__resolve-library-id(libraryName: "<library>", query: "<what you need>")

# Step 2: Query specific documentation
mcp__context7__query-docs(libraryId: "<resolved-id>", query: "<specific question>")
```

**Use for:**
- Verifying your API usage matches documentation
- Checking configuration options you may have missed
- Finding migration guides between versions
- Understanding expected behavior vs what you're seeing

**Max 3 queries per library.** Be specific:
- BAD: "how does axios work"
- GOOD: "axios interceptor error handling retry behavior"

### WebSearch — Known Issues and Community Solutions

**Purpose:** Find whether others have encountered the same issue, upstream bug reports, and community workarounds.

**Search patterns:**
```
"<library> <version> <error message>"
"<library> <symptom> site:github.com/issues"
"<library> <symptom> site:stackoverflow.com"
"<library> breaking changes <from-version> <to-version>"
"<library> changelog <version>"
```

**Use for:**
- Finding upstream bug reports (GitHub issues)
- Discovering known breaking changes
- Finding community workarounds with context on WHY they work
- Checking if the issue is fixed in a newer version

### WebFetch — Specific Pages

**Purpose:** Read specific upstream issue threads, changelogs, or documentation pages found via WebSearch.

**Use for:**
- Reading full GitHub issue threads (context on root cause and resolution)
- Reading detailed changelogs between versions
- Reading migration guides
- Reading the library's actual source code on GitHub (specific files)

## Phase 1: Root Cause Investigation (3rd-Party Extension)

After standard Phase 1 steps (read errors, reproduce, check recent changes), add:

### 1. Check Dependency Changes

```bash
# What changed in the lockfile since last known good state?
git diff <last-good-commit> -- package-lock.json yarn.lock pnpm-lock.yaml

# What version are we actually running?
npm ls <library>           # or yarn why, pnpm why
npm ls <library> --all     # Check for duplicate/conflicting versions

# Are there peer dependency warnings?
npm install 2>&1 | grep -i "peer\|WARN"
```

**Key questions:**
- Did this dependency version change recently?
- Are there multiple versions installed (version conflict)?
- Are peer dependency requirements satisfied?

### 2. Search for Known Issues

Use WebSearch to check if this is a known problem:

```
Search: "<library-name> <version> <error-message-or-symptom>"
Search: "<library-name> <error-code> github issue"
```

If you find a matching upstream issue:
- Use WebFetch to read the full thread
- Note whether it's confirmed, has a fix, or has workarounds
- Check which versions are affected

### 3. Verify Your API Usage

Use Context7 to read the library's documentation:

```
mcp__context7__resolve-library-id(libraryName: "<library>")
mcp__context7__query-docs(libraryId: "<id>", query: "<the specific API or feature>")
```

Compare your actual usage against the documented API:
- Are you passing the right types?
- Are you handling async correctly (promises, callbacks)?
- Are there required options you're not setting?
- Has the API changed between versions?

### 4. Create Minimal Reproduction

**This is the single most important step for 3rd-party bugs.**

Create a minimal project that ONLY uses the dependency:

```bash
mkdir /tmp/repro-<library>-bug && cd /tmp/repro-<library>-bug
npm init -y
npm install <library>@<your-version>
```

Write the smallest possible script that triggers the bug:

```javascript
// repro.js - minimal reproduction
const lib = require('<library>');
// Bare minimum code to trigger the issue
// No framework, no other dependencies, no config
```

**Outcome determines the diagnosis:**
- **Reproduces in minimal project** → Library bug or fundamental misuse
- **Does NOT reproduce** → Integration issue (your config, other deps, environment)

## Phase 2: Pattern Analysis (3rd-Party Extension)

### 1. Version Bisection

If the bug appeared after a dependency update:

```bash
# Pin to previous version and test
npm install <library>@<previous-version>
npm test

# If that works, check the changelog between versions
# Use WebFetch to read the changelog
```

Binary search across versions if needed:
```
Known good: 2.1.0
Known bad:  2.4.0
Test:       2.2.0 → good? test 2.3.0 → bad? Bug introduced in 2.3.0
```

Then read the changelog for that specific version to find what changed.

### 2. Read the Library Source

When documentation doesn't explain the behavior:

```
# Use WebFetch to read the specific source file on GitHub
WebFetch: "https://github.com/<org>/<repo>/blob/<tag>/src/<relevant-file>"
```

**Look for:**
- Default values you didn't expect
- Validation that rejects your input
- Conditional behavior based on environment
- Internal state that could conflict with your usage

### 3. Compare Against Library's Own Tests

The library's test suite shows intended usage:

```
WebFetch: "https://github.com/<org>/<repo>/tree/<tag>/test"
```

Find tests for the feature you're using. How do they set up and call the API?

## Phase 3: Hypothesis Testing (3rd-Party Extension)

### Hypothesis Categories

Frame your hypothesis specifically:

| Category | Example Hypothesis |
|----------|-------------------|
| **Wrong usage** | "I'm passing options in the wrong format — docs say X, I'm doing Y" |
| **Version mismatch** | "This API changed in v3.0 and I'm still using v2 patterns" |
| **Environment** | "The library behaves differently in test/CI because of NODE_ENV" |
| **Interaction** | "Library X and library Y conflict when both loaded" |
| **Upstream bug** | "This is a confirmed bug in v2.3.0, fixed in v2.3.1" |

### Testing Upstream Bug Hypothesis

If you suspect a library bug:

1. Check if your minimal repro (from Phase 1.4) confirms it
2. Test against latest version: `npm install <library>@latest`
3. Test against a known-good version: `npm install <library>@<old-version>`
4. Search upstream issues for confirmation

**Only conclude "upstream bug" when you have evidence from at least two of these.**

## Phase 4: Implementation (3rd-Party Fix Strategy)

Once root cause is confirmed, choose the appropriate fix strategy:

### Decision Tree

```
Root cause identified
├── Bug in YOUR code (wrong usage)
│   └── Fix your code normally (standard Phase 4)
│
├── Bug at THE BOUNDARY (edge case, undocumented behavior)
│   ├── Can you adjust your usage to avoid it?
│   │   └── YES → Adjust usage + add comment explaining why
│   │   └── NO → Wrap with defensive adapter (see below)
│   │
├── Bug in THE LIBRARY
│   ├── Is the library actively maintained?
│   │   ├── YES → Is there a newer version with the fix?
│   │   │   ├── YES → Upgrade + verify
│   │   │   └── NO → File issue + workaround (see below)
│   │   └── NO → Evaluate alternatives (see below)
│   │
└── Version incompatibility
    ├── Can you upgrade/downgrade to compatible version?
    │   └── YES → Pin version + document why
    │   └── NO → Adapter pattern (see below)
```

### Fix Patterns

#### 1. Adjust Usage (bug is in your code)
Standard Phase 4 — fix your code, write tests, verify.

#### 2. Pin Version
```json
// package.json - pin to last-known-good
"dependencies": {
  "library": "2.2.0"  // Pinned: v2.3.0 breaks X (see #123)
}
```
**Always add a comment or `// TODO` with the upstream issue link.**

#### 3. Defensive Adapter
Wrap the library call to handle the edge case:

```typescript
// adapters/library-name.ts
// Workaround for <library> issue #123: <brief description>
// Remove when fixed upstream: <link to issue>
export function safeLibraryCall(input: Input): Output {
  // Normalize input to avoid triggering the bug
  const sanitized = workaroundForBug(input);
  return library.call(sanitized);
}
```

**Requirements:**
- Isolate the workaround in one place (not scattered)
- Link to upstream issue
- Document when it can be removed
- Test both the workaround AND the original behavior

#### 4. Upstream Contribution
If you've identified the root cause in the library:

1. File an issue with your minimal reproduction
2. If you can fix it, submit a PR
3. Use your workaround locally until the fix is released
4. Set a reminder to remove the workaround after the fix ships

#### 5. Replace the Dependency
**Only when:**
- Library is unmaintained (no commits in 6+ months, issues ignored)
- Bug is fundamental (not an edge case)
- Alternative exists with comparable API

**Before replacing:**
- Map all usage points in your codebase
- Verify the alternative doesn't have the same issue
- Consider maintenance cost of the switch

## Anti-Patterns

| Anti-Pattern | Why It's Wrong | Instead |
|-------------|---------------|---------|
| Blindly upgrade to latest | May introduce new breaking changes | Test in minimal repro first |
| Copy-paste StackOverflow workaround | Don't understand WHY it works | Read the upstream issue, understand root cause |
| Wrap everything in try-catch | Hides the bug, doesn't fix it | Fix or workaround the specific issue |
| "It works on my machine" | Different versions, env, config | Reproduce in clean environment |
| Downgrade without pinning | Next `npm install` may upgrade again | Pin explicitly + document why |
| Scattered workarounds | Each caller handles the bug differently | Single adapter in one place |

## Documenting 3rd-Party Workarounds

Every workaround for a 3rd-party bug MUST include:

```typescript
/**
 * Workaround: <one-line description>
 * Library: <name>@<version>
 * Issue: <link to upstream issue>
 * Remove when: <condition — e.g., "library releases fix for #123">
 */
```

This prevents workarounds from becoming permanent, unexplained code.
