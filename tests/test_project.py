import pytest
import toml

from pinto.env import CondaEnvironment, PoetryEnvironment
from pinto.project import Project


def test_poetry_project(
    project_dir, poetry_env_context, installed_project_tests
):
    project = Project(project_dir)
    assert isinstance(project._venv, PoetryEnvironment)
    assert not project._venv.exists()

    project.install()
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

    project.install()
    with conda_env_context(project._venv):
        output = project.run(
            "python", "-c", "import requests;print('got it!')"
        )
        assert output.rstrip() == "got it!"

        installed_project_tests(project)
