# MEEP Photonic Devices Benchmark

This benchmark extends the repository's original waveguide screen into a small device suite with three block-based photonic tasks:

- broadband mode conversion
- two-port power splitting
- two-port spectral routing

## Why this benchmark exists

The existing MEEP integration already supports real simulator execution, artifact capture, and optimizer-driven iteration. What it lacked was task diversity. A single transmission monitor is enough to regression-test the loop, but it is weak evidence for photonic inverse design.

This suite broadens the evaluation while staying honest about the current device model:

- it is still a block-parameter screening workflow, not full adjoint topology optimization
- all tasks run through the same MEEP adapter and provenance path
- task-specific figures of merit are derived from port-aware monitor spectra

## Included tasks

The suite manifest lives at [`benchmarks/meep_photonic_devices/benchmark.json`](../../benchmarks/meep_photonic_devices/benchmark.json).

- `broadband_mode_converter.json`
  Single-output screening with `device_score` dominated by transmission mean and reflection penalty.
- `splitter_screen.json`
  Two-output screening with `device_score` derived from throughput and split balance.
- `demux_screen.json`
  Two-output spectral-routing screen with `device_score` derived from low-band and high-band routing contrast.

## Reported metrics

- `device_score`
  Shared benchmark metric used across all campaign types.
- `transmission_mean`
  Broadband throughput for the single-output task.
- `split_balance`
  Symmetry metric for the splitter task.
- `demux_score`
  Target-port minus leakage-port spectral routing score for the demux task.
- `artifact_coverage`
  Fraction of runs with workflow metadata and validation attached.
- `workflow_stage_coverage`
  Fraction of runs that captured the expected stage set.

## Run it

```bash
AUTOLAB_ENABLE_MEEP=true uv run autolab run-benchmark --manifest-path benchmarks/meep_photonic_devices/benchmark.json --execute-inline
```

To compare the original suite against the latest refined rerun and regenerate the checked-in figures:

```bash
uv run python scripts/generate_meep_photonic_benchmark_plots.py
```

This writes:

- `docs/benchmarks/assets/meep_photonic_devices_signal_metrics.png`
- `docs/benchmarks/assets/meep_photonic_devices_supporting_metrics.png`
- `docs/benchmarks/assets/meep_photonic_devices_comparison.csv`

## Current snapshot

The refined two-block search materially improves the raw task metrics over the original block-only suite:

- mode-converter `transmission_mean`: `9.66e-05` -> `1.83e-01`
- splitter `splitter_score`: `1.53e-07` -> `2.28e-03`
- demux `demux_score`: `2.54e-21` -> `2.42e-03`

Compare raw task metrics, not just `device_score`. The scoring function was recalibrated during the refined work so that demux and splitter performance would not be hidden behind a shared reflection-heavy penalty.

## Suggested paper angle

An honest framing is:

`An autonomous, provenance-aware workflow for reproducible photonic inverse design across multiple device classes`

The contribution is not a new electromagnetic solver. The contribution is that the loop can search distinct photonic objectives, retain all generated execution artifacts, and summarize task-specific metrics in a reproducible benchmark format.
