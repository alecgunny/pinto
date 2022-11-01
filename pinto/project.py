import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, Optional

import toml
from dotenv import load_dotenv

from pinto.env import Environment
from pinto.logging import logger


@dataclass
class ProjectBase:
    path: str

    def __post_init__(self):
        self.path = Path(self.path).resolve()
        if not self.path.exists():
            raise ValueError(f"Project {self.path} does not exist")

        config_path = self.path / "pyproject.toml"
        try:
            with open(config_path, "r") as f:
                self._config = toml.load(f)
        except FileNotFoundError:
            raise ValueError(
                "{} {} has no associated 'pyproject.toml' "
                "at location {}".format(
                    self.__class__.__name__, self.path, config_path
                )
            )

    @property
    def config(self) -> Dict:
        return self._config.copy()

    def load_dotenv(self, env: Optional[str] = None) -> None:
        if env is None or not os.path.isabs(env):
            env = env or ".env"
            env = self.path / env

        if os.path.exists(env):
            load_dotenv(env)


@dataclass
class Project(ProjectBase):
    """
    Represents an individual project or library with
    an environment to be managed by some combination
    of Poetry and Conda and which may expose some set
    of command-line commands once installed
    """

    def __post_init__(self):
        super().__post_init__()
        try:
            self.name = self._config["tool"]["poetry"]["name"]
        except KeyError as e:
            if "poetry" in str(e):
                raise ValueError(
                    "Project config '{}' has no 'tool.poetry' table".format(
                        self.path / "pyproject.toml"
                    )
                )

        self._venv = Environment(self)

    @property
    def pinto_config(self) -> dict:
        """
        Project Pinto settings as defined in the
        project's `pyproject.toml`
        """

        try:
            return self.config["tool"]["pinto"].copy()
        except KeyError:
            return {}

    @property
    def venv(self) -> Environment:
        """The virtual environment associated with this project"""
        return self._venv

    def install(
        self, force: bool = False, extras: Optional[Iterable[str]] = None
    ) -> None:
        """
        Install this project into the virtual environment,
        creating the environment if necessary.

        Args:
            force:
                If `True`, update the environment even
                if the project is already installed. Otherwise,
                if the project is already installed in
                the environment, log that fact and move on.
            extras:
                Groups of extra dependencies to install
        """

        if not self._venv.exists():
            self._venv.create()

        # ensure environment has this project
        # installed somewhere
        if not self._venv.contains(self):
            logger.info(
                "Installing project '{}' from '{}' into "
                "virtual environemnt '{}'".format(
                    self.name, self.path, self._venv.name
                )
            )
            self._venv.install(extras=extras)
        elif force:
            logger.info(
                "Updating project '{}' from '{}' in "
                "virtual environment '{}'".format(
                    self.name, self.path, self._venv.name
                )
            )
            # TODO: should we do a `poetry update` rather
            # than install in this case? What does that
            # command look like for the poetry env?
            self._venv.install(extras=extras)
        else:
            logger.info(
                "Project '{}' at '{}' already installed in "
                "virtual environment '{}'".format(
                    self.name, self.path, self._venv.name
                )
            )

    def run(self, *args: str, **kwargs: Any) -> str:
        """Run a command in the project's virtual environment

        Run an individual command in the project's
        virtual environment, with each space-separated
        argument in the command given as a separate
        string argument to this method.

        If the project's virtual environment doesn't
        exist or doesn't have the project installed
        yet, `Project.install` will be called before
        executing the command.

        Args:
            *args:
                Command-line parameters to execute
                in the project's virtual environment.
                Each `arg` will be treated as a single
                command line parameter, even if there
                are spaces in it. So, for example, calling

                ```python
                project = Project(...)
                project.run("/bin/bash", "-c", "cd /home && echo $PWD")
                ```

                will execute `"cd /home && echo $PWD"` as the entire
                argument of `/bin/bash -c`.
        Returns:
            The standard output generated by executing the command
        """

        if not self._venv.exists() or not self._venv.contains(self):
            self.install()

        # check if the project has specified a CUDA version to run with
        cuda_version = self.pinto_config.get("cuda-version")
        if cuda_version is not None:
            # if the version specified isn't a path to a CUDA
            # lib directory, assume it specifies a version
            # number and build the default path from it
            if not Path(cuda_version).is_dir():
                cuda_version = f"/usr/local/cuda-{cuda_version}/lib64"

            # insert it at the front of the LD_LIBRARY_PATH
            # environment variable so that it's the first
            # place that gets checked
            ld_library_path = os.environ.get("LD_LIBRARY_PATH", "")
            os.environ["LD_LIBRARY_PATH"] = f"{cuda_version}:{ld_library_path}"

        # now load any other environment variables
        # passed in from a .env file so that users
        # can override this default behavior if they
        # really really need to
        self.load_dotenv(kwargs.get("env"))

        logger.debug(f"Executing command '{args}' in project {self.path}")
        response = self._venv.run(*args)
        return response


@dataclass
class Pipeline(ProjectBase):
    def __post_init__(self):
        super().__post_init__()

        config_path = self.path / "pyproject.toml"
        try:
            _ = self.steps
        except KeyError:
            raise ValueError(
                f"Config file {config_path} has no '[tool.pinto]' "
                "table or 'steps' key in it."
            )
        try:
            _ = self.typeo_config
        except KeyError:
            raise ValueError(
                f"Config file {config_path} has no '[tool.typeo]' "
                "table necessary to run projects."
            )

    @property
    def steps(self):
        return self.config["tool"]["pinto"]["steps"]

    @property
    def typeo_config(self):
        return self.config["tool"]["typeo"]

    def create_project(self, name):
        return Project(self.path / name)

    def run(self, env: Optional[str] = None):
        self.load_dotenv(env)

        for step in self.steps:
            logger.debug(f"Parsing pipeline step {step}")

            try:
                component, command, subcommand = step.split(":")
            except ValueError:
                try:
                    component, command = step.split(":")
                    subcommand = None
                except ValueError:
                    raise ValueError(f"Can't parse pipeline step '{step}'")

            project = self.create_project(component)
            stdout = self.run_step(project, command, subcommand)
            logger.info(stdout)

    def run_step(
        self,
        project: Project,
        command: str,
        subcommand: Optional[str] = None,
    ):
        typeo_arg = str(self.path)
        try:
            if command in self.typeo_config["scripts"]:
                typeo_arg += ":" + command
        except KeyError:
            if subcommand is not None:
                typeo_arg += "::" + subcommand
        else:
            if subcommand is not None:
                typeo_arg += ":" + subcommand

        # override the project's load_dotenv method
        # so that it won't attempt to load any local
        # environment file it might have
        method = project.load_dotenv
        project.load_dotenv = lambda env: None
        try:
            project.run(command, "--typeo", typeo_arg)
        finally:
            project.load_dotenv = method
