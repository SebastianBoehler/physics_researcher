from __future__ import annotations

import json
import subprocess
from pathlib import Path

import httpx
import typer
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
    result = httpx.post(
        f"{_base_url()}/campaigns/{campaign['id']}/step",
        headers=_headers(),
        json={"execute_inline": True},
        timeout=60.0,
    )
    result.raise_for_status()
    print(result.json())
