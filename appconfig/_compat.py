# _compat.py - Python 2/3 compatibility

import sys

PY2 = sys.version_info < (3,)


if PY2:  # pragma: no cover
    import pathlib2 as pathlib

    iteritems = lambda x: x.iteritems()
    itervalues = lambda x: x.itervalues()

else:  # pragma: no cover
    import pathlib

    iteritems = lambda x: iter(x.items())
    itervalues = lambda x: iter(x.values())
