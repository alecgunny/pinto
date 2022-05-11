import subprocess

import pytest

from pinto.project import Project


def run_command(cmd):
    response = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if response.returncode:
        raise RuntimeError(
            f"Error encountered when running command {cmd}.\n"
            f"stderr:\n{response.stderr}\nstdout:\n{response.stdout}"
        )
    return response.stdout


def test_cli_build_poetry(
    project_dir, poetry_env_context, installed_project_tests, extras
):

    run_command(f"pinto build {project_dir}")
    project = Project(project_dir)
    with poetry_env_context(project._venv):
        installed_project_tests(project)

    with pytest.raises(RuntimeError) as excinfo:
        run_command(f"pinto build {project_dir} --no-more args")
    assert "Unknown arguments ['--no-more', 'args']" in str(excinfo)


def test_cli_run_poetry(project_dir, poetry_env_context):
    try:
        output = run_command(f"pinto -v run {project_dir} testme")
        assert output.rstrip().splitlines()[-1] == "can you hear me?"
    finally:
        project = Project(project_dir)
        if project._venv.exists():
            with poetry_env_context(project._venv):
                pass
