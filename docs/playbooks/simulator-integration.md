# Simulator Integration Playbook

Real simulator backends are isolated behind `SimulatorBackend` and the stage-based workflow adapter layer.

## LAMMPS

- Templates live in `packages/simulators/src/autolab/simulators/templates/lammps`.
- The `LammpsSimulator` adapter generates `in.lammps`, optional copied `read_data` inputs, `launch.sh`, manifests, logs, and parsed summaries.
- Supported first-pass controls include:
  - `ensemble`: `nve`, `nvt`, or `npt`
  - `thermo_frequency`
  - `timestep`
  - `dump_frequency`
  - `neighbor_skin`
  - `start_temperature` / `target_temperature`
  - `pressure_target`
- To seed a run from an existing LAMMPS data file, set `candidate.metadata["lammps_data_file"]` and the adapter will copy it into the stage workdir and render `read_data`.
- Enable it with `AUTOLAB_ENABLE_LAMMPS=true` and provide the binary via `AUTOLAB_LAMMPS_BIN` when needed.
- A simulator-enabled worker profile is included:

```bash
docker compose --profile lammps build worker-lammps
docker compose --profile lammps run --rm --no-deps worker-lammps uv run pytest tests/integration/test_real_simulator_execution.py -k lammps
```

- The same flow is available through `make test-lammps`.

## MEEP

- Templates live in `packages/simulators/src/autolab/simulators/templates/meep`.
- The `MeepSimulator` adapter generates a Python driver, launch script, manifests, logs, and spectrum summary JSON.
- Enable it with `AUTOLAB_ENABLE_MEEP=true`. By default it uses the configured Python interpreter, so the `meep` Python module must be installed in that environment.
- If MEEP lives in a separate conda environment, point the adapter at that interpreter with `AUTOLAB_MEEP_BIN=/path/to/env/bin/python`.
- The new adjoint workflow also needs `meep.adjoint` dependencies in that interpreter. In the current local setup this required installing `autograd` into the `autolab-meep` environment.
- The adjoint path now emits `adjoint_error.json` when the native driver aborts before writing `adjoint_results.json`. This keeps engine/runtime failures distinguishable from parser failures in benchmark reports.

## Quantum ESPRESSO, OpenMM, Elmer, and DEVSIM

- Each simulator now has a typed adapter scaffold with real file generation and parser hooks.
- Relevant environment variables:
  - `AUTOLAB_QE_PW_BIN`
  - `AUTOLAB_OPENMM_BIN`
  - `AUTOLAB_ELMER_SOLVER_BIN`
  - `AUTOLAB_DEVSIM_BIN`
- These adapters surface missing binaries as structured execution failures with captured logs and manifests.

## Verification checklist

- Confirm `manifest.json` exists for every stage.
- Confirm `parameters.json` and `environment.json` match the intended spec.
- Confirm `stdout.log` and `stderr.log` are present.
- Confirm `parsed_summary.json` exists for successfully parsed stages.
- Confirm stage mappings are recorded in provenance for dependent stages.
- For LAMMPS specifically, confirm:
  - `log.lammps` exists
  - at least one thermo section and one thermo row were parsed
  - the parsed metadata records `completion_detected=true`
  - copied `read_data` inputs are listed in `manifest.json` when data-file mode is used

## Contract requirements

Every adapter must satisfy the shared contract tests in `tests/integration/test_simulator_contracts.py`.
