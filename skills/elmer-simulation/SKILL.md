---
name: elmer-simulation
description: Elmer FEM experiment-spec and validation guidance for continuum simulation stages. Use when creating Elmer `.sif` stage defaults, checking expected solver artifacts, or reviewing parsed continuum outputs in Autolab workflows.
---

# Elmer Simulation

- Create solver specs with explicit steady-state iteration settings and material coefficients.
- Expect generated artifacts: `case.sif`, manifests, logs, and parsed summaries.
- Validate that solver output exists and stage completion is successful before trusting downstream transfer.
- Prefer Elmer stages as downstream consumers of mapped properties from atomistic or device simulators.
- Keep mappings explicit so cross-scale assumptions remain auditable.
