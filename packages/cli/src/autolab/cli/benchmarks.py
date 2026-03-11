from __future__ import annotations

import json
import math
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path
from statistics import median
from typing import Any

import httpx
from pydantic import BaseModel, Field


class BenchmarkManifest(BaseModel):
    name: str
    description: str = ""
    paper_hypothesis: str = ""
    primary_metric: str
    campaigns: list[str]
    evaluation: dict[str, Any] = Field(default_factory=dict)


def load_benchmark_manifest(path: Path) -> BenchmarkManifest:
    return BenchmarkManifest.model_validate(json.loads(path.read_text(encoding="utf-8")))


def resolve_benchmark_campaign_path(manifest_path: Path, campaign_ref: str) -> Path:
    candidate = Path(campaign_ref)
    if candidate.is_absolute():
        return candidate
    cwd_candidate = Path.cwd() / candidate
    if cwd_candidate.exists():
        return cwd_candidate
    manifest_relative = manifest_path.parent / candidate
    if manifest_relative.exists():
        return manifest_relative
    return cwd_candidate


def derive_step_budget(payload: dict[str, Any], max_steps: int | None) -> int:
    if max_steps is not None:
        return max_steps
    budget = payload.get("budget", {})
    max_runs = int(budget.get("max_runs", 1))
    batch_size = max(1, int(budget.get("batch_size", 1)))
    return max(1, math.ceil(max_runs / batch_size) + 1)


