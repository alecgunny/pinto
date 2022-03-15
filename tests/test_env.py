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
    """Indicates whether environment.yaml should live above project"""
    return request.param


@pytest.fixture
def conda_project_with_local_environment(
    conda_project_dir, yaml_extension, conda_environment_dict, nest
):
    if nest:
        # if we'r nesting, copy all the files from the
        # test project into a subdirectory
        project_dir = conda_project_dir / "testlib"
        os.makedirs(project_dir)
        for f in os.listdir(conda_project_dir):
            if f == "testlib":
                continue
            shutil.move(conda_project_dir / f, project_dir)

        # if we're testing the "<name>-base" syntax, replace
        # the name in the environment dictionary
        if nest == "base":
            conda_environment_dict["name"] = "pinto-base"
    else:
        project_dir = conda_project_dir

    # write the environment dictionary to the
    # top level directory, whether we're nesting
    # or not
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
    """Test an environment that has ostensibly installed its project"""

    # make sure that the `contains` method correctly
    # reflects the installation status
    assert env.contains(project)

    # make sure we can run our `testme` script
    # and that it produces the appropriate output
    output = env.run("testme")
    assert output.rstrip() == "can you hear me?"

    # now make sure that our dependency
    # got installed correctly
    output = env.run("python", "-c", "import pip_install_test")
    assert output.startswith("Good job!")


def test_poetry_environment(poetry_project):
    # make sure that the __new__ method maps correctly from
    # a project with no "poetry.toml" to a PoetryEnvironment
    env = Environment(poetry_project)
    assert isinstance(env, PoetryEnvironment)

    # make sure that the environment points to the
    # correct location and exists
    assert env.path == Path(__file__).resolve().parent / "tmp"
    assert not env.exists()

    # create the underlying virtual environment
    # and ensure its name is correct
    venv = env.create()
    assert env.name == venv.path.name
    assert env.name.startswith(
        env._manager.generate_env_name(
            poetry_project.name, str(poetry_project.path)
        )
    )

    # make sure that the environment exists, but
    # that it doesn't contain the corresponding
    # project since we haven't installed it yet
    assert env.exists()
    assert not env.contains(poetry_project)

    # install the project and then run standard
    # tests on the now complete environment
    env.install()
    _test_installed_env(env, poetry_project)


def test_conda_environment_with_local_environment_file(
    conda_project_with_local_environment, yaml_extension, nest
):
    # make sure that the __new__ method maps correctly from
    # a project with a "poetry.toml" to a CondaEnvironment
    env = Environment(conda_project_with_local_environment)
    assert isinstance(env, CondaEnvironment)

    expected_path = Path(__file__).resolve().parent / "tmp"
    expected_env = expected_path / ("environment." + yaml_extension)
    expected_name = "pinto-testenv"
    if nest:
        # if we're nesting, the environment path
        # should be buried one more level down
        expected_path /= "testlib"

        # if we're using the "<name>-base" syntax,
        # "base" should have been replaced by "testlib"
        if nest == "base":
            expected_name = "pinto-testlib"
        else:
            # otherwise the project name will be the
            # default environment name
            expected_name = conda_project_with_local_environment.name

    # make sure that all of our expectations are
    # met and that the environment doesn't exist yet
    assert env.path == expected_path
    assert not env.exists()
    assert env.name == expected_name
    assert env._base_env == expected_env

    # now create the environment, then run all
    # the tests in a context so that it gets
    # deleted at the end
    env.create()
    try:
        # make sure the environment exists now, but
        # that it still doesn't contain the relevant
        # project since we haven't installed it
        assert env.exists()
        assert not env.contains(conda_project_with_local_environment)

        # make sure that we can import the dependency
        # listed in our _conda_ environment file, and
        # that the `run` method works properly
        output = env.run("python", "-c", "import requests;print('got it!')")
        assert output.rstrip() == "got it!"

        # now install the test package and run the
        # standard tests on it
        env.install()
        _test_installed_env(env, conda_project_with_local_environment)
    finally:
        # delete all the environments no matter what
        # happened so that future tests can get a
        # fresh set of environments to deal with
        envs = [env.name]

        # make sure to include the environment we've
        # cloned from if we're running a nested test
        if nest == "base":
            envs.append("pinto-base")
        elif nest:
            envs.append("pinto-testenv")

        # run the command manually since conda env
        # commands aren't supported in the python api
        for env_name in envs:
            response = subprocess.run(
                f"conda env remove -n {env_name}",
                shell=True,
                capture_output=True,
                text=True,
            )
            if response.returncode:
                raise RuntimeError(response.stderr)

            # remove the environment package cache
            try:
                PrefixData._cache_.pop(env.env_root)
            except KeyError:
                pass


def test_conda_environment_with_no_environment_file(
    conda_project_with_no_environment,
):
    """
    Make sure that a conda environment with no
    environment file fails to resolve at initialization.
    """

    with pytest.raises(ValueError):
        Environment(conda_project_with_no_environment)
