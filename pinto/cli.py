import argparse
import logging
import os
import re
import sys
from collections import OrderedDict
from pathlib import Path
from typing import List

from pinto import __version__
from pinto.logging import logger
from pinto.project import Pipeline, Project

_commands = OrderedDict()


def _add_help(parser: argparse.ArgumentParser, extra_args: List[str]) -> bool:
    options = ["-h", "--help"]
    action = argparse._HelpAction(options)
    for flag in options:
        if flag in extra_args:
            parser._action_groups[1]._actions.append(action)
            return True
    else:
        return False


class CommandMeta(type):
    def __new__(cls, clsname, bases, attrs):
        obj = super().__new__(cls, clsname, bases, attrs)
        if obj.name:
            _commands[obj.name] = obj
        obj._subparser = None
        return obj

    @property
    def name(cls):
        return re.sub("Command$", "", cls.__name__).lower()

    @property
    def subparser(cls):
        return cls._subparser


def build_base_parser(parser: argparse.ArgumentParser):
    parser.add_argument(
        "--version", action="version", version=f"Pinto version {__version__}"
    )
    parser.add_argument("--log-file", type=str, help="Path to write logs to")
    parser.add_argument(
        "-v", "--verbose", action="store_true", help="Log verbosity"
    )
    parser.add_argument(
        "-p",
        "--project",
        type=str,
        help=(
            "Path to pinto project. "
            "Will default to current working directory"
        ),
        default=os.getcwd(),
    )

    # now add subparsers for each subcommand we want to implement
    subparsers = parser.add_subparsers(dest="command")
    for command in _commands.values():
        command.build_parser(subparsers)


class Command(metaclass=CommandMeta):
    @classmethod
    def build_parser(cls, subparser: argparse.ArgumentParser) -> None:
        parser = subparser.add_parser(
            cls.name, description=cls.__doc__, add_help=False
        )
        cls.add_arguments(parser)
        cls._subparser = parser

    @classmethod
    def add_arguments(cls, parser: argparse.ArgumentParser):
        return

    @classmethod
    def check_and_run(
        cls, flags: argparse.Namespace, extra_args: List[str]
    ) -> None:
        if _add_help(cls.subparser, extra_args):
            if len(extra_args) == 1:
                cls.print_help(flags)
            else:
                cls.subparser._action_groups[1]._actions.pop(-1)
        cls.run(flags, extra_args)

    @classmethod
    def print_help(cls, flags: argparse.Namespace):
        cls.subparser.print_help()
        cls.subparser.exit()


class RunCommand(Command):
    """
    Either run a command in a project's environment,
    or run a pipeline of projects
    """

    @classmethod
    def add_arguments(cls, parser: argparse.ArgumentParser):
        parser.add_argument(
            "-e",
            "--environment",
            type=Path,
            help="Path to file specifying environment variables for run",
        )

    @classmethod
    def get_project(cls, project: str):
        # first see if the project_path is to a single project
        try:
            return Project(project)
        except ValueError as e:
            if "'tool.poetry'" in str(e):
                # if a KeyError got raised mentioning "poetry",
                # this means that the project in question doesn't
                # have a "tool.poetry" section of its pyproject, and so
                # it's assumed that this is a pipeline
                return Pipeline(project)
            else:
                raise

    @classmethod
    def print_help(cls, flags: argparse.Namespace) -> None:
        project = cls.get_project(flags.project)
        if isinstance(project, Project):
            msg = cls.subparser.format_help() + "\n"

            scripts = project.config["tool"]["poetry"]["scripts"].keys()
            if not project.venv.exists():
                msg += (
                    "Project {} hasn't been installed so no scripts "
                    "are currently available. Available scripts "
                    "after installation are:\n\t{}".format(
                        project.name, "\n\t".join(scripts)
                    )
                )
            else:
                installed, not_installed = [], []
                bin_path = project.venv.env_root / "bin"
                for script in scripts:
                    if (bin_path / script).exists():
                        installed.append(script)
                    else:
                        not_installed.append(script)

                if installed:
                    msg += "Scripts available in project {} are:\n\t{}".format(
                        project.name, "\n\t".join(installed)
                    )
                if not_installed:
                    msg += (
                        "Project {} has scripts which have not "
                        "yet been installed:\n\t{}".format(
                            project.name, "\n\t".join(not_installed)
                        )
                    )
            cls.subparser._print_message(msg + "\n")
        else:
            cls.subparser.print_help()
        cls.subparser.exit()

    @classmethod
    def run(cls, flags: argparse.Namespace, extra_args: List[str]) -> None:
        project = cls.get_project(flags.project)
        if isinstance(project, Pipeline):
            if len(extra_args) > 0:
                # pipelines don't take additional arguments,
                # so raise an error if any got passed
                raise RuntimeError(
                    "Unknown arguments {} passed for "
                    "executing pipeline at path {}".format(
                        extra_args, project.path
                    )
                )
            project.run(env=flags.environment)
        else:
            if len(extra_args) == 0:
                raise ValueError("Must provide a command to run!")
            project.run(*extra_args, env=flags.environment)


class BuildCommand(Command):
    """Build a project's environment"""

    @classmethod
    def add_arguments(cls, parser: argparse.ArgumentParser):
        parser.add_argument(
            "-f", "--force", action="store_true", help="Force rebuild"
        )
        parser.add_argument(
            "-E",
            "--extras",
            action="append",
            type=str,
            help="Extra dependency groups to install",
        )

    @classmethod
    def run(cls, flags: argparse.Namespace, extra_args: List[str]) -> None:
        if len(extra_args) > 0:
            raise RuntimeError(f"Unknown arguments {extra_args}")

        project = Project(flags.project)
        project.install(flags.force, extras=flags.extras)


def main():
    parser = argparse.ArgumentParser(add_help=False)
    build_base_parser(parser)

    # executing a project allows for additional arbitrary
    # arguments to execute in the project environment,
    # so hang on to any args the parser doesn't understand
    flags, extra_args = parser.parse_known_args()

    # set up logging based on some of the top level args
    logger.setLevel(logging.DEBUG if flags.verbose else logging.INFO)
    logger.addHandler(logging.StreamHandler(stream=sys.stdout))

    # set up a file handler if we specified a file to write our logs to
    if flags.log_file is not None:
        handler = logging.FileHandler(filename=flags.log_file, mode="w")
        logger.addHandler(handler)

    # run the indicated pinto command
    try:
        command = _commands[flags.command]
    except KeyError:
        # if we didn't specify a command at all,
        # see if we passed a help flag at the
        # root level
        if flags.command is None:
            if _add_help(parser, extra_args):
                parser.print_help()
                parser.exit()
            else:
                parser.error(
                    "Must specify a command. Available commands "
                    "are:\n\t{}".format("\n\t".join(_commands.keys()))
                )
        else:
            # otherwise we specified an invalid command
            parser.error(f"Unrecognized command {flags.command}")
    else:
        command.check_and_run(flags, extra_args)


if __name__ == "__main__":
    main()
