# MEEP Inverse-Design Benchmark

This benchmark is the most paper-ready evaluation track for the current repository because it matches the existing architecture closely:

- real simulator adapter already exists for MEEP
- artifact generation, manifests, and parsed summaries are already first-class
- the tasks can be single-stage or cross-simulator without changing orchestration
- the benchmark can measure both optimization quality and scientific reproducibility

## Paper angle

Suggested paper framing:

`An agentic, provenance-aware workflow system for reproducible photonic inverse design`

The claim is not that the repository invents a new photonics solver. The claim is that it provides a useful autonomous experimentation loop over real simulators:

1. propose candidate geometry or workflow settings
2. generate executable artifacts deterministically
3. run the simulator with tracked provenance
4. parse and validate outputs
5. iterate with an optimization or agent policy

## Benchmark suite

The suite manifest lives at [`benchmarks/meep_inverse_design/benchmark.json`](/Users/sebastianboehler/Documents/GitHub/physics_researcher/benchmarks/meep_inverse_design/benchmark.json).

Included tasks:

- `waveguide_lowres_screen.json`
  Fast standalone MEEP screen for cheap iteration.
- `waveguide_highres_screen.json`
  Higher-resolution MEEP screen for quality-focused comparisons.
- `qe_to_meep_transfer_screen.json`
  Cross-simulator workflow that tests whether upstream electronic-structure information improves downstream photonic search or at least produces auditable transfer behavior.

## Recommended evaluation metrics

- `best_metric`
  Best `transmission_peak` reached within the fixed budget.
- `mean_metric`
  Mean objective value over completed runs.
- `success_rate`
  Fraction of runs with status `succeeded`.
- `artifact_coverage`
  Fraction of runs containing workflow metadata, stage results, and validation blocks.
- `workflow_stage_coverage`
  Fraction of runs that recorded all expected stages.
- `time_to_best`
  Iteration index at which the best objective first appears.

## Baselines

Baseline comparisons that fit the current codebase:

- random candidate generation under the same budget
- default optimizer-only loop
- standalone MEEP versus QE -> MEEP workflow

## Suggested figures

- objective versus iteration for each benchmark task
- success-rate and artifact-coverage bar chart
- best standalone MEEP design versus best QE -> MEEP design
- provenance diagram showing artifacts produced per stage

## How to run

Use the CLI runner:

```bash
uv run autolab run-benchmark benchmarks/meep_inverse_design/benchmark.json --execute-inline
```

This writes a machine-readable summary under `artifacts/benchmarks/<benchmark-name>/report.json`.

## What makes this benchmark publishable

- It exercises a real simulator rather than a synthetic environment.
- It measures autonomous workflow quality, not just raw model accuracy.
- It produces auditable artifacts and provenance for every trial.
- It naturally supports ablations on optimizer choice, workflow transfer, and failure handling.
