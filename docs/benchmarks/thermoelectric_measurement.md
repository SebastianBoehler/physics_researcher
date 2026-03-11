# Thermoelectric Measurement Benchmark

This benchmark evaluates the new Phase-1 experimental loop path:

1. propose thermoelectric candidate parameters
2. generate a fabrication protocol
3. ingest a measurement CSV
4. derive measured metrics
5. feed measured `power_factor` back into the loop

## What this benchmark is for

- verifying that manual-to-measurement workflow stages behave like first-class Autolab stages
- checking that measured metrics reach the optimizer and run summaries
- comparing broader versus tighter search spaces under the same workflow contract
- measuring artifact and workflow-stage coverage for a pseudo-experimental loop

## What this benchmark is not

The CSV measurement values are generated deterministically inside the `csv_measurement` stage. This is an orchestration and data-plumbing benchmark, not a wet-lab validation result.

## Benchmark suite

The suite manifest lives at [`benchmarks/thermoelectric_measurement/benchmark.json`](../../benchmarks/thermoelectric_measurement/benchmark.json).

Included tasks:

- `thermoelectric_broad_screen.json`
  Broad thermoelectric search space with weak prior knowledge.
- `thermoelectric_focused_screen.json`
  Tighter search around stronger synthetic candidates.
- `thermoelectric_high_pf_screen.json`
  High-power-factor prior with stricter conductivity filtering.

## Reported metrics

- `best_metric`
  Best observed measured `power_factor` within a task.
- `mean_metric`
  Mean measured `power_factor` across completed runs.
- `artifact_coverage`
  Fraction of runs with workflow metadata, stage results, and validation.
- `workflow_stage_coverage`
  Fraction of runs that recorded every expected stage.

## How to run

Start the API, then run:

```bash
uv run autolab run-benchmark benchmarks/thermoelectric_measurement/benchmark.json --execute-inline
uv run python scripts/generate_thermoelectric_benchmark_plots.py
```

This writes:

- `artifacts/benchmarks/thermoelectric-measurement-v1/report.json`
- `docs/benchmarks/assets/thermoelectric_measurement_comparison.png`
- `docs/benchmarks/assets/thermoelectric_measurement_progression.png`

## Current local result

The current local benchmark completed all 18/18 runs successfully across the three tasks, with `artifact_coverage = 1.0` and `workflow_stage_coverage = 1.0` for every task.

Task-level results:

| Task | Best power factor | Mean power factor | Artifact coverage | Workflow-stage coverage |
| --- | ---: | ---: | ---: | ---: |
| broad | `0.0027871945048813184` | `0.002396537237484774` | `1.0` | `1.0` |
| focused | `0.003036841520352007` | `0.0027825692303721527` | `1.0` | `1.0` |
| high-pf | `0.0033693258370941503` | `0.0032379005513877295` | `1.0` | `1.0` |

That monotonic improvement is the useful benchmark signal here: tighter prior knowledge improved measured-loop outcomes without sacrificing reproducibility metadata.

![Thermoelectric benchmark comparison](assets/thermoelectric_measurement_comparison.png)

![Thermoelectric benchmark progression](assets/thermoelectric_measurement_progression.png)
