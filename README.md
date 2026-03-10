# physics_researcher

`physics_researcher` is a production-minded Python monorepo for an autonomous digital materials lab. It combines typed orchestration services, agent tooling, simulation adapters, experiment tracking, and local infrastructure so closed-loop materials or process optimization workflows can be developed, tested, and run from one repository.

## Status

- Working local development scaffold
- Fake simulator-backed campaign loop implemented and tested
- Real simulator adapters for LAMMPS and OpenMM scaffolded behind a stable interface
- FastAPI API, Typer CLI, Redis/Ray worker path, PostgreSQL storage, MLflow hooks, and OpenTelemetry wiring in place

## Architecture at a glance

- `apps/api`: FastAPI control plane for campaigns, runs, artifacts, and health checks
- `apps/worker`: Redis Streams consumer that dispatches campaign steps via Ray
- `packages/core`: Pydantic v2 models, enums, settings, and utility helpers
- `packages/campaigns`: orchestration services, queueing, and MLflow logging
- `packages/simulators`: simulator contract, fake backend, and LAMMPS/OpenMM scaffolds
- `packages/optimizers`: Bayesian optimization and batch-selection logic
- `packages/skills`: typed reusable skills that can be exposed as ADK tools
- `packages/agents`: planner, execution, analysis, critic, and workflow agent scaffolds
- `packages/storage`: SQLAlchemy models, repositories, artifact store, and Alembic setup
- `packages/telemetry`: structured logging and tracing helpers
- `examples`: seeded demo campaign, config samples, and notebook scaffold
- `examples/prompts`: runnable problem statements and iteration prompts
- `docs`: ADRs, architecture notes, and operator playbooks

More detail is in [docs/architecture/overview.md](docs/architecture/overview.md) and [docs/adr/0001-orchestration-and-simulator-boundary.md](docs/adr/0001-orchestration-and-simulator-boundary.md).

## Core capabilities

- Create and manage optimization campaigns
- Define objectives, constraints, search spaces, and budgets
- Step campaigns synchronously for debugging or asynchronously through Redis and Ray
- Persist campaign metadata, runs, metrics, decisions, summaries, and artifacts
- Track runs in MLflow
- Expose deterministic skills and ADK-compatible agent tools
- Validate the full loop locally with a deterministic fake simulator

## Quickstart

### Prerequisites

- Python `3.12`
- `uv`
- Docker with Docker Compose
- Node.js `>=20` for Prettier-based formatting

### Bootstrap

```bash
uv run autolab init
uv sync --all-packages
npm ci
make up
```

The API will be available at [`http://localhost:8000/docs`](http://localhost:8000/docs).

### Run the demo workflow

```bash
uv run autolab seed-demo
uv run autolab start-campaign <campaign-id>
uv run autolab step-campaign <campaign-id> --execute-inline
uv run autolab list-runs <campaign-id>
```

The seeded example campaign lives at [demo_campaign.json](examples/campaigns/demo_campaign.json).

## Development commands

```bash
make sync
make lint
make format
make typecheck
make test
uv run autolab --help
npm run format:check
```

## Example problems to try

Start with the prompt and spec library in [examples/prompts/experiment_prompts.md](examples/prompts/experiment_prompts.md).

The most useful first runs are:

- [baseline_conductivity.json](examples/campaigns/baseline_conductivity.json)
- [cautious_feasible_search.json](examples/campaigns/cautious_feasible_search.json)
- [process_window_tuning.json](examples/campaigns/process_window_tuning.json)

## Local stack

The default Docker Compose stack includes:

- PostgreSQL
- Redis
- MLflow
- OpenTelemetry Collector
- Ray head node
- API service
- Worker service

Real simulator engines are intentionally not included in the default stack. The fake backend is the default for local development and CI.

## Testing strategy

- Unit tests for models, skills, and fake simulator behavior
- Integration tests for API lifecycle and simulator adapter contracts
- End-to-end test for the closed-loop demo campaign
- Strict linting and mypy enforcement in CI

## Open source repo conventions

- Contributor guidance: [CONTRIBUTING.md](CONTRIBUTING.md)
- Code of conduct: [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md)
- Security policy: [SECURITY.md](SECURITY.md)
- License: [LICENSE](LICENSE)

## Roadmap notes

The current repository is intentionally strong on boundaries and local operability rather than depth of domain-specific simulation logic. The next logical additions are:

- richer optimizer implementations
- production MLflow backend configuration
- real LAMMPS/OpenMM execution environments
- dashboard UI beyond the current placeholder
- stronger auth and multi-user controls
