# Local Development Playbook

1. Run `uv run autolab init` to create `.env`.
2. Run `uv sync --all-packages` to install workspace packages.
3. Start infrastructure with `make up`.
4. Visit `http://localhost:8000/docs` for OpenAPI.
5. Use `uv run autolab seed-demo` to create a fake-simulator campaign.
6. Use `uv run autolab step-campaign <campaign-id> --execute-inline` for a synchronous debug step or omit `--execute-inline` to exercise the worker queue.
7. Use the prompt and spec catalog in [examples/prompts/experiment_prompts.md](../../examples/prompts/experiment_prompts.md) when you want structured scenarios to run against the stack.
