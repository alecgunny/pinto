import os
import re
import shutil
import subprocess
from dataclasses import dataclass
from typing import TYPE_CHECKING, Iterable, Optional

import toml
import yaml
from cleo.application import Application
from conda.cli import python_api as conda
from conda.core.prefix_data import PrefixData
from poetry.factory import Factory
from poetry.installation.installer import Installer
from poetry.masonry.builders import EditableBuilder
from poetry.utils.env import EnvManager

from pinto.logging import logger

if TYPE_CHECKING:
    from .project import Project


@dataclass
class Environment:
    project: "Project"

    def __new__(self, project):
        try:
            with open(project.path / "poetry.toml", "r") as f:
                poetry_config = toml.load(f)
        except FileNotFoundError:
            env_class = PoetryEnvironment
        else:
            try:
                if poetry_config["virtualenvs"]["create"]:
                    env_class = PoetryEnvironment
                else:
                    env_class = CondaEnvironment
            except KeyError:
                env_class = PoetryEnvironment

        obj = object.__new__(env_class)
        return obj

    @property
    def path(self):
        return self.project.path


@dataclass
class PoetryEnvironment(Environment):
    def __post_init__(self):
        self._poetry = Factory().create_poetry(self.path)
        self._manager = EnvManager(self._poetry)
        self._io = Application.create_io(self)

        # if the actual virtual environment doesn't
        # exist yet, don't create it. But if it does,
        # call `create` to retrieve it and set the attribute
        if not self.exists():
            self._venv = None
        else:
            self.create()

    @property
    def env_root(self):
        if self._venv is None:
            # TODO: this isn't exactly right, but the
            # logic is a lot to reimplement and is the
            # environment doesn't exist yet, this seems
            # like a fair thing to return
            return self._manager.get()
        return self._venv.path

    @property
    def name(self) -> str:
        if self._venv is not None:
            return self._venv.path.name
        return self._manager.generate_env_name(
            self.project.name, str(self.project.path)
        )

    def exists(self) -> bool:
        return self._manager.get() != self._manager.get_system_env()

    def create(self):
        self._venv = self._manager.create_venv(self._io)
        return self._venv

    def contains(self, project: "Project") -> bool:
        if self._venv is None:
            raise ValueError(f"Virtual environment {self.name} not created")

        name = project.name.replace("-", "_")
        return self._venv.site_packages.find_distribution(name) is not None

    def install(self, extras: Optional[Iterable[str]] = None) -> None:
        installer = Installer(
            self._io,
            self._venv,
            self._poetry.package,
            self._poetry.locker,
            self._poetry.pool,
            self._poetry.config,
        )

        installer.update(True)
        installer.use_executor(True)
        if extras is not None:
            installer.extras(extras)

        installer.run()

        builder = EditableBuilder(self._poetry, self._venv, self._io)
        builder.build()

    def run(self, *args):
        try:
            return self._venv.run(*args)
        except Exception as e:
            raise RuntimeError(
                "Executing command {} in poetry environment {} "
                "failed with error:\n{}".format(
                    args, self._venv.path.name, str(e)
                )
            )


def _is_yaml(fname):
    return re.search(r"\.((yml)|(yaml))$", str(fname)) is not None


def _run_conda_command(*args):
    try:
        stdout, stderr, exit_code = conda.run_command(
            *map(str, args), use_exception_handler=False
        )
    except SystemExit:
        raise RuntimeError("System exit raised!")

    if exit_code:
        raise RuntimeError(
            "Executing command {} failed with error:\n{}".format(args, stderr)
        )
    return stdout


def _env_exists(env_name):
    stdout = _run_conda_command(conda.Commands.INFO, "--envs")
    rows = [i for i in stdout.splitlines() if i and not i.startswith("#")]
    env_names = [i.split()[0] for i in rows]
    return env_name in env_names


def _load_env_file(env_file):
    with open(env_file, "r") as f:
        return yaml.safe_load(f)


