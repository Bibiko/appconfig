# _compat.py - Python 2/3 compatibility
# pragma: no cover

import sys

PY2 = sys.version_info < (3,)


if PY2:  
    import pathlib2 as pathlib

    input = raw_input

else:
    import pathlib

    input = input
