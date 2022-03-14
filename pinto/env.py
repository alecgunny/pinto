import logging
import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

import toml
import yaml
from cleo.application import Application
from conda.cli import python_api as conda
from poetry.factory import Factory
from poetry.installation.installer import Installer
from poetry.masonry.builders import EditableBuilder
from poetry.utils.env import EnvManager

if TYPE_CHECKING:
    from .project import Project


@dataclass
class Environment:
    project: "Project"

    def __new__(self, project):
        try:
            with open(self.path / "poetry.toml", "r") as f:
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

        obj = env_class.__new__(project)
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
    def name(self) -> str:
        if self._venv is not None:
            return self._venv.path.name
        return self._manager.generate_()  # TODO: fix this

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

    def install(self, *args) -> None:
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
    return re.search(r"\.((yml)|(yaml))$", fname) is not None


def _run_conda_command(*args):
    stdout, stderr, exit_code = conda.run_command(*args)
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
    def _is_yaml(self, fname):
        return re.search(r"\.((yml)|(yaml))$", fname) is not None

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
                environment_file = env_dir / "environment.yaml"
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

                # if we've hit the root level, we don't know
                # what environment to use so raise an error
                if env_dir.parent == env_dir:
                    raise ValueError(
                        "No environment file in directory tree "
                        "of project {}".format(self.name)
                    )

                # otherwise move up to the next directory
                env_dir = env_dir.parent
        else:
            # if the pyproject specified an environment,
            # first check if what is specified is an
            # environment file
            if self._is_yaml(base_env):
                # load the file and get the name of the associated environment
                env_name = _load_env_file(base_env)["name"]
            else:
                # otherwise assume its specifying an
                # environment by name
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
            logging.warning(f"Environment {self.name} already exists")
            return

        # if the base environment is specified as a yaml
        # file, load in the yaml file to check if the
        # environment already exists
        if self._is_yaml(self._base_env):
            env_name = _load_env_file(self._base_env)["name"]

            # if the environment doesn't exist yet, create it
            # using the indicated environnment file
            if not _env_exists(env_name):
                logging.info(
                    "Creating conda environment {} "
                    "from environment file {}".format(env_name, self._base_env)
                )
                stdout = _run_conda_command(
                    conda.Commands.CREATE, "-f", self._base_env
                )
                logging.info(stdout)

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
        stdout = self.run_command(
            conda.Commands.CREATE, "-n", self.name, "--clone", env_name
        )
        logging.info(stdout)

    def contains(self, project: "Project") -> bool:
        project_name = project.name.replace("-", "_")
        regex = re.compile(f"(?m)^{project_name} ")
        package_list = self.run_command(conda.Commands.LIST, "-n", self.name)
        return regex.search(package_list) is not None

    def install(self):
        self.run(
            "/bin/bash", "-c", f"cd {self.project.path} && poetry install"
        )

    def run(self, *args):
        return self._run_conda_command(
            conda.Commands.RUN, "-n", self.name, *args
        )
