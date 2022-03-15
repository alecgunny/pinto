from pinto.env import CondaEnvironment, PoetryEnvironment
from pinto.project import Project


def _test_installed_project(project):
    assert project._venv.exists()
    assert project._venv.contains(project)

    output = project.run("testme")
    assert output.rstrip() == "can you hear me?"

    output = project.run("python", "-c", "import pip_install_test")
    assert output.startswith("Good job!")


def test_poetry_project(project_dir, poetry_env_context):
    project = Project(project_dir)
    assert isinstance(project._venv, PoetryEnvironment)
    assert not project._venv.exists()

    project.install()
    with poetry_env_context(project._venv):
        _test_installed_project(project)


def test_conda_project(complete_conda_project_dir, nest, conda_env_context):
    project = Project(complete_conda_project_dir)
    assert isinstance(project._venv, CondaEnvironment)
    assert not project._venv.exists()

    if not nest:
        assert project._venv.name == "pinto-testenv"
    elif nest == "base":
        assert project._venv.name == "pinto-testlib"
    else:
        assert project._venv.name == project.name

    project.install()
    with conda_env_context(project._venv):
        output = project.run(
            "python", "-c", "import requests;print('got it!')"
        )
        assert output.rstrip() == "got it!"

        _test_installed_project(project)
