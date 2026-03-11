from __future__ import annotations

import json
from pathlib import Path

import matplotlib.pyplot as plt


ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT / "docs" / "benchmarks" / "assets"
COMPARISON_OUTPUT_PATH = OUTPUT_DIR / "thermoelectric_measurement_comparison.png"
PROGRESSION_OUTPUT_PATH = OUTPUT_DIR / "thermoelectric_measurement_progression.png"
REPORT_PATH = ROOT / "artifacts" / "benchmarks" / "thermoelectric-measurement-v1" / "report.json"


def load_report() -> dict:
    return json.loads(REPORT_PATH.read_text(encoding="utf-8"))


def main() -> None:
    report = load_report()
    task_reports = report["task_reports"]
    labels = [task["campaign_name"].replace("thermoelectric-", "").replace("-screen", "") for task in task_reports]
    best_values = [float(task["best_metric"]) for task in task_reports]
    mean_values = [float(task["mean_metric"]) for task in task_reports]
    coverage_values = [float(task["artifact_coverage"]) for task in task_reports]
    stage_coverage_values = [float(task["workflow_stage_coverage"]) for task in task_reports]

    plt.style.use("seaborn-v0_8-whitegrid")
    fig, (ax0, ax1) = plt.subplots(1, 2, figsize=(12, 4.8), constrained_layout=True)

    positions = range(len(labels))
    ax0.bar(
        [position - 0.18 for position in positions],
        best_values,
        width=0.36,
        color="#0f766e",
        label="Best power factor",
    )
    ax0.bar(
        [position + 0.18 for position in positions],
        mean_values,
        width=0.36,
        color="#1d4ed8",
        label="Mean power factor",
    )
    ax0.set_xticks(list(positions), labels)
    ax0.set_ylabel("Power factor")
    ax0.set_title("Measured power-factor comparison")
    ax0.legend(frameon=False)

    ax1.plot(positions, coverage_values, marker="o", linewidth=2, color="#b45309", label="Artifact coverage")
    ax1.plot(
        positions,
        stage_coverage_values,
        marker="o",
        linewidth=2,
        color="#7c3aed",
        label="Workflow-stage coverage",
    )
    ax1.set_xticks(list(positions), labels)
    ax1.set_ylim(0.0, 1.05)
    ax1.set_ylabel("Coverage")
    ax1.set_title("Reproducibility coverage")
    ax1.legend(frameon=False)

    fig.suptitle("Thermoelectric measurement benchmark", fontsize=14)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    fig.savefig(COMPARISON_OUTPUT_PATH, dpi=220, bbox_inches="tight", facecolor="white")
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(8.8, 4.8), constrained_layout=True)
    colors = ["#0f766e", "#1d4ed8", "#b45309"]
    for index, task in enumerate(task_reports):
        metric_history = [float(value) for value in task.get("metric_history", [])]
        best_history = [float(value) for value in task.get("best_so_far_history", [])]
        iterations = list(range(1, len(metric_history) + 1))
        if not iterations:
            continue
        ax.plot(
            iterations,
            metric_history,
            marker="o",
            linewidth=1.5,
            alpha=0.45,
            color=colors[index % len(colors)],
            label=f"{labels[index]} run metric",
        )
        ax.plot(
            iterations,
            best_history,
            marker="o",
            linewidth=2.4,
            color=colors[index % len(colors)],
            label=f"{labels[index]} best so far",
        )
    ax.set_xlabel("Iteration")
    ax.set_ylabel("Power factor")
    ax.set_title("Run-by-run improvement over iteration")
    ax.legend(frameon=False, ncol=2)
    fig.savefig(PROGRESSION_OUTPUT_PATH, dpi=220, bbox_inches="tight", facecolor="white")
    plt.close(fig)

    print(COMPARISON_OUTPUT_PATH)
    print(PROGRESSION_OUTPUT_PATH)


if __name__ == "__main__":
    main()
