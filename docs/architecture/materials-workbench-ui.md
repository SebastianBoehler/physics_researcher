# Materials Workbench UI

This document defines the first product architecture for the future web dashboard in `apps/web`.

The goal is not a generic admin console. The goal is a workbench for autonomous materials research that exposes the existing campaign, run, artifact, benchmark, and skill primitives in a way that operators can trust.

## Product goal

Build a user-facing workbench with the same strengths as the backend:

- typed workflows
- inspectable provenance
- reproducible execution
- reusable skills

The workbench should make the system feel like a product in the same category as modern research operating systems, while staying honest about what the current backend actually does.

## Primary views

The v1 workbench should ship five views.

### Campaign Studio

Purpose:

- create and edit campaign definitions
- compose stage-based workflows visually
- validate parameters before execution

Key capabilities:

- workflow graph canvas
- stage templates by simulator kind
- objective and constraint editor
- budget and optimizer configuration
- campaign JSON preview

Primary backend mappings:

- `POST /campaigns`
- `POST /campaigns/{campaign_id}/start`
- `POST /campaigns/{campaign_id}/step`
- future endpoint for workflow templates and schema discovery

### Run Twin

Purpose:

- inspect what actually happened in a run
- follow a stage from spec to artifacts to parsed metrics

Key capabilities:

- stage timeline
- artifact browser
- manifest and environment viewer
- parsed summary and validation panel
- stage-to-stage mapping inspector

Primary backend mappings:

- `GET /runs/{run_id}`
- `GET /artifacts/{artifact_id}`
- future endpoint for artifact listing by run and stage

### Compare

Purpose:

- compare campaigns, runs, seeds, and optimizers
- identify meaningful scientific differences, not just status changes

Key capabilities:

- metric overlays
- seed comparison
- artifact diff summaries
- provenance diff summaries
- benchmark baseline comparison

Primary backend mappings:

- `GET /campaigns/{campaign_id}/runs`
- future comparison endpoint for normalized metric series

### Benchmark Hub

Purpose:

- publish benchmark suites and result summaries
- expose reproducibility and leaderboard-style comparisons

Key capabilities:

- benchmark catalog
- manifest viewer
- run history
- result tables
- baseline-versus-candidate views

Primary backend mappings:

- existing CLI benchmark flow through future benchmark API endpoints
- future endpoint for benchmark manifests and reports under `artifacts/benchmarks`

### Skill Catalog

Purpose:

- make the skill layer visible, searchable, and governable
- distinguish safe typed tools from planner-only guidance

Key capabilities:

- skill cards by domain
- filters by simulator, workflow family, and trust level
- input/output schema preview
- example prompts and example payloads
- source indicator:
  - native
  - imported
  - planner-only

Primary backend mappings:

- future endpoint for `SkillRegistry.list()`
- future endpoint for skill metadata and JSON schema

## Secondary views

These should follow after the primary views stabilize.

### Measurement Inbox

- ingest XRD and similar characterization results
- request human review for ambiguous parses
- link a measurement to upstream simulated candidates

### Review Room

- expose the existing review workflow surface
- coordinate agent and human discussion around runs and artifacts

### Literature Desk

- present literature research output alongside campaigns
- connect claims and references to experiment planning

## Information architecture

Suggested top-level navigation:

- Workbench
- Campaigns
- Runs
- Benchmarks
- Skills
- Reviews
- Literature

Suggested default landing page:

- Workbench

The landing page should summarize:

- active campaigns
- recent run outcomes
- benchmark deltas
- failed stages that need attention
- most-used skills

## Design principles

### 1. Provenance first

Every metric should be navigable back to:

- the run
- the stage
- the artifact set
- the parser summary
- the validation result

### 2. Structured before conversational

Chat should not be the primary interface.

Use structured panes for:

- workflow editing
- metric comparison
- artifact inspection
- validation review

### 3. Scientific visibility over task completion theater

Do not optimize for "agent completed task" messaging.

Optimize for:

- what was run
- what changed
- what failed
- what evidence supports the result

### 4. One-click traceability

Every run card should expose:

- inputs
- outputs
- logs
- metrics
- validation
- provenance

## Data model extensions needed for the UI

The current backend is close, but the workbench will need additional read models:

- campaign summaries with recent run aggregates
- run-stage summaries with artifact counts
- benchmark report indexes
- skill metadata with domain tags and schema summaries
- artifact listing by run and stage
- workflow template catalog

These should be exposed as read-optimized API endpoints rather than forcing the UI to reconstruct state client-side.

## Skill Catalog architecture

The catalog should treat each skill as a typed product object with:

- `name`
- `domain`
- `source`
- `description`
- `input_schema`
- `output_schema`
- `required_context`
- `required_integrations`
- `trust_level`
- `example_uses`

Trust levels:

- `execution_safe`
- `requires_operator_review`
- `planner_only`

This is especially important if external skill libraries are imported later.

## Campaign Studio architecture

The workflow editor should be stage-native, not prompt-native.

Each stage node should expose:

- simulator kind
- task family
- typed parameters
- dependencies
- mapping identifier
- expected outputs
- validation rules

The editor should support:

- drag-to-connect dependencies
- form-driven parameter editing
- simulator-specific stage templates
- JSON export for exact reproducibility

## Initial implementation sequence

1. Add read-only campaign and run pages.
2. Add a read-only skill catalog generated from the existing registry.
3. Add a benchmark report browser.
4. Add a workflow graph viewer for existing campaigns.
5. Add campaign creation and editing once schema endpoints exist.

## What should stay out of v1

- free-form agent chat as the main control surface
- generic notebook replacement features
- XR-specific UI affordances
- robotics control panels

Those can be added later if the backend grows in that direction.
