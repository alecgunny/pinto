import os
from contextlib import contextmanager

from pinto.logging import logger


@contextmanager
def temp_env_set(**kwargs):
    unset = {}
    for key, value in kwargs.items():
        try:
            old_value = os.environ[key]
        except KeyError:
            logger.debug(
                "Setting environment variable {} to {}".format(key, value)
            )
            pass
        else:
            logger.debug(
                "Setting environment variable {} from {} to {}".format(
                    key, old_value, value
                )
            )
            unset[key] = old_value

        os.environ[key] = value
    yield

    for key, value in kwargs.items():
        try:
            old_value = unset[key]
        except KeyError:
            logger.debug(f"Removing environment variable {key}")
            os.environ.pop(key)
        else:
            logger.debug(
                "Resetting environment variable {} to {}".format(
                    key, old_value
                )
            )
            os.environ[key] = old_value
