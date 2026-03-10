# Simulator Workflow Architecture

Autolab now supports typed, stage-based simulator workflows without giving agents raw shell access.

## Why typed specs instead of shell commands

- Agents reason about candidates, materials, geometry, parameters, and workflow structure.
- Adapters own binary invocation, workdir shape, template rendering, and output parsing.
- This keeps execution deterministic, auditable, and testable.

## Why adapters own artifact generation

- Scientific simulators depend on controlled input decks, Python drivers, launch scripts, manifests, logs, and parser summaries.
- Centralizing that logic inside adapters keeps prompts small and prevents path hacking or ad hoc subprocess use.
- Every stage workdir follows the same contract under `artifacts/runs/{campaign_id}/{experiment_id}/{stage_name}/`.

## Multi-stage workflows

- Campaigns can carry an optional typed `workflow`.
- Each stage declares its simulator, task, dependencies, and optional mapping identifier.
- Stage mapping functions are registered in code and transform parsed upstream outputs into downstream parameters.
- The campaign loop executes stages sequentially in the first phase and records:
  - stage execution records
  - simulator provenance rows
  - generated artifacts and manifests
  - final run-level metrics and validation summaries

## Verification across simulators

The workflow layer makes cross-simulator verification explicit:

- parameter echo verification
- artifact completeness verification
- provenance capture verification
- stage-to-stage mapping tolerance checks

This turns simulator transfer assumptions into something operators can inspect and test.
