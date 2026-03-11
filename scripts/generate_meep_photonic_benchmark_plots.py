from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from pathlib import Path

import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
DOCS_ASSET_DIR = ROOT / "docs" / "benchmarks" / "assets"
COMPARISON_CSV_PATH = DOCS_ASSET_DIR / "meep_photonic_devices_comparison.csv"
SIGNAL_PLOT_PATH = DOCS_ASSET_DIR / "meep_photonic_devices_signal_metrics.png"
SUPPORTING_PLOT_PATH = DOCS_ASSET_DIR / "meep_photonic_devices_supporting_metrics.png"

REPORTS = {
    "baseline": ROOT / "artifacts" / "benchmarks" / "meep-photonic-devices-v1" / "report.json",
    "refined": (
        ROOT / "artifacts" / "benchmarks" / "meep-photonic-devices-refined-v1" / "report.json"
    ),
}


@dataclass(frozen=True)
class TaskDefinition:
    label: str
    campaign_fragment: str
    signal_metric: str
    signal_label: str


TASKS = (
    TaskDefinition(
        label="Mode converter",
        campaign_fragment="mode-converter",
        signal_metric="transmission_mean",
        signal_label="Transmission mean",
    ),
    TaskDefinition(
        label="Splitter",
        campaign_fragment="splitter",
        signal_metric="splitter_score",
        signal_label="Splitter score",
    ),
    TaskDefinition(
        label="Demux",
        campaign_fragment="demux",
        signal_metric="demux_score",
        signal_label="Demux score",
    ),
)

SERIES_COLORS = {"baseline": "#64748b", "refined": "#0f766e"}


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def best_run_for_campaign(campaign_id: str, primary_metric: str) -> tuple[str, dict, dict]:
    run_root = ROOT / "artifacts" / "runs" / campaign_id
    best_run_id: str | None = None
    best_summary: dict | None = None
    best_parameters: dict | None = None
    best_value: float | None = None

    for summary_path in sorted(run_root.glob("*/meep/parsed_summary.json")):
        summary = load_json(summary_path)
        metric_value = float(summary["scalar_metrics"][primary_metric])
        if best_value is None or metric_value > best_value:
            best_value = metric_value
            best_run_id = summary_path.parents[1].name
            best_summary = summary
            parameter_path = summary_path.with_name("parameters.json")
            best_parameters = load_json(parameter_path) if parameter_path.exists() else {}

    if best_run_id is None or best_summary is None or best_parameters is None:
        raise FileNotFoundError(f"No run artifacts found for campaign {campaign_id}")

    return best_run_id, best_summary, best_parameters


def task_definition_for_campaign(campaign_name: str) -> TaskDefinition:
    for definition in TASKS:
        if definition.campaign_fragment in campaign_name:
            return definition
    raise KeyError(f"Unsupported campaign name: {campaign_name}")


def build_rows() -> list[dict[str, str | float | int]]:
    rows: list[dict[str, str | float | int]] = []
    for report_label, report_path in REPORTS.items():
        report = load_json(report_path)
        for task_report in report["task_reports"]:
            task_definition = task_definition_for_campaign(task_report["campaign_name"])
            run_id, parsed_summary, parameters = best_run_for_campaign(
                task_report["campaign_id"],
                task_report["primary_metric"],
            )
            metrics = parsed_summary["scalar_metrics"]
            rows.append(
                {
                    "series": report_label,
                    "task_label": task_definition.label,
                    "campaign_name": task_report["campaign_name"],
                    "campaign_id": task_report["campaign_id"],
                    "run_id": run_id,
                    "run_count": int(task_report["run_count"]),
                    "best_metric": float(task_report["best_metric"]),
                    "mean_metric": float(task_report["mean_metric"]),
                    "artifact_coverage": float(task_report["artifact_coverage"]),
                    "workflow_stage_coverage": float(task_report["workflow_stage_coverage"]),
                    "signal_metric_name": task_definition.signal_metric,
                    "signal_metric_value": float(metrics.get(task_definition.signal_metric, 0.0)),
                    "reflection_peak": float(metrics.get("reflection_peak", 0.0)),
                    "split_balance": float(metrics.get("split_balance", 0.0)),
                    "demux_target_mean": float(metrics.get("demux_target_mean", 0.0)),
                    "demux_leakage_mean": float(metrics.get("demux_leakage_mean", 0.0)),
                    "refractive_index": float(parameters.get("refractive_index", 0.0)),
                }
            )
    return rows


