# Contributing

## Development setup

```bash
uv run autolab init
uv sync --all-packages
npm ci
pre-commit install
```

## Before opening a pull request

Run the local checks:

```bash
uv run ruff check .
uv run mypy .
uv run pytest
npm run format:check
```

## Repo conventions

- Keep simulator-specific logic inside `packages/simulators` or `integrations/*`.
- Use typed Pydantic models for transport boundaries.
- Keep FastAPI handlers thin and route logic through service classes.
- Add or update tests with behavior changes.
- Prefer small, coherent pull requests.

## Commit style

Short imperative commits are preferred, for example:

- `Add fake simulator timeout classification`
- `Refine campaign step API responses`

## Issues and feature requests

Use the provided GitHub issue templates for bugs and proposals.
