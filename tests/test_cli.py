import subprocess

import pytest

from pinto.cli import _commands
from pinto.project import Project


def test_cli_command_objects():
    assert len(_commands) == 2

    build = _commands["build"]
    assert build.name == "build"

    run = _commands["run"]
    assert run.name == "run"


def run_command(cmd):
    response = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if response.returncode:
        raise RuntimeError(
            f"Error encountered when running command {cmd}.\n"
            f"stderr:\n{response.stderr}\nstdout:\n{response.stdout}"
        )
    return response.stdout


@pytest.fixture(params=[None, "-p", "--project"])
def project_flag(request):
    return request.param


def test_cli_build_poetry(
    project_dir,
    project_flag,
    poetry_env_context,
    installed_project_tests,
    extras,
):
    cmd = "pinto"
    if project_flag is None:
        cmd = f"cd {project_dir} && " + cmd
    else:
        cmd += f" {project_flag} {project_dir}"
    cmd += " build"

    if extras is not None:
        cmd += " -E extra"
    run_command(cmd)

    project = Project(project_dir)
    with poetry_env_context(project._venv):
        installed_project_tests(project)

    with pytest.raises(RuntimeError) as exc_info:
        run_command(cmd + " --no-more args")
    assert "Unknown arguments ['--no-more', 'args']" in str(exc_info.value)


def test_cli_run_poetry(project_dir, project_flag, poetry_env_context):
    cmd = "pinto -v"
    if project_flag is None:
        cmd = f"cd {project_dir} && " + cmd
    else:
        cmd += f" {project_flag} {project_dir}"
    cmd += " run testme"

    try:
        output = run_command(cmd)
        assert output.rstrip().splitlines()[-1] == "can you hear me?"

        # get rid of the command and make sure this raises an error
        with pytest.raises(RuntimeError) as exc_info:
            run_command(" ".join(cmd.split(" ")[:-1]))
        msg = str(exc_info.value)
        assert "ValueError: Must provide a command to run!" in msg

        if project_flag is not None:
            with pytest.raises(RuntimeError) as exc_info:
                run_command(f"pinto -v {project_flag} /bad/path run testme")
            msg = str(exc_info.value)
            assert "ValueError: Project /bad/path does not exist" in msg
    finally:
        project = Project(project_dir)
        if project._venv.exists():
            with poetry_env_context(project._venv):
                pass