@dataclass
class CondaEnvironment(Environment):
    @property
    def env_root(self):
        return os.path.join(os.environ["CONDA_ROOT"], "envs", self.name)

    def __post_init__(self):
        try:
            # first check to see if the project pyproject.toml
            # indicates a conda environment to poetry install
            # dependencies on top of
            base_env = self.project.pinto_config["base_env"]
        except KeyError:
            # if conda environment is not specified, begin
            # looking for an `environment.yaml` in every
            # directory going up to the root level from the
            # project directory, taking the first environment.yaml
            # we can find
            env_dir = self.path
            while True:
                for suffix in ["yaml", "yml"]:
                    environment_file = env_dir / ("environment." + suffix)
                    if environment_file.exists():
                        self._base_env = environment_file
                        env_name = _load_env_file(environment_file)["name"]

                        # if this environment file live's in the
                        # project's directory, then take it as
                        # the intended environment name
                        if env_dir == self.path:
                            self.name = env_name
                        else:
                            # otherwise if an environment file in
                            # the directory tree has a name ending
                            # in "-base", replace the "base" part
                            # with the name of the project
                            if env_name.endswith("-base"):
                                self.name = re.sub(
                                    "base$", self.project.name, env_name
                                )
                            else:
                                # otherwise use the name of the project
                                # as the name of the virtual environment
                                self.name = self.project.name
                        break
                else:
                    # if we've hit the root level, we don't know
                    # what environment to use so raise an error
                    if env_dir.parent == env_dir:
                        raise ValueError(
                            "No environment file in directory tree "
                            "of project {}".format(self.project.path)
                        )

                    # otherwise move up to the next directory
                    env_dir = env_dir.parent
                    continue
                break
        else:
            # if the pyproject specified an environment,
            # first check if what is specified is an
            # environment file
            if _is_yaml(base_env):
                # load the file and get the name of the associated environment
                env_name = _load_env_file(base_env)["name"]
            else:
                # otherwise assume its specifying an environment by name
                env_name = base_env

            if env_name.endswith("-base"):
                self.name = re.sub("base$", self.project.name, env_name)
            else:
                self.name = self.project.name

            self._base_env = base_env

    def exists(self):
        return _env_exists(self.name)

    def create(self):
        # TODO: do this check in the parent class?
        if self.exists():
            logger.warning(f"Environment {self.name} already exists")
            return

        # if the base environment is specified as a yaml
        # file, load in the yaml file to check if the
        # environment already exists
        if _is_yaml(self._base_env):
            env_name = _load_env_file(self._base_env)["name"]

            # if the environment doesn't exist yet, create it
            # using the indicated environnment file
            if not _env_exists(env_name):
                logger.info(
                    "Creating conda environment {} "
                    "from environment file {}".format(env_name, self._base_env)
                )

                # unfortunately the conda python api doesn't support
                # creating from an environment file, so call this
                # subprocess manually
                conda_cmd = f"conda env create -f {self._base_env}"
                response = subprocess.run(
                    conda_cmd, shell=True, capture_output=True, text=True
                )
                if response.returncode:
                    raise RuntimeError(
                        "Conda command '{}'' failed with return code {} "
                        "and stderr:\n{}".format(
                            conda_cmd, response.returncode, response.stderr
                        )
                    )
                logger.info(response.stdout)

            # if the specified environment file is for
            # _this_ environment, then we're done here
            if env_name == self.name:
                return
        else:
            env_name = self._base_env

        if not _env_exists(env_name):
            raise ValueError(f"No base Conda environment {env_name} to clone")

        # otherwise create a fresh environment
        # by cloning the indicated environment
        logger.info(
            "Creating environment {} by cloning from environment {}".format(
                self.name, env_name
            )
        )
        stdout = _run_conda_command(
            conda.Commands.CREATE, "-n", self.name, "--clone", env_name
        )
        logger.info(stdout)

    def contains(self, project: "Project") -> bool:
        project_name = project.name.replace("_", "-")
        regex = re.compile(f"(?m)^{project_name} ")
        package_list = _run_conda_command(conda.Commands.LIST, "-n", self.name)
        return regex.search(package_list) is not None

    def install(self, extras: Optional[Iterable[str]] = None):
        # use poetry binary explicitly since activating
        # environment may remove location from $PATH
        poetry_bin = shutil.which("poetry")
        cmd = f"cd {self.project.path} && {poetry_bin} install"

        # specify any extras and execute command
        if extras is not None:
            for extra in extras:
                cmd += f" -E {extra}"
        response = self.run("/bin/bash", "-c", cmd)

        # Conda caches calls to `conda list`, so manually update
        # the cache to reflect the newly pip-installed packages
        try:
            PrefixData._cache_.pop(self.env_root)
        except KeyError:
            pass

        return response

    def run(self, *args):
        return _run_conda_command(conda.Commands.RUN, "-n", self.name, *args)
