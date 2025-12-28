# Workflow State Directory

This directory contains workflow state files for orchestrator observability and recovery.

## File Format

Each workflow creates a state file: `<workflow-id>.json`

## Contents

- Workflow metadata (id, type, start time)
- Agent execution logs
- Results from each agent
- Error information
- Pre-flight check results

## Usage

- Files are created automatically by the orchestrator
- Can be used to resume interrupted workflows
- Useful for debugging and observability

## Cleanup

Old state files can be safely deleted after workflows complete.

