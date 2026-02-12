<!--
  SYNC IMPACT REPORT
  ==================
  Version change: N/A → v1.0.0 (initial creation)

  Modified Principles: N/A (initial creation)

  Added Sections:
  - Project Identity
  - Core Principles (5 principles)
  - Architecture Guidelines
  - Quality Standards
  - Governance

  Removed Sections: N/A (initial creation)

  Templates requiring updates:
  - .specify/templates/plan-template.md: ✅ compatible (Constitution Check section exists)
  - .specify/templates/spec-template.md: ✅ compatible (requirements/scenarios structure aligns)
  - .specify/templates/tasks-template.md: ✅ compatible (phase structure supports principles)

  Follow-up TODOs: None
-->

# Project Constitution

**Project Name**: speckit-wiggum-toolkit
**Version**: v1.0.0
**Ratification Date**: 2025-01-28
**Last Amended Date**: 2025-01-28

## Project Identity

### Mission

Build a robust AI development toolkit that combines specification-driven development
(spec-kit) with automated workflow orchestration (ralph-wiggum) to enable consistent,
high-quality project scaffolding for TypeScript/Node.js projects.

### Scope

This toolkit provides:
- CLI-based project scaffolding from templates
- Specification writing and management workflows
- Task generation and implementation planning
- Multi-agent orchestration for AI-assisted development
- Progress tracking and milestone management

### Target Users

- Software engineers bootstrapping new TypeScript/Node.js projects
- Teams adopting specification-driven development practices
- AI-assisted development workflows using Claude or similar agents

## Core Principles

### Principle 1: Specification First

All features MUST be fully specified before implementation begins.

**Rules**:
- Every feature MUST have a `spec.md` documenting user scenarios and requirements
- Implementation planning (`plan.md`) MUST NOT begin until spec is complete
- Task generation (`tasks.md`) MUST derive from approved specifications
- Changes to implementation MUST trace back to specification changes

**Rationale**: Specifications prevent scope creep, ensure alignment between stakeholders,
and provide the foundation for testable acceptance criteria. AI agents perform better
with clear, complete requirements.

### Principle 2: Simplicity Over Cleverness

Prefer straightforward solutions over sophisticated abstractions.

**Rules**:
- MUST NOT introduce abstractions until the third concrete use case (Rule of Three)
- MUST NOT add configurability for hypothetical future requirements
- MUST NOT use design patterns unless they solve a present problem
- Code MUST be readable by developers unfamiliar with the codebase

**Rationale**: AI development toolkits are used across diverse projects. Complexity in
the toolkit propagates to every project it scaffolds. Simple, predictable behavior
enables reliable automation.

### Principle 3: Explicit Over Implicit

All behavior, configuration, and dependencies MUST be clearly visible and documented.

**Rules**:
- Templates MUST contain placeholders that are self-documenting
- Default values MUST be stated explicitly, not assumed
- File paths and naming conventions MUST follow documented patterns
- Error messages MUST explain what went wrong and suggest resolution

**Rationale**: AI agents and human developers both benefit from explicit context.
Implicit behavior leads to confusion, debugging difficulty, and inconsistent outcomes
across different environments.

### Principle 4: Incremental Delivery

Features MUST be deliverable in independently testable increments.

**Rules**:
- User stories MUST be independently implementable and testable
- Each task phase MUST produce a verifiable checkpoint
- Features MUST NOT require other incomplete features to function
- MVP (Minimum Viable Product) MUST be achievable from the first user story

**Rationale**: Incremental delivery enables progress verification, reduces risk of
large failed investments, and allows early feedback. AI agents work more effectively
on bounded, completable units of work.

### Principle 5: Traceability and Auditability

All artifacts MUST maintain clear lineage to their sources.

**Rules**:
- Tasks MUST reference their source user story (US1, US2, etc.)
- Implementation files MUST trace to task IDs
- Changes MUST be tracked through version control with descriptive commits
- Progress MUST be tracked and reportable at any point

**Rationale**: Development workflows involving AI agents require auditability to verify
work quality, understand decision history, and enable effective handoffs between human
and AI collaborators.

## Architecture Guidelines

### Project Structure

```text
src/
├── cli/          # Command-line interface entry points
├── lib/          # Core library functions
├── models/       # Data structures and types
└── services/     # Business logic and orchestration

tests/
├── unit/         # Unit tests for individual functions
├── integration/  # Integration tests for workflows
└── contract/     # Contract tests for external interfaces
```

### Dependency Constraints

- External dependencies MUST be declared in `package.json` with pinned major versions
- New dependencies MUST NOT duplicate functionality of existing dependencies
- CLI dependencies (commander, inquirer, chalk) MUST remain minimal
- Development dependencies MUST NOT be required at runtime

### Technology Stack

- **Language**: TypeScript 5.x (strict mode)
- **Runtime**: Node.js 20+
- **Testing**: Vitest
- **Linting**: ESLint with TypeScript parser
- **Build**: TypeScript compiler (tsc)

## Quality Standards

### Code Quality Gates

Before any feature is considered complete:

- [ ] All TypeScript compilation errors resolved (`npm run typecheck`)
- [ ] All linting rules pass (`npm run lint`)
- [ ] All existing tests pass (`npm run test`)
- [ ] New functionality has corresponding tests where specified

### Documentation Requirements

- Public functions MUST have JSDoc comments explaining purpose and parameters
- CLI commands MUST have `--help` documentation
- Breaking changes MUST be documented in release notes

### Commit Standards

Commits MUST follow conventional commit format:
- `feat:` for new features
- `fix:` for bug fixes
- `docs:` for documentation changes
- `refactor:` for code restructuring without behavior change
- `test:` for test additions or modifications

## Governance

### Amendment Procedure

1. Propose changes via discussion with project maintainers
2. Draft amendment with clear rationale and impact assessment
3. Update constitution version according to semantic versioning:
   - **MAJOR**: Principle removals or incompatible governance changes
   - **MINOR**: New principles or substantial guidance additions
   - **PATCH**: Clarifications, typo fixes, non-semantic refinements
4. Update `Last Amended Date` to reflect change date
5. Propagate changes to dependent templates via Sync Impact Report

### Compliance Review

- All implementation plans MUST pass Constitution Check before proceeding
- Violations MUST be justified in the Complexity Tracking section of `plan.md`
- Repeated violations indicate the constitution may need amendment

### Template Synchronization

When the constitution changes, the following templates MUST be reviewed:
- `.specify/templates/plan-template.md` - Constitution Check alignment
- `.specify/templates/spec-template.md` - Requirements structure
- `.specify/templates/tasks-template.md` - Task categorization
- `.specify/templates/milestone-template.md` - Milestone criteria
- `.specify/templates/progress-template.md` - Progress tracking fields

---

*This constitution establishes the foundational principles and governance for the
speckit-wiggum-toolkit project. All contributors and AI agents operating within
this project MUST adhere to these guidelines.*
