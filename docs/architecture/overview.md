# Architecture Overview

Autolab is organized as a Python monorepo with clear boundaries between orchestration, optimization, simulation, storage, and user-facing interfaces.

## Control plane

`apps/api` exposes campaign management endpoints and a bearer-token auth scaffold. Route handlers are thin and delegate to `CampaignService`, `RunService`, and `ArtifactService`.

## Execution plane

`apps/worker` consumes Redis Stream events and executes campaign steps through Ray. The worker reconstructs the same service graph used by the API and runs steps asynchronously by default.

## Domain and persistence

`packages/core` owns transport models and configuration. `packages/storage` persists campaigns, runs, metrics, agent decisions, summaries, artifacts, and optimizer state with SQLAlchemy and Alembic.

## Optimization and agents

`packages/optimizers` contains the working Bayesian optimizer path and a clean RL extension point. `packages/skills` defines reusable typed capabilities. `packages/agents` wraps those skills into Google ADK-compatible agent definitions without coupling the agents to simulator internals.

## Simulation backends

`packages/simulators` defines the only stable simulator contract. The fake backend is production-shaped enough for CI and demo workflows. Real engine adapters live behind the same interface, with isolated assets under `integrations/lammps` and `integrations/openmm`.
