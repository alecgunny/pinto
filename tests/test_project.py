import os
import shutil
from pathlib import Path

import pytest
import toml
import yaml

from pinto.env import CondaEnvironment, PoetryEnvironment
from pinto.project import Pipeline, Project


def test_poetry_project(
    project_dir, poetry_env_context, installed_project_tests, extras
):
    project = Project(project_dir)
    assert isinstance(project._venv, PoetryEnvironment)
    assert not project._venv.exists()

    if extras is None:
        project.install()
    else:
        project.install(extras=["extra"])

    with poetry_env_context(project._venv):
        installed_project_tests(project)

    bad_config = project.config
    bad_config["tool"].pop("poetry")
    with open(project.path / "pyproject.toml", "w") as f:
        toml.dump(bad_config, f)

    with pytest.raises(ValueError):
        project = Project(project_dir)


def test_conda_project(
    complete_conda_project_dir,
    nest,
    conda_env_context,
    installed_project_tests,
    extras,
    capfd,
):
    project = Project(complete_conda_project_dir)
    assert isinstance(project._venv, CondaEnvironment)
    assert not project._venv.exists()

    if not nest:
        assert project._venv.name == "pinto-testenv"
    elif nest == "base":
        assert project._venv.name == "pinto-" + project.name
    else:
        assert project._venv.name == project.name

    if extras is None:
        project.install()
    else:
        project.install(extras=["extra"])

    with conda_env_context(project._venv):
        project.run("python", "-c", "import requests;print('passed!')")
        output = capfd.readouterr().out
        assert output.splitlines()[-1] == "passed!"

        installed_project_tests(project)


@pytest.fixture(scope="function")
def poetry_dotenv_project_dir(make_project_dir, write_dotenv, dotenv):
    project_dir = make_project_dir("testlib", None, False)
    write_dotenv(project_dir)

    yield project_dir
    shutil.rmtree(project_dir)
    if dotenv is not None:
        for i in range(2):
            try:
                os.environ.pop(f"ENVARG{i}")
            except KeyError:
                continue


@pytest.fixture(scope="function")
def conda_dotenv_project_dir(
    make_project_dir, write_dotenv, conda_environment_dict, dotenv
):
    project_dir = make_project_dir("testlib", None, True)
    with open(project_dir / "environment.yaml", "w") as f:
        yaml.dump(conda_environment_dict, f)
    write_dotenv(project_dir)

    yield project_dir
    shutil.rmtree(project_dir)
    if dotenv is not None:
        for i in range(2):
            try:
                os.environ.pop(f"ENVARG{i}")
            except KeyError:
                continue


@pytest.fixture
def validate_project_dotenv(validate_dotenv, capfd):
    def validate(project):
        def run_fn(*cmd, env=None):
            project.run(*cmd, env=env)
            return capfd.readouterr().out

        validate_dotenv(project.path, run_fn, SystemExit)

    return validate


def test_poetry_project_with_dotenv(
    poetry_dotenv_project_dir,
    poetry_env_context,
    validate_project_dotenv,
):
    project = Project(poetry_dotenv_project_dir)
    with poetry_env_context(project.venv):
        project.install()
        validate_project_dotenv(project)


def test_conda_project_with_dotenv(
    conda_dotenv_project_dir, validate_project_dotenv
):
    project = Project(conda_dotenv_project_dir)
    project.install()
    validate_project_dotenv(project)


@pytest.fixture(params=[11.2, "local-dir"])
def cuda_version(request):
    return request.param


@pytest.fixture(params=[True, False])
def conda(request):
    return request.param


GET_LD_LIB_SCRIPT = """
import os

print(os.getenv("LD_LIBRARY_PATH", "Nothin"))
"""


