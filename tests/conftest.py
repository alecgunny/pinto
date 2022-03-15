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


@pytest.fixture
def config_dir():
    return Path(__file__).resolve().parent / "configs"


@pytest.fixture
def pyproject(config_dir):
    return config_dir / "pyproject.toml"


@pytest.fixture
def conda_environment_dict():
    return {"name": "pinto-testenv", "dependencies": ["requests"]}


@pytest.fixture
def conda_poetry_config():
    return {"virtualenvs": {"create": False}}


@pytest.fixture
def project_dir(pyproject):
    project_dir = Path(__file__).resolve().parent / "tmp"

    os.makedirs(project_dir)
    shutil.copy(pyproject, project_dir)
    with open(project_dir / "testlib.py", "w") as f:
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
