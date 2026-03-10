from __future__ import annotations

import json
from pathlib import Path
from statistics import median

import matplotlib.pyplot as plt


ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT / "docs" / "benchmarks" / "assets"
OUTPUT_PATH = OUTPUT_DIR / "openmm_lj_pair_comparison.png"


def load_report(relative_path: str) -> dict:
    path = ROOT / relative_path
    return json.loads(path.read_text())


def build_summary(report: dict, label: str) -> dict[str, float | str]:
    task_reports = report["task_reports"]
    best_metrics = [float(task["best_metric"]) for task in task_reports]
    return {
        "label": label,
        "task_count": len(task_reports),
        "best": min(best_metrics),
        "median": median(best_metrics),
        "worst": max(best_metrics),
    }


def main() -> None:
    reports = [
        build_summary(load_report("artifacts/benchmarks/openmm-lj-pair-v1/report.json"), "8-run\nsingle seed"),
        build_summary(
            load_report("artifacts/benchmarks/openmm-lj-pair-longrun-v1/report.json"),
            "64-run\n3 seeds",
        ),
        build_summary(
            load_report("artifacts/benchmarks/openmm-lj-pair-refined-multiseed-v1/report.json"),
            "128-run refined\n6 seeds",
        ),
    ]

    refined = load_report("artifacts/benchmarks/openmm-lj-pair-refined-multiseed-v1/report.json")
    refined_seed_names = [task["campaign_name"].replace("openmm-lj-pair-refined-seed-", "seed ") for task in refined["task_reports"]]
    refined_seed_values = [float(task["best_metric"]) for task in refined["task_reports"]]

    plt.style.use("seaborn-v0_8-whitegrid")
    fig, (ax0, ax1) = plt.subplots(1, 2, figsize=(12, 4.8), constrained_layout=True)

    labels = [str(item["label"]) for item in reports]
    best_values = [float(item["best"]) for item in reports]
    median_values = [float(item["median"]) for item in reports]
    worst_values = [float(item["worst"]) for item in reports]

    x = range(len(labels))
    ax0.plot(x, best_values, marker="o", linewidth=2, color="#0f766e", label="Best")
    ax0.plot(x, median_values, marker="o", linewidth=2, color="#1d4ed8", label="Median")
    ax0.plot(x, worst_values, marker="o", linewidth=2, color="#b45309", label="Worst")
    ax0.set_xticks(list(x), labels)
    ax0.set_yscale("log")
    ax0.set_ylabel("Energy gap to reference (log scale)")
    ax0.set_title("Benchmark family comparison")
    ax0.legend(frameon=False)

    refined_positions = range(len(refined_seed_names))
    ax1.scatter(refined_positions, refined_seed_values, color="#7c3aed", s=42, zorder=3)
    ax1.plot(refined_positions, refined_seed_values, color="#c4b5fd", linewidth=1.5, zorder=2)
    ax1.set_xticks(list(refined_positions), refined_seed_names, rotation=25, ha="right")
    ax1.set_yscale("log")
    ax1.set_ylabel("Best energy gap to reference (log scale)")
    ax1.set_title("Refined multi-seed consistency")

    fig.suptitle("OpenMM Lennard-Jones benchmark convergence", fontsize=14)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUTPUT_PATH, dpi=220, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print(OUTPUT_PATH)


if __name__ == "__main__":
    main()
