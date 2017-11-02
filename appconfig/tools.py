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


def duplicates(iterable):
    """Return duplicated (hashable) items from iterable preservig order.

    >>> duplicates([1, 2, 2, 3, 1])
    [2, 1]
    """
    seen = set()
    return [i for i in iterable if i in seen or seen.add(i)]
