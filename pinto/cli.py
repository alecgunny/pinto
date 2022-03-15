import argparse
import logging
import sys

from pinto import __version__
from pinto.logging import logger
from pinto.project import Pipeline, Project


def main():
    parser = argparse.ArgumentParser()

    # add top level arguments
    parser.add_argument(
        "--version", action="version", version=f"Pinto version {__version__}"
    )
    parser.add_argument("--log-file", type=str, help="Path to write logs to")
    parser.add_argument(
        "-v", "--verbose", action="store_true", help="Log verbosity"
    )

    # now add subparsers for each subcommand we want to implement
    subparsers = parser.add_subparsers(dest="subcommand")

    # add a parser for executing a command in a
    # project, or executing a pipeline end-to-end
    subparser = subparsers.add_parser(
        "run", description="Run a project or pipeline"
    )
    subparser.add_argument(
        "project_path", type=str, help="Project or pipeline to run"
    )

    # add a parser for just building the environment
    # for a specified project
    subparser = subparsers.add_parser("build", description="Build a project")
    subparser.add_argument("project_path", type=str, help="Project to build")
    subparser.add_argument(
        "-f", "--force", action="store_true", help="Force rebuild"
    )

    # executing a project allows for additional arbitrary
    # arguments to execute in the project environment,
    # so hang on to any args the parser doesn't understand
    args, unknown_args = parser.parse_known_args()

    # set up logging based on some of the top level args
    logger.setLevel(logging.DEBUG if args.verbose else logging.INFO)
    logger.addHandler(logging.StreamHandler(stream=sys.stdout))

    # set up a file handler if we specified a file
    # to write our logs to
    if args.log_file is not None:
        handler = logging.FileHandler(filename=args.log_file, mode="w")
        logger.addHandler(handler)

    if args.subcommand == "run":
        # first see if the project_path is to a single project
        try:
            project = Project(args.project_path)
        except ValueError as e:
            if "'tool.poetry'" in str(e):
                # if a KeyError got raised mentioning "poetry",
                # this means that the project in question doesn't
                # have a "tool.poetry" section of its pyproject, and so
                # it's assumed that this is a pipeline
                pipeline = Pipeline(args.project_path)

                if len(unknown_args) > 0:
                    # pipelines don't take additional arguments,
                    # so raise an error if any got passed
                    raise parser.error(
                        "Unknown arguments {} passed for "
                        "executing pipeline at path {}".format(
                            unknown_args, pipeline.path
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
            stdout = project.run(*unknown_args)
            logger.info(stdout)

    elif args.subcommand == "build":
        if len(unknown_args) > 0:
            raise parser.error(f"Unknown arguments {unknown_args}")

        project = Project(args.project_path)
        project.install(args.force)


if __name__ == "__main__":
    main()
