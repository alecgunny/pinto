import subprocess
from pathlib import Path

import pytest

from pinto.env import CondaEnvironment, PoetryEnvironment
from pinto.project import Project

EXAMPLES_DIR = Path(__file__).resolve().parent.parent.parent / "examples"


def _run_command(cmd):
    response = subprocess.run(cmd, shell=True, text=True, capture_output=True)
    if response.returncode:
        raise RuntimeError(
            f"Command '{cmd}' failed with error:\n{response.stderr}"
        )
    return response.stdout


@pytest.fixture(params=list(EXAMPLES_DIR.iterdir()))
def example_dir(request):
    example_dir = request.param
    if "nested" in request.param.name:
        example_dir = example_dir / "src"
    return example_dir


def test_simple_poetry_example(example_dir):
    response = _run_command(f"pinto -p {example_dir} build")

    project = Project(example_dir)
    if "poetry" in example_dir.name:
        env = PoetryEnvironment(project)
    else:
        env = CondaEnvironment(project)
    assert env.exists()
    assert env.contains(project)

    response = _run_command(f"pinto -p {example_dir} run testme")
    assert response.startswith("Good job!")
    assert response.rstrip().endswith("Everything's working!")