def summarize_campaign_runs(
    *,
    campaign_name: str,
    campaign_payload: dict[str, Any],
    campaign_response: dict[str, Any],
    runs: list[dict[str, Any]],
    primary_metric: str,
    step_history: list[dict[str, Any]],
    evaluation: dict[str, Any] | None = None,
) -> dict[str, Any]:
    campaign_metadata = campaign_payload.get("metadata", {})
    optimizer_config = campaign_metadata.get("optimizer", {})
    if not isinstance(optimizer_config, dict):
        optimizer_config = {}
    optimizer_algorithm = str(
        optimizer_config.get(
            "algorithm", campaign_metadata.get("optimizer_algorithm", "bayesian_gp")
        )
    )
    baseline_name = str(campaign_metadata.get("baseline_name", optimizer_algorithm))

    ordered_runs = sorted(runs, key=lambda run: str(run.get("created_at", "")))
    metric_values = [
        float(run["metrics"][primary_metric])
        for run in ordered_runs
        if primary_metric in run.get("metrics", {})
    ]
    objective_direction = "maximize"
    for objective in campaign_payload.get("objectives", []):
        if objective.get("metric_key") == primary_metric:
            objective_direction = str(objective.get("direction", "maximize"))
            break
    status_counts: dict[str, int] = {}
    artifact_coverage_hits = 0
    workflow_stage_coverage_hits = 0

    expected_stage_count = (
        len(campaign_payload.get("workflow", {}).get("stages", []))
        if campaign_payload.get("workflow") is not None
        else 1
    )

    metric_history = [
        float(run["metrics"][primary_metric])
        for run in ordered_runs
        if primary_metric in run.get("metrics", {})
    ]
    evaluation = evaluation or {}
    low_gap_thresholds = evaluation.get("low_gap_thresholds", [])
    if not isinstance(low_gap_thresholds, list):
        low_gap_thresholds = []
    low_gap_hits_by_threshold: dict[str, int] = {}
    low_gap_rate_by_threshold: dict[str, float] = {}
    best_so_far_history: list[float] = []
    running_best: float | None = None
    for value in metric_history:
        if running_best is None:
            running_best = value
        elif objective_direction == "minimize":
            running_best = min(running_best, value)
        else:
            running_best = max(running_best, value)
        best_so_far_history.append(running_best)

    for run in ordered_runs:
        status = str(run.get("status", "unknown"))
        status_counts[status] = status_counts.get(status, 0) + 1
        run_metadata = run.get("metadata", {})
        if {"workflow_name", "stage_results", "validation"}.issubset(run_metadata):
            artifact_coverage_hits += 1
        stage_results = run_metadata.get("stage_results", {})
        if isinstance(stage_results, dict) and len(stage_results) >= expected_stage_count:
            workflow_stage_coverage_hits += 1

    run_count = len(runs)
    sorted_metric_values = sorted(metric_values)
    best_metric = (
        (min(metric_values) if objective_direction == "minimize" else max(metric_values))
        if metric_values
        else None
    )
    mean_metric = sum(metric_values) / len(metric_values) if metric_values else None
    median_metric = median(metric_values) if metric_values else None
    top_k_sizes = evaluation.get("top_k_sizes", [3])
    if not isinstance(top_k_sizes, list):
        top_k_sizes = [3]
    top_k_mean_by_size: dict[str, float] = {}
    for top_k_size in top_k_sizes:
        k = max(1, int(top_k_size))
        if not sorted_metric_values:
            continue
        if objective_direction == "minimize":
            selected_values = sorted_metric_values[:k]
        else:
            selected_values = sorted_metric_values[-k:]
        top_k_mean_by_size[f"top_{k}"] = sum(selected_values) / len(selected_values)
    for threshold_value in low_gap_thresholds:
        threshold = float(threshold_value)
        threshold_key = f"{threshold:g}"
        if objective_direction == "minimize":
            hits = sum(1 for value in metric_history if value <= threshold)
        else:
            hits = sum(1 for value in metric_history if value >= threshold)
        low_gap_hits_by_threshold[threshold_key] = hits
        low_gap_rate_by_threshold[threshold_key] = hits / len(metric_history) if metric_history else 0.0

    summary = {
        "campaign_name": campaign_name,
        "campaign_id": campaign_response["id"],
        "simulator": campaign_response["simulator"],
        "status": campaign_response["status"],
        "primary_metric": primary_metric,
        "run_count": run_count,
        "succeeded_runs": status_counts.get("succeeded", 0),
        "failed_runs": status_counts.get("failed", 0),
        "timed_out_runs": status_counts.get("timed_out", 0),
        "best_metric": best_metric,
        "mean_metric": mean_metric,
        "median_metric": median_metric,
        "status_counts": status_counts,
        "metric_direction": objective_direction,
        "artifact_coverage": artifact_coverage_hits / run_count if run_count else 0.0,
        "workflow_stage_coverage": workflow_stage_coverage_hits / run_count if run_count else 0.0,
        "metric_history": metric_history,
        "best_so_far_history": best_so_far_history,
        "step_history": step_history,
        "tags": campaign_payload.get("tags", []),
        "optimizer_algorithm": optimizer_algorithm,
        "baseline_name": baseline_name,
        "metadata": campaign_metadata,
    }
    if low_gap_hits_by_threshold:
        summary["low_gap_hits_by_threshold"] = low_gap_hits_by_threshold
        summary["low_gap_rate_by_threshold"] = low_gap_rate_by_threshold
    if top_k_mean_by_size:
        summary["top_k_mean_by_size"] = top_k_mean_by_size
    return summary


