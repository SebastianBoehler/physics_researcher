# MEEP Adjoint Devices Benchmark

This benchmark is the first freeform photonics milestone in the repository.

It does not extend the existing block-based MEEP search. Instead, it introduces a separate adjoint-driven path based on `meep.adjoint` and `MaterialGrid`.

## Current scope

The first version is intentionally small:

- one 2D splitter smoke task
- one Autolab campaign run
- a freeform design region optimized inside the MEEP driver
- artifact capture for objective history, beta schedule, gradient norms, and final density weights

## Why it exists

The block-based photonics benchmark was useful for framework evaluation, but it is not the right methodological class for literature-competitive inverse design.

This benchmark establishes the minimum working path for:

- freeform design regions
- adjoint-based optimization
- direct dB-style photonic metrics
- future fabrication-aware extensions

## Manifest

- benchmark manifest: [`benchmarks/meep_adjoint_devices/benchmark.json`](../../benchmarks/meep_adjoint_devices/benchmark.json)
- campaign: [`benchmarks/meep_adjoint_devices/campaigns/adjoint_splitter_smoke.json`](../../benchmarks/meep_adjoint_devices/campaigns/adjoint_splitter_smoke.json)

## Run it

Use a MEEP Python environment that includes `meep.adjoint` dependencies such as `autograd`.

```bash
AUTOLAB_ENABLE_MEEP=true AUTOLAB_MEEP_BIN=/Users/sebastianboehler/miniconda3/envs/autolab-meep/bin/python uv run autolab run-benchmark --manifest-path benchmarks/meep_adjoint_devices/benchmark.json --execute-inline
```

## Current execution status

The scaffold is implemented and integrated into the normal Autolab benchmark path, but the current local MEEP runtime still aborts during the adjoint phase with a native assertion:

- benchmark report: `artifacts/benchmarks/meep-adjoint-devices-v1/report.json`
- latest local campaign: `artifacts/runs/9933ef06-d9db-4045-96c6-78b17739bb9e/08f57a13-ec50-4407-bc34-a5647faad238/meep`
- native stderr symptom: `Assertion failed: (changed_materials), function step_db, file step_db.cpp, line 40.`

Autolab now records this cleanly through `adjoint_error.json` instead of collapsing into a generic parse failure, so the failure is preserved as an engine/runtime blocker with manifests, parameters, logs, and validation output intact.

The current debugging result narrows the blocker further:

- a second forward-style run with the same geometry and design-region monitors is fine
- the native abort appears when adjoint sources are active and Meep is also stepping `DftFields` monitors
- this reproduces even with a plain `Ez` DFT field monitor, so the issue is not specific to the design-region gradient extraction code

## What to look for

The first success criteria are:

- the run completes end-to-end through the normal Autolab campaign path
- `adjoint_results.json` is captured as an artifact
- the parser reports:
  - `splitter_excess_loss_db`
  - `split_imbalance_db`
  - `splitter_bandwidth_fraction`
  - `adjoint_final_objective`
  - `adjoint_iteration_count`
  - `design_fill_fraction`
  - `design_binary_fraction`

This benchmark should currently be treated as a methodological smoke test, not a literature-facing photonic result.

At the moment, the practical next step is to resolve the native MEEP adjoint runtime issue in this environment rather than scale this benchmark up.
