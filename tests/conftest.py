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


@pytest.fixture(params=[None, "attrs"])
def extras(request):
    return request.param


@pytest.fixture
def make_project_dir(conda_poetry_config):
    def f(project_name, extras=None, conda=False, subdir=False):
        project_dir = Path(__file__).resolve().parent / "tmp"
        if subdir:
            project_dir /= project_name

        standardized_name = project_name.replace("-", "_")
        # TODO: fixture for python version?
        pyproject = {
            "tool": {
                "poetry": {
                    "name": project_name,
                    "version": "0.0.1",
                    "description": "test project",
                    "authors": ["test author <test@testproject.biz>"],
                    "scripts": {"testme": standardized_name + ":main"},
                    "dependencies": {
                        "python": ">=3.9,<3.11",
                        "pip_install_test": "^0.5",
                    },
                }
            }
        }
        if extras is not None:
            pyproject["tool"]["poetry"]["dependencies"][extras] = {
                "version": "^21.4",
                "optional": True,
            }
            pyproject["tool"]["poetry"]["extras"] = {"extra": ["attrs"]}

        os.makedirs(project_dir)
        with open(project_dir / "pyproject.toml", "w") as f:
            toml.dump(pyproject, f)
        with open(project_dir / (standardized_name + ".py"), "w") as f:
            f.write("def main():\n" "    print('can you hear me?')\n")

        if conda:
            with open(project_dir / "poetry.toml", "w") as f:
                toml.dump(conda_poetry_config, f)
        return project_dir

    return f


@pytest.fixture
def project_dir(make_project_dir, project_name, extras):
    project_dir = make_project_dir(project_name, extras)
    yield project_dir
    shutil.rmtree(project_dir)


@pytest.fixture
def conda_project_dir(make_project_dir, project_name, extras):
    project_dir = make_project_dir(project_name, extras, True)
    yield project_dir
    shutil.rmtree(project_dir)


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


@pytest.fixture
def conda_env_context(nest):
    return partial(_conda_env_context, nest=nest)


@pytest.fixture
def poetry_env_context():
    @contextmanager
    def ctx(env):
        try:
            yield
        finally:
            shutil.rmtree(env.env_root)

    return ctx


@pytest.fixture
def installed_project_tests(extras, capfd):
    def _test_installed_project(project):
        assert project._venv.exists()
        assert project._venv.contains(project)

        project.run("testme")
        output = capfd.readouterr()
        assert output.out.endswith("can you hear me?\n")

        project.run("python", "-c", "import pip_install_test")
        output = capfd.readouterr()
        assert output.out.startswith("Good job!")

        if extras is not None:
            project.run("python", "-c", "import attrs")
        else:
            with pytest.raises(SystemExit):
                project.run("python", "-c", "import attrs")

    return _test_installed_project


@pytest.fixture(params=[None, ".env", ".other-env"], scope="function")
def dotenv(request):
    return request.param


@pytest.fixture
def validate_dotenv(dotenv, capfd):
    def f(project):
        script = """
            import os
            print(os.environ['ENVARG1'])
            print(os.environ['ENVARG2'])
        """
        script = "\n".join([i.strip() for i in script.splitlines()])

        if dotenv != ".env":
            # if there's no .env, pinto won't know to look for one
            # and so the environment variables should not get set
            with pytest.raises(SystemExit):
                project.run("python", "-c", script)
            stderr = capfd.readouterr().err
            assert "KeyError" in stderr

            # if there is an env file, just not one called .env,
            # we can specify explicitly via the `env` argument
            if dotenv is not None:
                env = str(project.path / dotenv)
                project.run("python", "-c", script, env=env)
                stdout = capfd.readouterr().out
                assert stdout == "thom\nthom-yorke\n"
        elif dotenv == ".env":
            # if there is a .env file, we shouldn't need to
            # specify anything: pinto will pick it up on its own
            project.run("python", "-c", script)
            stdout = capfd.readouterr().out
            assert stdout.endswith("thom\nthom-yorke\n")

    return f


@pytest.fixture
def write_dotenv(dotenv):
    def f(project_dir):
        if dotenv is not None:
            with open(project_dir / dotenv, "w") as f:
                f.write("ENVARG1=thom\nENVARG2=${ENVARG1}-yorke\n")

    return f
