from pathlib import Path

from autolab.simulators.core.runner import ProcessRunner


def test_resolve_command_preserves_explicit_symlink_path(tmp_path: Path) -> None:
    real_executable = tmp_path / "real-python"
    real_executable.write_text("#!/usr/bin/env bash\n", encoding="utf-8")
    symlink = tmp_path / "venv-python"
    symlink.symlink_to(real_executable)

    resolved = ProcessRunner().resolve_command([str(symlink), "run_openmm.py"])

    assert resolved[0] == str(symlink.absolute())
    assert resolved[1:] == ["run_openmm.py"]
