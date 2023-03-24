import os
from contextlib import contextmanager
from typing import Literal, Optional

from pinto.logging import logger

Actions = Literal["replace", "append", "insert"]


def get_new_value(new: str, old: Optional[str], action: Actions) -> str:
    if action == "replace" or old is None:
        return new
    elif action == "append":
        return f"{old}:{new}"
    elif action == "insert":
        return f"{new}:{old}"
    else:
        raise ValueError(f"Unknown environment action f{action}")


@contextmanager
def temp_env_set(action: Actions = "replace", **kwargs):
    unset = {}
    for key, value in kwargs.items():
        try:
            old_value = os.environ[key]
        except KeyError:
            old_value = None
        else:
            unset[key] = old_value

        new_value = get_new_value(value, old_value, action)
        logger.debug(
            "Setting environment variable {} from {} to {}".format(
                key, old_value, new_value
            )
        )
        os.environ[key] = new_value
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