def build_summary(
    task_reports: list[dict[str, Any]],
    evaluation: dict[str, Any],
    *,
    include_baseline_groups: bool = True,
) -> dict[str, Any]:
    aggregate_best = [
        float(report["best_metric"])
        for report in task_reports
        if report.get("best_metric") is not None
    ]
    aggregate_medians = [
        float(report["median_metric"])
        for report in task_reports
        if report.get("median_metric") is not None
    ]
    summary: dict[str, Any] = {
        "task_count": len(task_reports),
        "mean_best_metric": sum(aggregate_best) / len(aggregate_best) if aggregate_best else None,
        "median_best_metric": median(aggregate_best) if aggregate_best else None,
        "mean_median_metric": (
            sum(aggregate_medians) / len(aggregate_medians) if aggregate_medians else None
        ),
        "all_campaigns_succeeded": all(
            report["status"] == "completed" and report["failed_runs"] == 0
            for report in task_reports
        ),
    }
    reference_best = evaluation.get("reference_best_metric")
    if reference_best is not None and aggregate_best:
        reference_value = float(reference_best)
        direction = str(evaluation.get("reference_direction", "maximize"))
        best_observed = max(aggregate_best) if direction == "maximize" else min(aggregate_best)
        if direction == "maximize":
            summary["best_observed_gap_to_reference"] = reference_value - best_observed
        else:
            summary["best_observed_gap_to_reference"] = best_observed - reference_value
        summary["reference_best_metric"] = reference_value
        summary["reference_direction"] = direction
    if include_baseline_groups:
        baseline_groups: dict[str, list[dict[str, Any]]] = {}
        for report in task_reports:
            baseline_name = str(
                report.get("baseline_name", report.get("optimizer_algorithm", "default"))
            )
            baseline_groups.setdefault(baseline_name, []).append(report)
        if baseline_groups:
            summary["baseline_summaries"] = [
                {
                    "baseline_name": baseline_name,
                    "optimizer_algorithm": str(
                        reports[0].get("optimizer_algorithm", baseline_name)
                    ),
                    **build_summary(reports, evaluation, include_baseline_groups=False),
                }
                for baseline_name, reports in sorted(baseline_groups.items())
            ]
    top_k_sizes = evaluation.get("top_k_sizes", [3])
    if isinstance(top_k_sizes, list):
        aggregate_top_k_mean_by_size: dict[str, float] = {}
        for top_k_size in top_k_sizes:
            k = max(1, int(top_k_size))
            key = f"top_{k}"
            values = [
                float(report["top_k_mean_by_size"][key])
                for report in task_reports
                if key in report.get("top_k_mean_by_size", {})
            ]
            if values:
                aggregate_top_k_mean_by_size[key] = sum(values) / len(values)
        if aggregate_top_k_mean_by_size:
            summary["top_k_mean_by_size"] = aggregate_top_k_mean_by_size
    low_gap_thresholds = evaluation.get("low_gap_thresholds", [])
    if isinstance(low_gap_thresholds, list):
        low_gap_hits_by_threshold: dict[str, int] = {}
        low_gap_rate_by_threshold: dict[str, float] = {}
        total_run_count = sum(int(report.get("run_count", 0)) for report in task_reports)
        for threshold_value in low_gap_thresholds:
            threshold = float(threshold_value)
            threshold_key = f"{threshold:g}"
            hits = sum(
                int(report.get("low_gap_hits_by_threshold", {}).get(threshold_key, 0))
                for report in task_reports
            )
            low_gap_hits_by_threshold[threshold_key] = hits
            low_gap_rate_by_threshold[threshold_key] = hits / total_run_count if total_run_count else 0.0
        if low_gap_hits_by_threshold:
            summary["low_gap_hits_by_threshold"] = low_gap_hits_by_threshold
            summary["low_gap_rate_by_threshold"] = low_gap_rate_by_threshold
    return summary


