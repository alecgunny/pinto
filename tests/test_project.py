import os
import shutil

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
        os.environ.pop("ENVARG1")
        os.environ.pop("ENVARG2")


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
        os.environ.pop("ENVARG1")
        os.environ.pop("ENVARG2")


def test_poetry_project_with_dotenv(
    poetry_dotenv_project_dir, poetry_env_context, dotenv, validate_dotenv
):
    project = Project(poetry_dotenv_project_dir)
    with poetry_env_context(project.venv):
        project.install()
        validate_dotenv(project)


def test_conda_project_with_dotenv(
    conda_dotenv_project_dir, dotenv, validate_dotenv
):
    project = Project(conda_dotenv_project_dir)
    project.install()
    validate_dotenv(project)


PIPELINE_SCRIPT = """
import os
from hermes.typeo import typeo


@typeo
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
        config["tool"]["poetry"]["dependencies"]["hermes.typeo"] = "^0.1.5"

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