def write_csv(rows: list[dict[str, str | float | int]]) -> None:
    DOCS_ASSET_DIR.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "series",
        "task_label",
        "campaign_name",
        "campaign_id",
        "run_id",
        "run_count",
        "best_metric",
        "mean_metric",
        "artifact_coverage",
        "workflow_stage_coverage",
        "signal_metric_name",
        "signal_metric_value",
        "reflection_peak",
        "split_balance",
        "demux_target_mean",
        "demux_leakage_mean",
        "refractive_index",
    ]
    with COMPARISON_CSV_PATH.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def render_signal_plot(rows: list[dict[str, str | float | int]]) -> None:
    plt.style.use("seaborn-v0_8-whitegrid")
    fig, axes = plt.subplots(1, 3, figsize=(13.5, 4.6), constrained_layout=True)

    for axis, definition in zip(axes, TASKS, strict=True):
        task_rows = [row for row in rows if row["task_label"] == definition.label]
        labels = [str(row["series"]).capitalize() for row in task_rows]
        values = [float(row["signal_metric_value"]) for row in task_rows]
        colors = [SERIES_COLORS[str(row["series"])] for row in task_rows]
        bars = axis.bar(labels, values, color=colors, width=0.58)
        axis.set_yscale("log")
        axis.set_title(definition.label)
        axis.set_ylabel(definition.signal_label)
        for bar, value in zip(bars, values, strict=True):
            axis.text(
                bar.get_x() + bar.get_width() / 2.0,
                value * 1.25,
                f"{value:.2e}",
                ha="center",
                va="bottom",
                fontsize=8,
            )

    fig.suptitle("MEEP photonic benchmark: task-specific signal metrics", fontsize=14)
    fig.savefig(SIGNAL_PLOT_PATH, dpi=220, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def render_supporting_plot(rows: list[dict[str, str | float | int]]) -> None:
    plt.style.use("seaborn-v0_8-whitegrid")
    fig, axes = plt.subplots(1, 3, figsize=(13.5, 4.8), constrained_layout=True)

    mode_rows = [row for row in rows if row["task_label"] == "Mode converter"]
    splitter_rows = [row for row in rows if row["task_label"] == "Splitter"]
    demux_rows = [row for row in rows if row["task_label"] == "Demux"]

    labels = [str(row["series"]).capitalize() for row in mode_rows]
    reflection_values = [float(row["reflection_peak"]) for row in mode_rows]
    bars = axes[0].bar(
        labels,
        reflection_values,
        color=[SERIES_COLORS[str(row["series"])] for row in mode_rows],
        width=0.58,
    )
    axes[0].set_title("Mode reflection peak")
    for bar, value in zip(bars, reflection_values, strict=True):
        axes[0].text(
            bar.get_x() + bar.get_width() / 2.0,
            value * 1.03,
            f"{value:.3f}",
            ha="center",
            va="bottom",
            fontsize=8,
        )

    labels = [str(row["series"]).capitalize() for row in splitter_rows]
    split_balance_values = [float(row["split_balance"]) for row in splitter_rows]
    bars = axes[1].bar(
        labels,
        split_balance_values,
        color=[SERIES_COLORS[str(row["series"])] for row in splitter_rows],
        width=0.58,
    )
    axes[1].set_title("Splitter balance")
    axes[1].set_ylim(0.0, 1.08)
    for bar, value in zip(bars, split_balance_values, strict=True):
        axes[1].text(
            bar.get_x() + bar.get_width() / 2.0,
            min(value + 0.03, 1.05),
            f"{value:.3f}",
            ha="center",
            va="bottom",
            fontsize=8,
        )

    labels = [str(row["series"]).capitalize() for row in demux_rows]
    positions = list(range(len(labels)))
    target_values = [float(row["demux_target_mean"]) for row in demux_rows]
    leakage_values = [float(row["demux_leakage_mean"]) for row in demux_rows]
    axes[2].bar(
        [position - 0.18 for position in positions],
        target_values,
        width=0.36,
        color="#1d4ed8",
        label="Target mean",
    )
    axes[2].bar(
        [position + 0.18 for position in positions],
        leakage_values,
        width=0.36,
        color="#b45309",
        label="Leakage mean",
    )
    axes[2].set_xticks(positions, labels)
    axes[2].set_title("Demux routing means")
    axes[2].legend(frameon=False, fontsize=8)

    fig.suptitle("MEEP photonic benchmark: supporting metrics", fontsize=14)
    fig.savefig(SUPPORTING_PLOT_PATH, dpi=220, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def main() -> None:
    rows = build_rows()
    write_csv(rows)
    render_signal_plot(rows)
    render_supporting_plot(rows)
    print(COMPARISON_CSV_PATH)
    print(SIGNAL_PLOT_PATH)
    print(SUPPORTING_PLOT_PATH)


if __name__ == "__main__":
    main()