def run_benchmark_suite(
    *,
    manifest_path: Path,
    base_url: str,
    headers: dict[str, str],
    execute_inline: bool,
    max_steps: int | None = None,
    output_path: Path | None = None,
    timeout_seconds: float = 60.0,
    max_parallel_campaigns: int = 1,
) -> dict[str, Any]:
    manifest = load_benchmark_manifest(manifest_path)
    task_reports: list[dict[str, Any] | None] = [None] * len(manifest.campaigns)

    if max_parallel_campaigns <= 1 or len(manifest.campaigns) <= 1:
        for index, campaign_ref in enumerate(manifest.campaigns):
            task_reports[index] = _run_benchmark_campaign(
                manifest_path=manifest_path,
                campaign_ref=campaign_ref,
                primary_metric=manifest.primary_metric,
                evaluation=manifest.evaluation,
                base_url=base_url,
                headers=headers,
                execute_inline=execute_inline,
                max_steps=max_steps,
                timeout_seconds=timeout_seconds,
            )
    else:
        with ThreadPoolExecutor(
            max_workers=min(max_parallel_campaigns, len(manifest.campaigns)),
            thread_name_prefix=f"autolab-benchmark-{manifest.name}",
        ) as executor:
            future_map = {
                executor.submit(
                    _run_benchmark_campaign,
                    manifest_path=manifest_path,
                    campaign_ref=campaign_ref,
                    primary_metric=manifest.primary_metric,
                    evaluation=manifest.evaluation,
                    base_url=base_url,
                    headers=headers,
                    execute_inline=execute_inline,
                    max_steps=max_steps,
                    timeout_seconds=timeout_seconds,
                ): index
                for index, campaign_ref in enumerate(manifest.campaigns)
            }
            for future, index in future_map.items():
                task_reports[index] = future.result()

    suite_report = {
        "benchmark_name": manifest.name,
        "description": manifest.description,
        "paper_hypothesis": manifest.paper_hypothesis,
        "primary_metric": manifest.primary_metric,
        "generated_at": datetime.now(UTC).isoformat(),
        "task_reports": [report for report in task_reports if report is not None],
        "summary": build_summary(
            [report for report in task_reports if report is not None], manifest.evaluation
        ),
        "evaluation": manifest.evaluation,
    }

    destination = output_path or (Path("artifacts") / "benchmarks" / manifest.name / "report.json")
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(suite_report, indent=2), encoding="utf-8")
    return suite_report


def _run_benchmark_campaign(
    *,
    manifest_path: Path,
    campaign_ref: str,
    primary_metric: str,
    evaluation: dict[str, Any],
    base_url: str,
    headers: dict[str, str],
    execute_inline: bool,
    max_steps: int | None,
    timeout_seconds: float,
) -> dict[str, Any]:
    campaign_path = resolve_benchmark_campaign_path(manifest_path, campaign_ref)
    payload = json.loads(campaign_path.read_text(encoding="utf-8"))

    with httpx.Client(timeout=timeout_seconds) as client:
        create_response = client.post(f"{base_url}/campaigns", json=payload, headers=headers)
        create_response.raise_for_status()
        campaign = create_response.json()

        start_response = client.post(
            f"{base_url}/campaigns/{campaign['id']}/start",
            headers=headers,
        )
        start_response.raise_for_status()

        step_history: list[dict[str, Any]] = []
        step_limit = derive_step_budget(payload, max_steps=max_steps)
        for _ in range(step_limit):
            status_response = client.get(
                f"{base_url}/campaigns/{campaign['id']}",
                headers=headers,
            )
            status_response.raise_for_status()
            campaign_status = status_response.json()["status"]
            if campaign_status in {"completed", "failed", "paused"}:
                campaign["status"] = campaign_status
                break
            step_response = client.post(
                f"{base_url}/campaigns/{campaign['id']}/step",
                json={"execute_inline": execute_inline},
                headers=headers,
            )
            step_response.raise_for_status()
            step_payload = step_response.json()
            step_history.append(step_payload)
            if step_payload["status"] in {"completed", "failed"}:
                campaign["status"] = step_payload["status"]
                break
            campaign["status"] = step_payload["status"]

        runs_response = client.get(
            f"{base_url}/campaigns/{campaign['id']}/runs",
            headers=headers,
        )
        runs_response.raise_for_status()
        runs = runs_response.json()["runs"]

    return summarize_campaign_runs(
        campaign_name=payload["name"],
        campaign_payload=payload,
        campaign_response=campaign,
        runs=runs,
        primary_metric=primary_metric,
        step_history=step_history,
        evaluation=evaluation,
    )
