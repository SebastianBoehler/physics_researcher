# OpenMM Lennard-Jones Cluster Benchmark

This benchmark is the next step after the two-atom Lennard-Jones equilibrium check.

The pair benchmark is useful because it shows that the loop can recover a smooth analytic minimum with very small numerical error. It does not say much about scaling, local minima, or many-body search.

The cluster benchmark changes that:

- the search space grows to `3N-6` physically relevant coordinates
- the objective is the total many-body Lennard-Jones energy
- the landscape contains many local minima
- failure to reach the reference is now scientifically informative rather than automatically a bug

## First target

The current repository ships a first `LJ13` benchmark:

- benchmark manifest: [benchmark.json](../../benchmarks/openmm_lj13_cluster/benchmark.json)
- benchmark campaign: [openmm_lj13_cluster_seed_31.json](../../benchmarks/openmm_lj13_cluster/campaigns/openmm_lj13_cluster_seed_31.json)

`LJ13` is the classic 13-atom Lennard-Jones cluster. The accepted global minimum energy is used as the reference and the report tracks `energy_gap_to_reference`.

The benchmark fixes rigid-body redundancy by:

- placing atom 0 at the origin
- constraining atom 1 to the x-axis
- constraining atom 2 to the xy-plane

That leaves the optimizer with the physically relevant `3N-6 = 33` search dimensions.

## Run it

```bash
AUTOLAB_ENABLE_OPENMM=true uv run autolab run-benchmark benchmarks/openmm_lj13_cluster/benchmark.json --execute-inline
```

This writes a report to `artifacts/benchmarks/openmm-lj13-cluster-v1/report.json`.

To compare optimizer baselines on the same raw `LJ13` landscape, run:

```bash
AUTOLAB_ENABLE_OPENMM=true uv run autolab run-benchmark --manifest-path benchmarks/openmm_lj13_baselines/benchmark.json --execute-inline
uv run python scripts/generate_openmm_lj13_baseline_artifacts.py
```

This writes:

- `artifacts/benchmarks/openmm-lj13-baselines-v1/report.json`
- `docs/benchmarks/assets/openmm_lj13_baseline_comparison.csv`
- `docs/benchmarks/assets/openmm_lj13_baseline_comparison.png`

## How to interpret it

This is intentionally a harder benchmark than the pair problem.

- small gap: the optimizer found a configuration near the accepted global minimum
- large gap: the optimizer likely got trapped in a local minimum or did not scale well to the higher-dimensional landscape
- high cross-seed variance: the method is sensitive to initialization

If the current optimizer struggles here, that is not a contradiction of the pair result. It means the repository has crossed from smooth local recovery into a genuine global-optimization benchmark.

The current checked-in baseline comparison supports a narrower but more useful claim:

- `bayesian_gp` is better than `random_search` on average under the current raw `LJ13` budget
- both optimizers can still reach the accepted minimum in the best case
- hit-rate and top-k summaries are more informative than the mean over all raw trajectories
