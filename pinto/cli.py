import argparse
import logging
import os
import re
import sys
from collections import OrderedDict
from typing import List

from pinto import __version__
from pinto.logging import logger
from pinto.project import Pipeline, Project

_commands = OrderedDict()


class CommandMeta(type):
    def __new__(cls, clsname, bases, attrs):
        obj = super().__new__(cls, clsname, bases, attrs)
        if obj.name:
            _commands[obj.name] = obj
        return obj

    @property
    def name(cls):
        return re.sub("Command$", "", cls.__name__).lower()


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
        parser = subparser.add_parser(cls.name, description=cls.__doc__)
        cls.add_arguments(parser)

    @classmethod
    def add_arguments(cls, parser: argparse.ArgumentParser):
        return


class RunCommand(Command):
    """
    Either run a command in a project's environment,
    or run a pipeline of projects
    """

    @classmethod
    def run(cls, flags: argparse.Namespace, extra_args: List[str]) -> None:
        # first see if the project_path is to a single project
        try:
            project = Project(flags.project)
        except ValueError as e:
            if "'tool.poetry'" in str(e):
                # if a KeyError got raised mentioning "poetry",
                # this means that the project in question doesn't
                # have a "tool.poetry" section of its pyproject, and so
                # it's assumed that this is a pipeline
                pipeline = Pipeline(flags.project)

                if len(extra_args) > 0:
                    # pipelines don't take additional arguments,
                    # so raise an error if any got passed
                    raise RuntimeError(
                        "Unknown arguments {} passed for "
                        "executing pipeline at path {}".format(
                            extra_args, pipeline.path
                        )
                    )

                # execute the pipeline
                pipeline.run()
            else:
                # otherwise this is some other KeyError, raise it
                raise
        else:
            # if the pyproject has a "tool.poetry" table,
            # we assume that this is a single project and
            # execute any additional arguments passed
            if len(extra_args) == 0:
                raise ValueError("Must provide a command to run!")

            stdout = project.run(*extra_args)
            logger.info(stdout)


class BuildCommand(Command):
    """Build a project's environment"""

    @classmethod
    def add_arguments(self, parser: argparse.ArgumentParser):
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
    parser = argparse.ArgumentParser()
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
    command = _commands[flags.command]
    command.run(flags, extra_args)


if __name__ == "__main__":
    main()
