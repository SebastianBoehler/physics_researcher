from __future__ import annotations

import csv
import json
from pathlib import Path

import matplotlib.pyplot as plt


ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT / "docs" / "benchmarks" / "assets"
CSV_PATH = OUTPUT_DIR / "openmm_lj13_baseline_comparison.csv"
PLOT_PATH = OUTPUT_DIR / "openmm_lj13_baseline_comparison.png"
RAW_REPORT_PATH = ROOT / "artifacts" / "benchmarks" / "openmm-lj13-cluster-v1" / "report.json"
BASELINE_REPORT_PATH = (
    ROOT / "artifacts" / "benchmarks" / "openmm-lj13-baselines-v1" / "report.json"
)


def load_report(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def build_rows(raw_report: dict, baseline_report: dict) -> list[dict[str, str | float | int]]:
    rows: list[dict[str, str | float | int]] = []

    raw_summary = raw_report["summary"]
    rows.append(
        {
            "series": "raw_current",
            "task_count": int(raw_summary["task_count"]),
            "mean_best_metric": float(raw_summary["mean_best_metric"]),
            "median_best_metric": float(raw_summary["median_best_metric"]),
            "mean_median_metric": float(raw_summary["mean_median_metric"]),
            "best_observed_gap_to_reference": float(raw_summary["best_observed_gap_to_reference"]),
            "top_3_mean": float(raw_summary["top_k_mean_by_size"]["top_3"]),
            "low_gap_hits_1e-05": "",
            "low_gap_rate_1e-05": "",
            "low_gap_hits_1e-06": "",
            "low_gap_rate_1e-06": "",
        }
    )

    for baseline_summary in baseline_report["summary"]["baseline_summaries"]:
        rows.append(
            {
                "series": str(baseline_summary["baseline_name"]),
                "task_count": int(baseline_summary["task_count"]),
                "mean_best_metric": float(baseline_summary["mean_best_metric"]),
                "median_best_metric": float(baseline_summary["median_best_metric"]),
                "mean_median_metric": float(baseline_summary["mean_median_metric"]),
                "best_observed_gap_to_reference": float(
                    baseline_summary["best_observed_gap_to_reference"]
                ),
                "top_3_mean": float(baseline_summary["top_k_mean_by_size"]["top_3"]),
                "low_gap_hits_1e-05": int(
                    baseline_summary["low_gap_hits_by_threshold"]["1e-05"]
                ),
                "low_gap_rate_1e-05": float(
                    baseline_summary["low_gap_rate_by_threshold"]["1e-05"]
                ),
                "low_gap_hits_1e-06": int(
                    baseline_summary["low_gap_hits_by_threshold"]["1e-06"]
                ),
                "low_gap_rate_1e-06": float(
                    baseline_summary["low_gap_rate_by_threshold"]["1e-06"]
                ),
            }
        )
    return rows


def write_csv(rows: list[dict[str, str | float | int]]) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "series",
        "task_count",
        "mean_best_metric",
        "median_best_metric",
        "mean_median_metric",
        "best_observed_gap_to_reference",
        "top_3_mean",
        "low_gap_hits_1e-05",
        "low_gap_rate_1e-05",
        "low_gap_hits_1e-06",
        "low_gap_rate_1e-06",
    ]
    with CSV_PATH.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def render_plot(rows: list[dict[str, str | float | int]]) -> None:
    plt.style.use("seaborn-v0_8-whitegrid")
    fig, (ax0, ax1) = plt.subplots(1, 2, figsize=(12.2, 4.8), constrained_layout=True)

    labels = [str(row["series"]).replace("_", "\n") for row in rows]
    x = list(range(len(rows)))
    best_values = [float(row["mean_best_metric"]) for row in rows]
    median_values = [float(row["mean_median_metric"]) for row in rows]
    top3_values = [float(row["top_3_mean"]) for row in rows]

    ax0.plot(x, best_values, marker="o", linewidth=2, color="#0f766e", label="Mean best")
    ax0.plot(x, median_values, marker="o", linewidth=2, color="#1d4ed8", label="Mean median")
    ax0.plot(x, top3_values, marker="o", linewidth=2, color="#b45309", label="Mean top-3")
    ax0.set_xticks(x, labels)
    ax0.set_yscale("log")
    ax0.set_ylabel("Gap to reference (log scale)")
    ax0.set_title("LJ13 summary statistics")
    ax0.legend(frameon=False, fontsize=9)

    baseline_rows = [row for row in rows if str(row["series"]) != "raw_current"]
    hit_labels = [str(row["series"]).replace("_", "\n") for row in baseline_rows]
    hit_x = list(range(len(baseline_rows)))
    hit_1e5 = [float(row["low_gap_rate_1e-05"]) for row in baseline_rows]
    hit_1e6 = [float(row["low_gap_rate_1e-06"]) for row in baseline_rows]

    ax1.bar([value - 0.18 for value in hit_x], hit_1e5, width=0.36, color="#2563eb", label="<= 1e-5")
    ax1.bar([value + 0.18 for value in hit_x], hit_1e6, width=0.36, color="#7c3aed", label="<= 1e-6")
    ax1.set_xticks(hit_x, hit_labels)
    ax1.set_ylabel("Hit rate")
    ax1.set_ylim(0.0, max(hit_1e5 + hit_1e6 + [0.1]) * 1.25)
    ax1.set_title("Low-gap hit rate by baseline")
    ax1.legend(frameon=False, fontsize=9)

    fig.suptitle("OpenMM LJ13 raw and baseline comparison", fontsize=14)
    fig.savefig(PLOT_PATH, dpi=220, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def main() -> None:
    rows = build_rows(load_report(RAW_REPORT_PATH), load_report(BASELINE_REPORT_PATH))
    write_csv(rows)
    render_plot(rows)
    print(CSV_PATH)
    print(PLOT_PATH)


if __name__ == "__main__":
    main()