def test_project_with_cuda_version(
    make_project_dir, cuda_version, conda, conda_environment_dict, capfd
):
    project_dir = make_project_dir("test_project", conda=conda)
    if conda:
        with open(project_dir / "environment.yaml", "w") as f:
            yaml.dump(conda_environment_dict, f)

    with open(project_dir / "test_project.py", "w") as f:
        f.write(GET_LD_LIB_SCRIPT)

    with open(project_dir / "pyproject.toml", "r") as f:
        config = toml.load(f)
    config["tool"]["pinto"] = {"cuda-version": str(cuda_version)}
    with open(project_dir / "pyproject.toml", "w") as f:
        toml.dump(config, f)

    if not isinstance(cuda_version, float):
        Path(cuda_version).mkdir()

    try:
        project = Project(project_dir)
        project.install()
        capfd.readouterr()

        project.run("python", project_dir / "test_project.py")
        stdout = capfd.readouterr().out.splitlines()[-1]
        paths = stdout.split(":")

        if isinstance(cuda_version, float):
            assert f"/usr/local/cuda-{cuda_version}/lib64" in paths
        else:
            assert cuda_version in paths
    finally:
        shutil.rmtree(project_dir)
        if not isinstance(cuda_version, float):
            shutil.rmtree(cuda_version)


PIPELINE_SCRIPT = """
import os
from typeo import scriptify


@scriptify
def main(i: int):
    env = int(os.environ.get("ENVARG", "0"))
    print(f"arg is equal to {i + env}")
"""


def test_pipeline(make_project_dir, dotenv, capfd):
    # create a pipeline with two projects, each with
    # a different executable script
    for i in [1, 2]:
        project_dir = make_project_dir(f"project{i}", subdir=True)
        with open(project_dir / f"project{i}.py", "w") as f:
            f.write(PIPELINE_SCRIPT)

        # update the project config to give its script a
        # unique name and add a typeo dependency
        with open(project_dir / "pyproject.toml", "r") as f:
            config = toml.load(f)

        config["tool"]["poetry"]["scripts"].pop("testme")
        config["tool"]["poetry"]["scripts"][f"testme{i}"] = f"project{i}:main"
        config["tool"]["poetry"]["dependencies"]["typeo"] = {
            "git": "https://github.com/ML4GW/typeo.git",
            "branch": "main",
        }

        with open(project_dir / "pyproject.toml", "w") as f:
            toml.dump(config, f)

    try:
        with open(project_dir.parent / "pyproject.toml", "w") as f:
            toml.dump(
                {
                    "tool": {
                        "pinto": {
                            "steps": ["project1:testme1", "project2:testme2"]
                        },
                        "typeo": {
                            "scripts": {
                                "testme1": {"i": 3},
                                "testme2": {"i": 10},
                            }
                        },
                    }
                },
                f,
            )

        kwargs = {}
        if dotenv is not None:
            with open(project_dir.parent / dotenv, "w") as f:
                f.write("ENVARG=1\n")

            # write a different dotenv to one of the projects
            # to verify that it doesn't get used
            with open(project_dir / ".env", "w") as f:
                f.write("ENVARG=2\n")

            # if the dotenv file has a unique name, specify
            # it explicitly to pipeline.run
            if dotenv != ".env":
                kwargs["env"] = project_dir.parent / "env"

        pipeline = Pipeline(project_dir.parent)
        pipeline.run(**kwargs)

        stdout = capfd.readouterr().out
        for i in [3, 10]:
            if dotenv is not None:
                i = i + 1
            assert f"arg is equal to {i}" in stdout
    finally:
        shutil.rmtree(project_dir.parent)


@pytest.mark.parametrize("override", [True, False, None])
def test_conda_env_with_ld_lib(
    override, make_project_dir, conda_environment_dict, capfd
):
    project_dir = make_project_dir("test_project", conda=True)
    with open(project_dir / "environment.yaml", "w") as f:
        yaml.dump(conda_environment_dict, f)

    with open(project_dir / "test_project.py", "w") as f:
        f.write(GET_LD_LIB_SCRIPT)

    # if we specified an explicit (not None) value
    # for override, add it to the project pinto config
    if override is not None:
        conda_config = {"append_base_ld_library_path": override}
        with open(project_dir / "pyproject.toml", "r") as f:
            config = toml.load(f)
        config["tool"]["pinto"] = {"conda": conda_config}
        with open(project_dir / "pyproject.toml", "w") as f:
            toml.dump(config, f)

    prefix = os.environ["CONDA_PREFIX"]
    try:
        project = Project(project_dir)
        project.install()
        capfd.readouterr()

        project.run("python", project_dir / "test_project.py")
        stdout = capfd.readouterr().out.splitlines()[-1]
        if not override:
            assert stdout == "Nothin"
        else:
            paths = stdout.split(":")
            assert f"{project._venv.env_root}/lib" in paths
            assert f"{prefix}/lib" in paths
    finally:
        shutil.rmtree(project_dir)
