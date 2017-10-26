# tools.py

import os
import sys
import contextlib


@contextlib.contextmanager
def working_directory(path):
    """A context manager which changes the working directory to the given
    path, and then changes it back to its previous value on exit.
    """
    prev_cwd = os.getcwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(prev_cwd)


def caller_dirname(steps=1):
    frame = sys._getframe(steps + 1)

    try:
        path = os.path.dirname(frame.f_code.co_filename)
    finally:
        del frame

    return os.path.basename(path)
