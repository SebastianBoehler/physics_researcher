# Example Prompts and Problems

This file is the short list of prompts to try against the current repository. It is split into:

- prompts that exercise the current real-adapter workflow surface
- prompts that should drive the next round of iteration

## Runnable now

### 1. Real-adapter demo run

Use with [demo_campaign.json](../campaigns/demo_campaign.json).

```text
Run a real-adapter demo campaign through the LAMMPS path. If the binary is unavailable, inspect the generated workdir, manifest, and validation metadata instead of treating the run as opaque.
```

What this stresses:

- full campaign stepping loop
- real simulator adapter generation
- missing-binary failure handling
- persistence of stage artifacts and manifests

## Prompt templates for operator testing

These are useful when you want to watch the agents and orchestration layer rather than just submit a static campaign JSON.

### Candidate rationale prompt

```text
Explain why the proposed batch is reasonable using only campaign objectives, constraints, and prior run history. Do not speculate about simulator internals.
```

### Critic summary prompt

```text
Compare the last five runs, identify the most likely promising region in parameter space, and state whether the next batch should explore or exploit.
```

### Report-writing prompt

```text
Write a short run report for each completed simulation and a campaign summary after every batch. Highlight feasible best-so-far candidates.
```

## Next iteration prompts

These are not fully implemented today, but they are the right problems to use when extending the repository.

### 6. Failure recovery campaign

```text
Inject transient failures into 20 percent of runs, retry only transient failures, and summarize failure classes at the end of the campaign.
```

Why it matters:

- needs campaign-level failure injection hooks
- exercises retry and classification more directly

### 7. Early stopping by diminishing returns

```text
Stop the campaign early if the last three completed runs improve conductivity by less than 2 percent, and explain why the stop condition was triggered.
```

Why it matters:

- needs explicit stop-rule configuration
- pushes critic-driven workflow control

### 8. Robustness over peak performance

```text
Search for robust candidates, not just high-performing ones. Prefer regions where small parameter changes do not sharply reduce stability.
```

Why it matters:

- needs derived robustness metrics
- suggests new evaluation logic beyond single-point objective values

### 9. Seeded versus unseeded comparison

```text
Warm-start the optimizer with four hand-picked candidates, then compare the seeded campaign against an unseeded baseline after the same budget.
```

Why it matters:

- needs candidate seeding support at campaign start
- good benchmark for optimizer initialization

### 10. Multi-objective tradeoff analysis

```text
Maximize conductivity while minimizing cost and explain the tradeoff frontier after each batch.
```

Why it matters:

- current transport models allow multiple objectives
- the working optimizer still behaves as single-objective-first and should be extended before treating this as production-ready

### 11. Materials-to-photonics workflow

Use with [qe_to_meep_photonic_screen.json](../campaigns/qe_to_meep_photonic_screen.json).

```text
Run a cross-simulator workflow that uses Quantum ESPRESSO outputs to parameterize a MEEP photonics stage. Explain every transferred parameter and keep the workdir manifests auditable.
```

Why it matters:

- demonstrates typed stage handoff
- exercises artifact generation across two simulators
- shows interdisciplinary value beyond a single engine

### 12. Electronic-to-atomistic bootstrap workflow

Use with [qe_to_lammps_forcefield_bootstrap.json](../campaigns/qe_to_lammps_forcefield_bootstrap.json).

```text
Run a workflow that uses Quantum ESPRESSO outputs to bootstrap a downstream LAMMPS stage. Explain which electronic-structure quantities were transferred, which LAMMPS parameters changed as a result, and whether the provenance manifest is sufficient to reproduce the handoff.
```

Why it matters:

- demonstrates a practical multiple-simulator bridge for materials work
- makes a registered stage mapping visible to the operator
- fits the “agent proposes, adapters execute, parser returns evidence” pattern well

### 13. Multiscale materials workflow

Use with [lammps_to_elmer_multiscale_screen.json](../campaigns/lammps_to_elmer_multiscale_screen.json).

```text
Run a multiscale workflow that starts in LAMMPS and maps into Elmer. Summarize both the atomistic outputs and the continuum assumptions created from them.
```

