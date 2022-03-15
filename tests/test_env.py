import os
import shutil
import subprocess
from pathlib import Path
from unittest.mock import Mock

import pytest
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


@pytest.fixture(params=[False, True, "base"])
def nest(request):
    return request.param


@pytest.fixture
def conda_project_with_local_environment(
    conda_project_dir, yaml_extension, conda_environment_dict, nest
):
    if nest:
        project_dir = conda_project_dir / "testlib"
        os.makedirs(project_dir)
        for f in os.listdir(conda_project_dir):
            if f == "testlib":
                continue
            shutil.move(conda_project_dir / f, project_dir)
        if nest == "base":
            conda_environment_dict["name"] = "pinto-base"
    else:
        project_dir = conda_project_dir

    environment_file = conda_project_dir / ("environment." + yaml_extension)
    with open(environment_file, "w") as f:
        yaml.dump(conda_environment_dict, f)

    project = Mock()
    project.path = project_dir
    project.name = "testlib"
    project.pinto_config = {}
    return project


@pytest.fixture
def conda_project_with_no_environment(conda_project_dir, conda_poetry_config):
    project = Mock()
    project.path = conda_project_dir
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
    conda_project_with_local_environment, yaml_extension, nest
):
    env = Environment(conda_project_with_local_environment)
    assert isinstance(env, CondaEnvironment)

    expected_path = Path(__file__).resolve().parent / "tmp"
    expected_env = expected_path / ("environment." + yaml_extension)
    expected_name = "pinto-testenv"
    if nest:
        expected_path /= "testlib"

        if nest == "base":
            expected_name = "pinto-testlib"
        else:
            expected_name = conda_project_with_local_environment.name

    assert env.path == expected_path
    assert not env.exists()
    assert env.name == expected_name
    assert env._base_env == expected_env

    env.create()
    try:
        assert env.exists()
        assert not env.contains(conda_project_with_local_environment)
        output = env.run("python", "-c", "import requests;print('got it!')")
        assert output.rstrip() == "got it!"

        env.install()
        _test_installed_env(env, conda_project_with_local_environment)
    finally:
        envs = [env.name]
        if nest:
            envs.append("pinto-testenv")

        for env_name in envs:
            response = subprocess.run(
                f"conda env remove -n {env_name}",
                shell=True,
                capture_output=True,
                text=True,
            )
            if response.returncode:
                raise RuntimeError(response.stderr)

            try:
                PrefixData._cache_.pop(env.env_root)
            except KeyError:
                pass


def test_conda_environment_with_no_environment_file(
    conda_project_with_no_environment,
):
    with pytest.raises(ValueError):
        Environment(conda_project_with_no_environment)
