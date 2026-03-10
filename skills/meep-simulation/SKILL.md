---
name: meep-simulation
description: MEEP experiment-spec and validation guidance for photonics stages. Use when defining MEEP geometry, source, monitor, and spectrum settings, reviewing generated Python driver artifacts, or checking parsed transmission and reflection outputs in Autolab workflows.
---

# MEEP Simulation

- Create stage specs with explicit geometry dimensions, refractive index, `resolution`, `fcen`, `df`, `nfreq`, and runtime horizon.
- Expect generated artifacts: `run_meep.py`, `launch.sh`, manifests, logs, and `meep_results.json`.
- Validate that frequency, transmission, and reflection arrays are present and non-empty.
- Treat missing spectrum JSON or empty monitor outputs as invalid or partial.
- Use MEEP stages when downstream decisions depend on photonic response rather than free-form script authoring.
