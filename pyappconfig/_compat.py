# _compat.py - Python 2/3 compatibility

import sys

PY2 = sys.version_info < (3,)


if PY2:  # pragma: no cover
    import pathlib2 as pathlib

    input = raw_input

else:  # pragma: no cover
    import pathlib

    input = input
