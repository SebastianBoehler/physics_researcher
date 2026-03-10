---
name: lammps-simulation
description: LAMMPS experiment-spec and validation guidance for molecular dynamics stages. Use when creating or reviewing LAMMPS stage specs, choosing default MD parameters, checking expected input/output artifacts, or interpreting thermo-style parsed metrics in Autolab workflows.
---

# LAMMPS Simulation

- Create compact molecular-dynamics stage specs with explicit `temperature`, `steps`, `lattice_constant`, `epsilon`, `sigma`, and `cutoff`.
- Expect generated artifacts: `in.lammps`, `launch.sh`, `parameters.json`, `manifest.json`, logs, and `parsed_summary.json`.
- Validate that the parsed thermo block yields temperature, potential energy, total energy, pressure, and volume.
- Flag missing thermo tables, missing `log.lammps`, or non-success exit status as invalid.
- Prefer single-purpose LAMMPS stages that produce reusable scalar outputs for downstream mappings.
