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
The optimizer baseline suite lives at [`benchmarks/meep_photonic_devices/baselines_benchmark.json`](../../benchmarks/meep_photonic_devices/baselines_benchmark.json).
The higher-budget coarse-to-fine suite lives at [`benchmarks/meep_photonic_devices/advanced_benchmark.json`](../../benchmarks/meep_photonic_devices/advanced_benchmark.json).

- `broadband_mode_converter.json`
  Single-output screening with `device_score` dominated by transmission mean and reflection penalty.
- `splitter_screen.json`
  Two-output screening with `device_score` derived from throughput and split balance.
- `demux_screen.json`
  Two-output spectral-routing screen with `device_score` derived from low-band and high-band routing contrast.
- `advanced_*.json`
  Higher-budget three-block variants that use dB-shaped photonic metrics and a coarse-to-fine Bayesian search.

## Reported metrics

- `device_score`
  Shared benchmark metric used across all campaign types.
- `transmission_mean`
  Broadband throughput for the single-output task.
- `split_balance`
  Symmetry metric for the splitter task.
- `demux_score`
  Target-port minus leakage-port spectral routing score for the demux task.
- `insertion_loss_db`, `splitter_excess_loss_db`, `split_imbalance_db`, `demux_isolation_db`
  Literature-shaped supporting metrics for the advanced suite.
- `artifact_coverage`
  Fraction of runs with workflow metadata and validation attached.
- `workflow_stage_coverage`
  Fraction of runs that captured the expected stage set.

## Run it

```bash
AUTOLAB_ENABLE_MEEP=true uv run autolab run-benchmark --manifest-path benchmarks/meep_photonic_devices/benchmark.json --execute-inline
```

To compare `bayesian_gp` and `random_search` on the refined device family under matched budgets, run:

```bash
AUTOLAB_ENABLE_MEEP=true AUTOLAB_MEEP_BIN=/path/to/meep-python uv run autolab run-benchmark --manifest-path benchmarks/meep_photonic_devices/baselines_benchmark.json --execute-inline
```

To run the higher-budget coarse-to-fine suite and regenerate the refined-vs-advanced comparison:

```bash
AUTOLAB_ENABLE_MEEP=true AUTOLAB_MEEP_BIN=/Users/sebastianboehler/miniconda3/envs/autolab-meep/bin/python uv run autolab run-benchmark --manifest-path benchmarks/meep_photonic_devices/advanced_benchmark.json --execute-inline --max-parallel-campaigns 2
uv run python scripts/generate_meep_photonic_advanced_comparison.py
```

To compare the original suite against the latest refined rerun and regenerate the checked-in figures:

```bash
uv run python scripts/generate_meep_photonic_benchmark_plots.py
```

This writes:

- `docs/benchmarks/assets/meep_photonic_devices_signal_metrics.png`
- `docs/benchmarks/assets/meep_photonic_devices_supporting_metrics.png`
- `docs/benchmarks/assets/meep_photonic_devices_comparison.csv`
- `docs/benchmarks/assets/meep_photonic_advanced_comparison.png`
- `docs/benchmarks/assets/meep_photonic_advanced_comparison.csv`

## Current snapshot

The refined two-block search materially improves the raw task metrics over the original block-only suite:

- mode-converter `transmission_mean`: `9.66e-05` -> `1.83e-01`
- splitter `splitter_score`: `1.53e-07` -> `2.28e-03`
- demux `demux_score`: `2.54e-21` -> `2.42e-03`

Compare raw task metrics, not just `device_score`. The scoring function was recalibrated during the refined work so that demux and splitter performance would not be hidden behind a shared reflection-heavy penalty.

## Baseline comparison snapshot

With `AUTOLAB_MEEP_BIN` pointed at a Python environment that already contains `pymeep`, the refined baseline suite runs successfully and the default Bayesian optimizer outperforms random search across all three device classes:

- mode converter `device_score`: `0.5087` vs `0.4556`
- splitter `device_score`: `2.1909` vs `1.9923`
- demux `device_score`: `5.3592` vs `4.3056`

In the current local run, Bayesian also matched the previously checked-in refined-suite best results on all three tasks, while random search remained consistently worse. That makes the current photonics story much stronger than before: the framework is not only wired correctly, it now shows the same optimizer preference outside the OpenMM benchmark family.

## Advanced pipeline snapshot

The new advanced suite completed all `54/54` runs successfully with the coarse-to-fine optimizer and three-block geometry family. The report lives at `artifacts/benchmarks/meep-photonic-devices-advanced-v1/report.json`.

Do not compare the refined and advanced `device_score` values directly. The refined report predates the new dB-shaped scoring function, so the safe comparison is on derived physical metrics in `docs/benchmarks/assets/meep_photonic_advanced_comparison.csv`.

On those raw metrics, the advanced pipeline improves several quantities:

- mode-converter insertion loss: `7.37 dB` -> `5.44 dB`
- splitter excess loss: `25.80 dB` -> `12.18 dB`
- splitter imbalance: `1.17 dB` -> `0.35 dB`
- splitter bandwidth fraction: `0.22` -> `0.30`
- demux insertion loss: `22.58 dB` -> `20.31 dB`
- demux bandwidth fraction: `0.00` -> `0.21`

It also exposes the remaining weaknesses more clearly:

- mode-converter bandwidth fraction drops from `0.39` to `0.28`
- demux isolation drops from `1.08 dB` to `0.89 dB`

So the current result is useful, but still not literature-competitive. The pipeline changes improved some photonic metrics, but the search space and objective design are still constraining final device quality.

## Suggested paper angle

An honest framing is:

`An autonomous, provenance-aware workflow for reproducible photonic inverse design across multiple device classes`

The contribution is not a new electromagnetic solver. The contribution is that the loop can search distinct photonic objectives, retain all generated execution artifacts, and summarize task-specific metrics in a reproducible benchmark format.
