import os
import shutil
import subprocess
from contextlib import contextmanager
from functools import partial
from pathlib import Path

import pytest
import toml
import yaml
from conda.core.prefix_data import PrefixData


@pytest.fixture(params=["testlib", "test-lib", "test_lib"])
def project_name(request):
    return request.param


@pytest.fixture
def conda_environment_dict():
    return {"name": "pinto-testenv", "dependencies": ["requests"]}


@pytest.fixture
def conda_poetry_config():
    return {"virtualenvs": {"create": False}}


@pytest.fixture
def project_dir(project_name):
    project_dir = Path(__file__).resolve().parent / "tmp"

    standardized_name = project_name.replace("-", "_")
    pyproject = {
        "tool": {
            "poetry": {
                "name": project_name,
                "version": "0.0.1",
                "description": "test project",
                "authors": ["test author <test@testproject.biz>"],
                "scripts": {"testme": standardized_name + ":main"},
                "dependencies": {"pip_install_test": "^0.5"},
            }
        }
    }

    os.makedirs(project_dir)
    with open(project_dir / "pyproject.toml", "w") as f:
        toml.dump(pyproject, f)
    with open(project_dir / (standardized_name + ".py"), "w") as f:
        f.write("def main():\n" "    print('can you hear me?')\n")

    yield project_dir
    shutil.rmtree(project_dir)


@pytest.fixture
def conda_project_dir(project_dir, conda_poetry_config):
    with open(project_dir / "poetry.toml", "w") as f:
        toml.dump(conda_poetry_config, f)
    return project_dir


@pytest.fixture(params=["yaml", "yml"])
def yaml_extension(request):
    return request.param


@pytest.fixture(params=[False, True, "base"])
def nest(request):
    """Indicates whether environment.yaml should live above project"""
    return request.param


@pytest.fixture
def complete_conda_project_dir(
    conda_project_dir, conda_environment_dict, yaml_extension, nest
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

    return project_dir


@contextmanager
def _conda_env_context(env, nest):
    try:
        yield
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


@contextmanager
def _poetry_env_context(env):
    try:
        yield
    finally:
        shutil.rmtree(env.env_root)


@pytest.fixture
def conda_env_context(nest):
    return partial(_conda_env_context, nest=nest)


@pytest.fixture
def poetry_env_context():
    return _poetry_env_context


def _test_installed_project(project):
    assert project._venv.exists()
    assert project._venv.contains(project)

    output = project.run("testme")
    assert output.rstrip() == "can you hear me?"

    output = project.run("python", "-c", "import pip_install_test")
    assert output.startswith("Good job!")


@pytest.fixture
def installed_project_tests():
    return _test_installed_project
