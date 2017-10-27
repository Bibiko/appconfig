# tools.py - one-trick ponies

import os
import sys

__all__ = ['caller_dirname']


def caller_dirname(steps=1):
    frame = sys._getframe(steps + 1)

    try:
        path = os.path.dirname(frame.f_code.co_filename)
    finally:
        del frame

    return os.path.basename(path)
