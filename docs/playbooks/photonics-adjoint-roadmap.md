# Photonics Adjoint Roadmap

This note turns the current photonics benchmark results into a concrete path toward literature-competitive experiments.

## Why the current pipeline will not reach SOTA by brute force

The current MEEP work in this repository is still a low-dimensional block-parameter search. Even with a better optimizer and longer budgets, that search space is too constrained to match the inverse-designed photonics literature.

What the literature is doing instead:

- freeform or topology-style design regions rather than a few geometric blocks
- adjoint gradients rather than pure black-box search
- multi-wavelength objectives optimized directly for insertion loss, crosstalk or isolation, and bandwidth
- fabrication-aware constraints such as minimum feature size and binarization
- robustness checks against fabrication variation and process corners

Primary references:

- MEEP adjoint solver and `MaterialGrid`: <https://meep.readthedocs.io/en/latest/Python_Tutorials/Adjoint_Solver/>
- broadband inverse-designed wavelength demux with low insertion loss and low crosstalk: <https://www.nature.com/articles/nphoton.2015.69>
- fabrication-constrained nanophotonic inverse design: <https://www.nature.com/articles/s41598-017-01939-2>
- integrated silicon nitride devices via inverse design with explicit fabrication benchmarking: <https://www.nature.com/articles/s41467-025-64359-1>

## Current gap

Our best current advanced MEEP run improves several physical metrics over the earlier refined suite, but it is still far from literature-level device performance.

Examples from the current checked-in comparison:

- mode-converter insertion loss: `5.44 dB`
- splitter excess loss: `12.18 dB`
- demux insertion loss: `20.31 dB`
- demux isolation: `0.89 dB`

Those numbers are useful for framework development, but they are not close to the photonics papers above.

## Target methodological shift

The next serious photonics path for this repo should be:

1. Add a dedicated adjoint-driven MEEP workflow path.
2. Move from compact block parameters to a freeform 2D design region.
3. Optimize literature-shaped metrics directly.
4. Add fabrication constraints from the first working version.
5. Run longer adjoint campaigns only after the objective and design representation are correct.

## What to build next in this repo

### Phase 1: Adjoint-capable simulator path

Goal:

Create a new MEEP workflow path for freeform inverse design rather than extending the current block parser indefinitely.

Implementation direction:

- add a new simulator task family, for example `meep_adjoint_device`
- keep it separate from the current block-based `meep_flux_scan` path
- generate an adjoint driver script that uses:
  - `meep`
  - `meep.adjoint`
  - `MaterialGrid`
  - an explicit design region
- store optimization traces as artifacts:
  - objective history
  - gradient or update history
  - final density field
  - binarized mask
  - final field snapshots

Why:

This keeps the existing benchmark path stable while allowing a fundamentally different photonics method to evolve cleanly.

### Phase 2: Literature-shaped benchmark definitions

Goal:

Define photonic tasks using the same metrics the literature uses.

Initial benchmark set:

- `adjoint_mode_converter_2d`
- `adjoint_splitter_1x2_2d`
- `adjoint_demux_1x2_2d`

Required reported metrics:

- insertion loss in dB
- return loss in dB
- crosstalk or isolation in dB
- bandwidth over threshold
- split imbalance in dB
- footprint
- success rate across seeds

Rule:

Do not use a custom aggregate `device_score` as the headline result. Keep it only as an internal optimizer convenience if needed.

### Phase 3: Fabrication-aware constraints

Goal:

Prevent the optimizer from producing non-manufacturable junk.

Minimum first version:

- minimum feature size smoothing or filtering
- projection or binarization schedule
- clipped index bounds
- symmetry constraint where appropriate

Next version:

- robustness evaluation under etch or width perturbations
- process-corner checks on the final top candidates

Why:

The fabrication-constrained literature makes clear that performance without manufacturability is not enough.

### Phase 4: Optimization strategy

Goal:

Use the right optimizer for the right level of the problem.

Recommended split:

- inner loop: adjoint gradient updates inside the MEEP run
- outer loop: Autolab campaign orchestration over seeds, objective variants, geometry footprints, and robustness settings

This means:

- do not force the current Bayesian optimizer to solve a problem that the adjoint solver should solve internally
- use the Autolab optimizer layer mainly for experiment management above the device-level optimization

### Phase 5: Long-run experiment plan

Once the adjoint path exists, run a staged experiment plan:

1. Smoke test:
   one small 2D design region, one seed, one wavelength or narrow band
2. Stable single-device benchmark:
   3 to 5 seeds, one task, fixed footprint
3. Fabrication-aware benchmark:
   same task with minimum feature size and binarization
4. Multi-task benchmark:
   mode converter, splitter, demux
5. Robustness benchmark:
   final designs under perturbations

Only after phases 2 and 3 are stable should we spend real budget on longer runs.

## Immediate next coding tasks

The next implementation steps should be:

1. Add a new driver template for MEEP adjoint optimization.
2. Add a new campaign example using a small `MaterialGrid` design region.
3. Extend artifact capture to save density maps and optimization traces.
4. Add a parser for adjoint-run summaries and dB-based metrics.
5. Create a first benchmark manifest for a single adjoint splitter task.

## Success criteria for the first serious adjoint milestone

The first milestone is not SOTA.

It is:

- a fully reproducible adjoint MEEP run in this framework
- stable artifact capture and parsing
- direct reporting of insertion loss, imbalance, and bandwidth
- at least one device class that beats the current block-based benchmark by a large margin

If that milestone works, then longer experiments become worth the budget.

## Honest expectation

This roadmap can move the repo toward the same methodological class as the inverse-designed photonics literature.

It does not guarantee SOTA.

But it is the first path in this repository that gives a realistic chance of producing photonics results that are scientifically competitive rather than only framework-interesting.
