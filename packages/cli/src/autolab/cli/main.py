from __future__ import annotations

import json
import subprocess
from pathlib import Path

import httpx
import typer
from autolab.cli.benchmarks import run_benchmark_suite
from autolab.core.settings import get_settings
from rich import print

app = typer.Typer(help="Autolab control CLI.")


def _base_url() -> str:
    settings = get_settings()
    return f"http://{settings.app.api_host}:{settings.app.api_port}"


def _headers() -> dict[str, str]:
    settings = get_settings()
    return {"Authorization": f"Bearer {settings.auth.admin_token}"}


def _run_compose(args: list[str]) -> None:
    subprocess.run(["docker", "compose", *args], check=True)


@app.command("init")
def init_env() -> None:
    env_example = Path(".env.example")
    env_file = Path(".env")
    if env_file.exists():
        print("[yellow].env already exists[/yellow]")
        return
    env_file.write_text(env_example.read_text(encoding="utf-8"), encoding="utf-8")
    print("[green]Created .env from .env.example[/green]")


@app.command("up")
def up() -> None:
    _run_compose(["up", "-d", "--build"])


@app.command("down")
def down() -> None:
    _run_compose(["down"])


@app.command("create-campaign")
def create_campaign(config_path: Path) -> None:
    payload = json.loads(config_path.read_text(encoding="utf-8"))
    response = httpx.post(
        f"{_base_url()}/campaigns", json=payload, headers=_headers(), timeout=30.0
    )
    response.raise_for_status()
    print(response.json())


@app.command("start-campaign")
def start_campaign(campaign_id: str) -> None:
    response = httpx.post(
        f"{_base_url()}/campaigns/{campaign_id}/start",
        headers=_headers(),
        timeout=30.0,
    )
    response.raise_for_status()
    print(response.json())


@app.command("step-campaign")
def step_campaign(campaign_id: str, execute_inline: bool = False) -> None:
    response = httpx.post(
        f"{_base_url()}/campaigns/{campaign_id}/step",
        headers=_headers(),
        json={"execute_inline": execute_inline},
        timeout=30.0,
    )
    response.raise_for_status()
    print(response.json())


@app.command("list-runs")
def list_runs(campaign_id: str) -> None:
    response = httpx.get(
        f"{_base_url()}/campaigns/{campaign_id}/runs",
        headers=_headers(),
        timeout=30.0,
    )
    response.raise_for_status()
    print(response.json())


@app.command("inspect-run")
def inspect_run(run_id: str) -> None:
    response = httpx.get(f"{_base_url()}/runs/{run_id}", headers=_headers(), timeout=30.0)
    response.raise_for_status()
    print(response.json())


@app.command("open-review")
def open_review(
    campaign_id: str,
    title: str,
    objective: str,
    created_by: str,
    run_id: str | None = None,
    artifact_ids: list[str] | None = None,
) -> None:
    payload = {
        "title": title,
        "objective": objective,
        "created_by": created_by,
        "run_id": run_id,
        "artifact_ids": artifact_ids or [],
        "participants": [],
    }
    response = httpx.post(
        f"{_base_url()}/campaigns/{campaign_id}/reviews",
        json=payload,
        headers=_headers(),
        timeout=30.0,
    )
    response.raise_for_status()
    print(response.json())


@app.command("list-reviews")
def list_reviews(campaign_id: str, run_id: str | None = None) -> None:
    response = httpx.get(
        f"{_base_url()}/campaigns/{campaign_id}/reviews",
        params={"run_id": run_id} if run_id is not None else None,
        headers=_headers(),
        timeout=30.0,
    )
    response.raise_for_status()
    print(response.json())


@app.command("show-review")
def show_review(review_id: str) -> None:
    response = httpx.get(f"{_base_url()}/reviews/{review_id}", headers=_headers(), timeout=30.0)
    response.raise_for_status()
    print(response.json())


@app.command("comment-review")
def comment_review(
    review_id: str,
    author_key: str,
    body: str,
    author_type: str = "human",
    role_label: str | None = None,
    parent_post_id: str | None = None,
) -> None:
    payload = {
        "author_key": author_key,
        "author_type": author_type,
        "body": body,
        "role_label": role_label,
        "parent_post_id": parent_post_id,
    }
    response = httpx.post(
        f"{_base_url()}/reviews/{review_id}/posts",
        json=payload,
        headers=_headers(),
        timeout=30.0,
    )
    response.raise_for_status()
    print(response.json())


@app.command("run-review-round")
def run_review_round(
    review_id: str,
    mode: str = "moderated_panel",
    participant_keys: list[str] | None = None,
    execute_inline: bool = False,
) -> None:
    payload = {
        "mode": mode,
        "participant_keys": participant_keys or [],
        "execute_inline": execute_inline,
    }
    response = httpx.post(
        f"{_base_url()}/reviews/{review_id}/rounds",
        json=payload,
        headers=_headers(),
        timeout=60.0,
    )
    response.raise_for_status()
    print(response.json())


@app.command("resolve-review")
def resolve_review(
    review_id: str,
    status: str,
    resolution_summary: str,
    resolved_by: str = "system",
) -> None:
    payload = {
        "status": status,
        "resolution_summary": resolution_summary,
        "resolved_by": resolved_by,
    }
    response = httpx.post(
        f"{_base_url()}/reviews/{review_id}/resolve",
        json=payload,
        headers=_headers(),
        timeout=30.0,
    )
    response.raise_for_status()
    print(response.json())


@app.command("seed-demo")
def seed_demo() -> None:
    payload = json.loads(Path("examples/campaigns/demo_campaign.json").read_text(encoding="utf-8"))
    response = httpx.post(
        f"{_base_url()}/campaigns", json=payload, headers=_headers(), timeout=30.0
    )
    response.raise_for_status()
    campaign = response.json()
    httpx.post(
        f"{_base_url()}/campaigns/{campaign['id']}/start",
        headers=_headers(),
        timeout=30.0,
    ).raise_for_status()
    print(campaign)


@app.command("test-sim")
def test_sim() -> None:
    payload = json.loads(
        Path("examples/campaigns/cross_simulator_transfer_verification.json").read_text(
            encoding="utf-8"
        )
    )
    response = httpx.post(
        f"{_base_url()}/campaigns", json=payload, headers=_headers(), timeout=30.0
    )
    response.raise_for_status()
    campaign = response.json()
    httpx.post(
        f"{_base_url()}/campaigns/{campaign['id']}/start",
        headers=_headers(),
        timeout=30.0,
    ).raise_for_status()
    result = httpx.post(
        f"{_base_url()}/campaigns/{campaign['id']}/step",
        headers=_headers(),
        json={"execute_inline": True},
        timeout=60.0,
    )
    result.raise_for_status()
    print(result.json())


@app.command("run-benchmark")
def run_benchmark(
    manifest_path: Path = Path("benchmarks/meep_inverse_design/benchmark.json"),
    execute_inline: bool = True,
    max_steps: int | None = None,
    output_path: Path | None = None,
    max_parallel_campaigns: int | None = None,
) -> None:
    settings = get_settings()
    report = run_benchmark_suite(
        manifest_path=manifest_path,
        base_url=_base_url(),
        headers=_headers(),
        execute_inline=execute_inline,
        max_steps=max_steps,
        output_path=output_path,
        max_parallel_campaigns=(
            max_parallel_campaigns
            if max_parallel_campaigns is not None
            else settings.app.max_parallel_benchmark_campaigns
        ),
    )
    print(report)
