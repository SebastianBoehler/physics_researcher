from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from autolab.core.settings import Settings


class BenchmarkReportService:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def list_reports(self) -> list[dict[str, Any]]:
        reports_root = self._settings.app.artifact_root / "benchmarks"
        if not reports_root.exists():
            return []
        entries: list[dict[str, Any]] = []
        for report_path in sorted(reports_root.rglob("report.json")):
            try:
                payload = json.loads(report_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            summary = payload.get("summary", {})
            benchmark_name = str(payload.get("benchmark_name", report_path.parent.name))
            entries.append(
                {
                    "benchmark_name": benchmark_name,
                    "description": str(payload.get("description", "")),
                    "paper_hypothesis": str(payload.get("paper_hypothesis", "")),
                    "primary_metric": str(payload.get("primary_metric", "")),
                    "generated_at": str(payload.get("generated_at", "")),
                    "report_path": str(report_path),
                    "manifest_path": self._manifest_path_for(benchmark_name),
                    "task_count": int(summary.get("task_count", len(payload.get("task_reports", [])))),
                    "summary": summary,
                }
            )
        return sorted(entries, key=lambda entry: entry["generated_at"], reverse=True)

    def _manifest_path_for(self, benchmark_name: str) -> str | None:
        manifest_path = Path("benchmarks") / benchmark_name / "benchmark.json"
        if manifest_path.exists():
            return str(manifest_path)
        return None
