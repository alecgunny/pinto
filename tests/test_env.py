import subprocess
from pathlib import Path
from unittest.mock import Mock

import pytest
import toml
import yaml
from conda.core.prefix_data import PrefixData

from pinto.env import CondaEnvironment, Environment, PoetryEnvironment


@pytest.fixture
def poetry_project(project_dir):
    project = Mock()
    project.path = project_dir
    project.name = "testlib"
    return project


@pytest.fixture(params=["yaml", "yml"])
def yaml_extension(request):
    return request.param


@pytest.fixture
def conda_project_with_local_environment(
    project_dir, yaml_extension, conda_environment_dict, conda_poetry_config
):
    with open(project_dir / ("environment." + yaml_extension), "w") as f:
        yaml.dump(conda_environment_dict, f)

    with open(project_dir / "poetry.toml", "w") as f:
        toml.dump(conda_poetry_config, f)

    project = Mock()
    project.path = project_dir
    project.name = "testlib"
    project.pinto_config = {}
    return project


def _test_installed_env(env, project):
    assert env.contains(project)
    output = env.run("testme")
    assert output.rstrip() == "can you hear me?"

    output = env.run("python", "-c", "import pip_install_test")
    assert output.startswith("Good job!")


def test_poetry_environment(poetry_project):
    env = Environment(poetry_project)
    assert isinstance(env, PoetryEnvironment)
    assert env.path == Path(__file__).resolve().parent / "tmp"
    assert not env.exists()

    venv = env.create()
    assert env.name == venv.path.name
    assert env.name.startswith(
        env._manager.generate_env_name(
            poetry_project.name, str(poetry_project.path)
        )
    )

    assert env.exists()
    assert not env.contains(poetry_project)

    env.install()
    _test_installed_env(env, poetry_project)


def test_conda_environment_with_local_environment_file(
    conda_project_with_local_environment, yaml_extension
):
    env = Environment(conda_project_with_local_environment)
    assert isinstance(env, CondaEnvironment)
    assert env.path == Path(__file__).resolve().parent / "tmp"
    assert not env.exists()
    assert env.name == "pinto-testenv"
    assert env._base_env == env.path / ("environment." + yaml_extension)

    env.create()
    try:
        assert env.exists()
        assert not env.contains(conda_project_with_local_environment)
        output = env.run("python", "-c", "import requests;print('got it!')")
        assert output.rstrip() == "got it!"

        env.install()
        _test_installed_env(env, conda_project_with_local_environment)
    finally:
        response = subprocess.run(
            f"conda env remove -n {env.name}",
            shell=True,
            capture_output=True,
            text=True,
        )
        if response.returncode:
            raise RuntimeError(response.stderr)

        PrefixData._cache_.pop(env.env_root)
