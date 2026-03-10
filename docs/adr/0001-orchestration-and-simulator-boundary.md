# ADR 0001: Separate campaign orchestration from simulator adapters

## Status

Accepted

## Context

The system needs to run autonomous closed-loop campaigns while remaining extensible to multiple simulation backends. Optimizers, agents, the API, and workers must not encode simulator-specific logic or depend on unstable engine details.

## Decision

- Introduce a strict `SimulatorBackend` protocol with `prepare_input`, `run`, `poll`, `parse`, and `validate`.
- Keep orchestrators, skills, and agents dependent on typed transport models rather than backend-specific payloads.
- Place engine-specific assets in isolated integration directories and keep real engines out of the default local stack.
- Use a deterministic fake simulator as the default backend for local development, tests, and documentation.

## Consequences

- New simulators can be added without changing campaign logic.
- Agent reasoning remains above the simulator boundary and cannot manipulate physics-engine internals directly.
- CI remains deterministic and lightweight because it relies on the fake simulator rather than heavyweight engine binaries.
