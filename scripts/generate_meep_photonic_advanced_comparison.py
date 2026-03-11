from __future__ import annotations

import csv
import json
import math
from dataclasses import dataclass
from pathlib import Path

import matplotlib.pyplot as plt


ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT / "docs" / "benchmarks" / "assets"
CSV_PATH = OUTPUT_DIR / "meep_photonic_advanced_comparison.csv"
PLOT_PATH = OUTPUT_DIR / "meep_photonic_advanced_comparison.png"

REPORTS = {
    "refined": ROOT / "artifacts" / "benchmarks" / "meep-photonic-devices-refined-v1" / "report.json",
    "advanced": ROOT / "artifacts" / "benchmarks" / "meep-photonic-devices-advanced-v1" / "report.json",
}


@dataclass(frozen=True)
class TaskDefinition:
    label: str
    fragment: str


TASKS = (
    TaskDefinition("Mode converter", "mode-converter"),
    TaskDefinition("Splitter", "splitter"),
    TaskDefinition("Demux", "demux"),
)

SERIES_COLORS = {"refined": "#64748b", "advanced": "#0f766e"}


def _power_db(value: float, *, floor: float = 1.0e-12) -> float:
    return 10.0 * math.log10(max(value, floor))


def _insertion_loss_db(value: float) -> float:
    return -_power_db(value)


def _imbalance_db(first: float, second: float, *, floor: float = 1.0e-12) -> float:
    numerator = max(first, second, floor)
    denominator = max(min(first, second), floor)
    return 10.0 * math.log10(numerator / denominator)


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def find_task_definition(campaign_name: str) -> TaskDefinition:
    for task in TASKS:
        if task.fragment in campaign_name:
            return task
    raise KeyError(f"unsupported campaign name: {campaign_name}")


def best_run_for_campaign(campaign_id: str, primary_metric: str) -> tuple[str, dict]:
    run_root = ROOT / "artifacts" / "runs" / campaign_id
    best_run_id: str | None = None
    best_summary: dict | None = None
    best_value: float | None = None
    for summary_path in sorted(run_root.glob("*/meep/parsed_summary.json")):
        summary = load_json(summary_path)
        metric_value = summary.get("scalar_metrics", {}).get(primary_metric)
        if metric_value is None:
            continue
        value = float(metric_value)
        if best_value is None or value > best_value:
            best_value = value
            best_run_id = summary_path.parents[1].name
            best_summary = summary
    if best_run_id is None or best_summary is None:
        raise FileNotFoundError(f"no best run found for campaign {campaign_id}")
    return best_run_id, best_summary


def derive_mode_metrics(summary: dict) -> dict[str, float]:
    metrics = summary["scalar_metrics"]
    transmission = float(metrics.get("transmission_mean", 0.0))
    reflection = float(metrics.get("reflection_mean", metrics.get("reflection_peak", 0.0)))
    passband_fraction = metrics.get("passband_fraction")
    if passband_fraction is None:
        transmission_series = [float(value) for value in summary.get("timeseries", {}).get("transmission", [])]
        peak = max(transmission_series) if transmission_series else transmission
        threshold = max(0.1, 0.5 * peak)
        passband_fraction = (
            sum(1 for value in transmission_series if value >= threshold) / len(transmission_series)
            if transmission_series
            else 0.0
        )
    return {
        "device_score": float(metrics.get("device_score", 0.0)),
        "insertion_loss_db": float(metrics.get("insertion_loss_db", _insertion_loss_db(transmission))),
        "return_loss_db": float(metrics.get("return_loss_db", _insertion_loss_db(reflection))),
        "bandwidth_fraction": float(passband_fraction),
    }


def derive_splitter_metrics(summary: dict) -> dict[str, float]:
    metrics = summary["scalar_metrics"]
    total_output_mean = float(metrics.get("total_output_mean", 0.0))
    upper_mean = float(metrics.get("upper_mean", 0.0))
    lower_mean = float(metrics.get("lower_mean", 0.0))
    splitter_bandwidth_fraction = metrics.get("splitter_bandwidth_fraction")
    if splitter_bandwidth_fraction is None:
        upper = [float(value) for value in summary.get("timeseries", {}).get("upper", [])]
        lower = [float(value) for value in summary.get("timeseries", {}).get("lower", [])]
        totals = [first + second for first, second in zip(upper, lower, strict=False)]
        peak = max(totals) if totals else total_output_mean
        threshold = max(1.0e-6, 0.5 * peak)
        splitter_bandwidth_fraction = (
            sum(
                1
                for first, second, total in zip(upper, lower, totals, strict=False)
                if total >= threshold and _imbalance_db(first, second) <= 1.0
            )
            / len(totals)
            if totals
            else 0.0
        )
    return {
        "device_score": float(metrics.get("device_score", 0.0)),
        "excess_loss_db": float(
            metrics.get("splitter_excess_loss_db", _insertion_loss_db(total_output_mean))
        ),
        "split_imbalance_db": float(
            metrics.get("split_imbalance_db", _imbalance_db(upper_mean, lower_mean))
        ),
        "bandwidth_fraction": float(splitter_bandwidth_fraction),
    }


