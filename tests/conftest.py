import os
import shutil
from pathlib import Path

import pytest


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