Why it matters:

- demonstrates explicit stage mappings
- tests stage-by-stage provenance capture
- shows how downstream continuum solvers can consume upstream atomistic results

### 14. Molecular relaxation workflow

Use with [openmm_protein_relaxation.json](../campaigns/openmm_protein_relaxation.json).

```text
Run an OpenMM-based molecular relaxation screen and explain which candidates appear most structurally stable by the end of the minimization. Report the generated driver, parsed energy terms, and which parameter region should be explored next.
```

Why it matters:

- gives the repo a concrete protein or binder-adjacent example without pretending to solve full drug discovery
- shows how the same orchestration layer can drive molecular simulation rather than only materials engines
- is a good starting point for future docking or sequence-design extensions

### 15. Standalone photonics inverse screen

Use with [meep_waveguide_inverse_screen.json](../campaigns/meep_waveguide_inverse_screen.json).

```text
Run a standalone MEEP screen over waveguide geometry and refractive index. Summarize which shapes maximize transmission while keeping the generated driver and spectrum summaries auditable.
```

Why it matters:

- demonstrates a direct geometry-optimization loop in a single simulator
- is a good template for later inverse-design workflows
- keeps the example domain visibly different from atomistic materials work

### 16. Paper benchmark workflow

Use with [benchmark.json](../../benchmarks/meep_inverse_design/benchmark.json).

```text
Run the MEEP inverse-design benchmark suite, compare low-resolution, high-resolution, and QE to MEEP transfer tasks, and write a benchmark report that summarizes best metric, mean metric, success rate, artifact coverage, and workflow-stage coverage.
```

Why it matters:

- maps directly to a paper-oriented evaluation
- uses the same API and CLI surface as normal campaigns
- gives the agent a repeatable benchmark target rather than an ad hoc prompt

### 17. Cross-simulator verification workflow

Use with [cross_simulator_transfer_verification.json](../campaigns/cross_simulator_transfer_verification.json).

```text
Run a verification-focused workflow and confirm that parameter echoes, mapping tolerances, artifact completeness, and provenance manifests are all present for every stage.
```

Why it matters:

- treats the simulator boundary as something to verify, not just execute
- makes cross-stage transfer assumptions testable
- provides a strong operator example for scientific reproducibility

### 18. Lennard-Jones cluster benchmark

Use with [benchmark.json](../../benchmarks/openmm_lj13_cluster/benchmark.json).

```text
Run the OpenMM LJ13 cluster benchmark, report the best energy gap to the accepted global minimum, and explain whether the optimizer appears to converge, stall, or get trapped in local minima across the search history.
```

Why it matters:

- upgrades the existing pair benchmark into a genuine many-body landscape
- exposes optimizer scaling behavior in `3N-6` dimensions
- is scientifically useful even when the current optimizer fails, because the failure mode is the result

## Suggested order

If you want a disciplined progression, run them in this order:

1. real-adapter demo run
2. molecular relaxation workflow
3. standalone photonics inverse screen
4. materials-to-photonics workflow
5. electronic-to-atomistic bootstrap workflow
6. multiscale materials workflow
7. paper benchmark workflow
8. cross-simulator verification workflow
9. Lennard-Jones cluster benchmark
10. failure recovery campaign
11. early stopping by diminishing returns

## CLI examples

```bash
uv run autolab create-campaign examples/campaigns/demo_campaign.json
uv run autolab create-campaign examples/campaigns/openmm_protein_relaxation.json
uv run autolab create-campaign examples/campaigns/meep_waveguide_inverse_screen.json
uv run autolab create-campaign examples/campaigns/qe_to_meep_photonic_screen.json
uv run autolab create-campaign examples/campaigns/qe_to_lammps_forcefield_bootstrap.json
uv run autolab create-campaign examples/campaigns/cross_simulator_transfer_verification.json
uv run autolab run-benchmark benchmarks/meep_inverse_design/benchmark.json --execute-inline
uv run autolab run-benchmark benchmarks/openmm_lj13_cluster/benchmark.json --execute-inline
```
