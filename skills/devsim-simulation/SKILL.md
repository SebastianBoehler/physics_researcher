---
name: devsim-simulation
description: DEVSIM experiment-spec and validation guidance for semiconductor device stages. Use when creating DEVSIM stage defaults, reviewing generated driver scripts, checking device-output artifacts, or coupling DEVSIM outputs into downstream Autolab workflows.
---

# DEVSIM Simulation

- Create device-stage specs with explicit device name, bias, and any contact or region assumptions.
- Expect generated artifacts: `run_devsim.py`, manifests, logs, and `devsim_results.json`.
- Validate that current or device-response metrics are present and that execution completed successfully.
- Treat missing device result JSON as invalid.
- Use DEVSIM stages when device-state outputs need to feed photonic or systems-level downstream stages.