def derive_demux_metrics(summary: dict) -> dict[str, float]:
    metrics = summary["scalar_metrics"]
    target = float(metrics.get("demux_target_mean", 0.0))
    leakage = float(metrics.get("demux_leakage_mean", 0.0))
    bandwidth_fraction = metrics.get("demux_bandwidth_fraction", 0.0)
    isolation_db = metrics.get("demux_isolation_db")
    if isolation_db is None:
        isolation_db = -_power_db(leakage / max(target, 1.0e-12))
    return {
        "device_score": float(metrics.get("device_score", 0.0)),
        "insertion_loss_db": float(
            metrics.get("demux_insertion_loss_db", _insertion_loss_db(target))
        ),
        "isolation_db": float(isolation_db),
        "bandwidth_fraction": float(bandwidth_fraction),
    }


def build_rows() -> list[dict[str, str | float]]:
    rows: list[dict[str, str | float]] = []
    for series, report_path in REPORTS.items():
        report = load_json(report_path)
        for task_report in report["task_reports"]:
            task = find_task_definition(task_report["campaign_name"])
            run_id, summary = best_run_for_campaign(task_report["campaign_id"], task_report["primary_metric"])
            if task.label == "Mode converter":
                derived = derive_mode_metrics(summary)
            elif task.label == "Splitter":
                derived = derive_splitter_metrics(summary)
            else:
                derived = derive_demux_metrics(summary)
            rows.append(
                {
                    "series": series,
                    "task_label": task.label,
                    "campaign_name": task_report["campaign_name"],
                    "campaign_id": task_report["campaign_id"],
                    "run_id": run_id,
                    **derived,
                }
            )
    return rows


def write_csv(rows: list[dict[str, str | float]]) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "series",
        "task_label",
        "campaign_name",
        "campaign_id",
        "run_id",
        "device_score",
        "insertion_loss_db",
        "return_loss_db",
        "excess_loss_db",
        "split_imbalance_db",
        "isolation_db",
        "bandwidth_fraction",
    ]
    with CSV_PATH.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def render_plot(rows: list[dict[str, str | float]]) -> None:
    plt.style.use("seaborn-v0_8-whitegrid")
    fig, axes = plt.subplots(1, 3, figsize=(13.5, 4.8), constrained_layout=True)

    mode_rows = [row for row in rows if row["task_label"] == "Mode converter"]
    splitter_rows = [row for row in rows if row["task_label"] == "Splitter"]
    demux_rows = [row for row in rows if row["task_label"] == "Demux"]

    for axis, task_rows, title, metric_key, ylabel in [
        (axes[0], mode_rows, "Mode converter", "insertion_loss_db", "Insertion loss (dB)"),
        (axes[1], splitter_rows, "Splitter", "excess_loss_db", "Excess loss (dB)"),
        (axes[2], demux_rows, "Demux", "isolation_db", "Isolation (dB)"),
    ]:
        labels = [str(row["series"]).capitalize() for row in task_rows]
        values = [float(row[metric_key]) for row in task_rows]
        bars = axis.bar(
            labels,
            values,
            color=[SERIES_COLORS[str(row["series"])] for row in task_rows],
            width=0.58,
        )
        axis.set_title(title)
        axis.set_ylabel(ylabel)
        for bar, value, row in zip(bars, values, task_rows, strict=True):
            axis.text(
                bar.get_x() + bar.get_width() / 2.0,
                value + (0.3 if metric_key != "isolation_db" else 0.1),
                f"{value:.2f}\nbw={float(row['bandwidth_fraction']):.2f}",
                ha="center",
                va="bottom",
                fontsize=8,
            )

    fig.suptitle("MEEP photonic pipeline comparison: refined vs advanced", fontsize=14)
    fig.savefig(PLOT_PATH, dpi=220, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def main() -> None:
    rows = build_rows()
    write_csv(rows)
    render_plot(rows)
    print(CSV_PATH)
    print(PLOT_PATH)


if __name__ == "__main__":
    main()
