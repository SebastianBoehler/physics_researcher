# Simulator Integration Playbook

Real simulator backends are isolated behind `SimulatorBackend`.

## LAMMPS

- Templates live in `integrations/lammps/templates`.
- The `LammpsSimulator` adapter prepares typed inputs and command construction but is disabled by default.
- Enable it with `AUTOLAB_ENABLE_LAMMPS=true` and provide engine binaries through your own runtime image or cluster environment.

## OpenMM

- Templates live in `integrations/openmm/templates`.
- The `OpenMMSimulator` scaffold mirrors the LAMMPS adapter shape for future extension.

## Contract requirements

Every adapter must satisfy the shared contract tests in `tests/integration/test_simulator_contracts.py`.
