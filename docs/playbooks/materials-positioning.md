# Materials Positioning

This note defines how `physics_researcher` should present itself publicly as the project grows from a simulator-centric monorepo into a product surface for autonomous materials R&D.

## Positioning statement

`physics_researcher` is an AI operating system for autonomous materials research.

It connects:

- agent planning
- typed simulation workflows
- measurement and protocol loops
- experiment provenance
- benchmarked evaluation

The project should present itself as a materials-research workbench, not as a generic agent framework and not as an XR lab copilot today.

## Category

Closest category:

- autonomous research operating system for materials science

Not yet credible:

- AI-XR co-scientist
- wet-lab robotics runtime
- general scientific AGI platform

Those can become future directions, but they should not be headline claims until the corresponding perception, instrument, or robotics layers exist in the repo.

## How to be LabOS-like without overclaiming

LabOS is a useful reference because it presents an integrated surface:

- a clear product identity
- a benchmark and leaderboard story
- operator-facing interfaces
- a visible loop between planning and execution

This project should emulate the product discipline, not the exact claim set.

Recommended public framing:

- "AI operating system for autonomous materials research"
- "Agentic workbench for simulation, measurement, and reproducible campaign execution"
- "From candidate generation to simulator orchestration to measurement feedback"

Avoid these until implemented:

- XR-first messaging
- robotics-first messaging
- "works with humans in real laboratories" as a primary claim

## Core differentiators

The strongest current differentiators in this repository are:

- typed stage-based workflows
- simulator adapter boundaries
- cross-simulator provenance capture
- benchmarkable campaign execution
- ADK-compatible typed skills rather than ad hoc prompt bundles

This means the project should lead with:

1. Trustworthy workflow execution
2. Reproducible materials benchmarks
3. Extensible simulator and measurement lanes
4. Curated materials-specific skill packs

## Target narrative

### Current narrative

"A production-minded monorepo for an autonomous digital materials lab."

This is directionally correct but undersells the product shape.

### Recommended narrative

"A materials research workbench that lets agents plan, execute, compare, and improve simulation and measurement campaigns through typed workflows and reproducible provenance."

### Short homepage version

"Autonomous materials R&D, grounded in typed workflows."

### Longer homepage version

"`physics_researcher` is an AI operating system for materials R&D. It gives agents and researchers a shared workbench for orchestrating simulator chains, measurement loops, benchmarks, and reusable skills without sacrificing provenance or execution control."

## Product pillars

The product surface should be organized around five pillars:

### 1. Plan

- create campaign intents
- compose workflows from typed stages
- choose objectives, constraints, and budgets

### 2. Execute

- run simulators and measurement stages
- manage queues, artifacts, and failures
- preserve manifests, logs, and parser outputs

### 3. Compare

- compare runs, seeds, benchmarks, and optimizers
- inspect transfer mappings across stages
- evaluate progress against benchmark baselines

### 4. Reuse

- discover curated skills
- promote successful workflow templates
- reuse benchmark and analysis recipes

### 5. Govern

- expose provenance
- show execution history
- make operator approvals and measurement evidence explicit

## Messaging guardrails

Do:

- say "materials workbench"
- say "autonomous materials research"
- say "simulation-to-measurement loops"
- say "typed skills and workflows"
- say "benchmark-grade execution"

Do not:

- imply embodied perception if there is no perception layer
- imply robotics autonomy if there are no robotics adapters
- imply experimental safety guarantees
- market a broad scientific domain coverage that the current simulator stack does not support

## What to build so the positioning becomes true

The minimum product work needed to support this positioning is:

1. A real web workbench with campaign and run visibility
2. A curated materials skill catalog
3. Benchmark-grade simulator lanes for materials workflows
4. Measurement-facing interfaces for XRD and related characterization
5. Comparison and leaderboard surfaces

## Near-term tagline candidates

- "AI operating system for autonomous materials research"
- "Materials R&D workbench for agents and researchers"
- "Typed workflows for autonomous simulation and measurement"
- "From candidate proposal to benchmarked experiment trace"
