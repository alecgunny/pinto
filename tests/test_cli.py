import shutil
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


def run_command(cmd, cwd):
    response = subprocess.run(
        cmd, shell=False, capture_output=True, text=True, cwd=cwd
    )
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
    cmd = [shutil.which("pinto")]
    if project_flag is None:
        cwd = str(project_dir)
    else:
        cwd = None
        cmd.extend([project_flag, str(project_dir)])
    cmd.append("build")

    if extras is not None:
        cmd.extend(["-E", "extra"])
    run_command(cmd, cwd)

    project = Project(project_dir)
    with poetry_env_context(project._venv):
        installed_project_tests(project)

    with pytest.raises(RuntimeError) as exc_info:
        run_command(cmd + ["--no-more", "args"], cwd)
    assert "Unknown arguments ['--no-more', 'args']" in str(exc_info.value)


def test_cli_run_poetry(project_dir, project_flag, poetry_env_context):
    cmd = [shutil.which("pinto")]
    if project_flag is None:
        cwd = str(project_dir)
    else:
        cwd = None
        cmd += [project_flag, str(project_dir)]
    cmd.extend(["run", "testme"])

    try:
        output = run_command(cmd, cwd)
        assert output.rstrip().splitlines()[-1] == "can you hear me?"

        # get rid of the command and make sure this raises an error
        with pytest.raises(RuntimeError) as exc_info:
            run_command(cmd[:-1], cwd)
        msg = str(exc_info.value)
        assert "ValueError: Must provide a command to run!" in msg

        if project_flag is not None:
            with pytest.raises(RuntimeError) as exc_info:
                cmd = f"pinto -v {project_flag} /bad/path run testme".split()
                run_command(cmd, None)
            msg = str(exc_info.value)
            assert "ValueError: Project /bad/path does not exist" in msg
    finally:
        project = Project(project_dir)
        if project._venv.exists():
            with poetry_env_context(project._venv):
                pass


def test_cli_run_with_dotenv(
    make_project_dir, poetry_env_context, write_dotenv, validate_dotenv, dotenv
):
    project_dir = make_project_dir("testlib", None, False)
    write_dotenv(project_dir)
    pinto_cmd = f"pinto -p {project_dir} run".split()

    def run_fn(*cmd, env=None):
        if env is None:
            env_cmd = []
        else:
            env_cmd = ["-e", env]
        return run_command(pinto_cmd + env_cmd + list(cmd), None)

    try:
        validate_dotenv(project_dir, run_fn, RuntimeError)
    finally:
        project = Project(project_dir)
        if project._venv.exists():
            with poetry_env_context(project._venv):
                pass

        shutil.rmtree(project_dir)
