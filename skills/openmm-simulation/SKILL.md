---
name: openmm-simulation
description: OpenMM experiment-spec and validation guidance for Python-driven molecular simulation stages. Use when creating OpenMM stage defaults, reviewing generated Python drivers, checking result JSON outputs, or integrating lightweight OpenMM stages into Autolab workflows.
---

# OpenMM Simulation

- Prefer compact, deterministic stage specs with explicit temperature, step count, and force parameters.
- Expect generated artifacts: `run_openmm.py`, `launch.sh`, manifests, logs, and `openmm_results.json`.
- Validate that potential energy, kinetic energy, and temperature are present in the parsed result.
- Treat missing result JSON or failed execution as invalid.
- Use OpenMM stages when a Python-native simulator path is a good fit for local experimentation.
