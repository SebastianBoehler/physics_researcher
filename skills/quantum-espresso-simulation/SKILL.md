---
name: quantum-espresso-simulation
description: Quantum ESPRESSO experiment-spec and validation guidance for electronic-structure stages. Use when defining SCF inputs, checking QE workdir artifacts, reviewing convergence expectations, or mapping QE outputs into downstream Autolab stages.
---

# Quantum ESPRESSO Simulation

- Create SCF-focused specs with explicit `ecutwfc`, `conv_thr`, lattice parameter, `prefix`, `pseudo_dir`, and `outdir`.
- Expect generated artifacts: `qe.in`, `launch.sh`, manifests, logs, and parsed summaries.
- Validate that the output contains a total-energy line and explicit convergence text when available.
- Treat missing total energy or failed execution as invalid.
- Use QE stages primarily for upstream property extraction and controlled stage-to-stage mappings.
