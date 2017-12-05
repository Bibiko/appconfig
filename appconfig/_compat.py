# _compat.py - Python 2/3 compatibility

import sys

try:
    import pathlib2 as pathlib
except ImportError:
    import pathlib

PY2 = sys.version_info < (3,)


if PY2:  # pragma: no cover
    from urllib2 import urlopen, HTTPError

    iteritems = lambda x: x.iteritems()
    itervalues = lambda x: x.itervalues()

else:  # pragma: no cover
    from urllib.request import urlopen, HTTPError

    iteritems = lambda x: iter(x.items())
    itervalues = lambda x: iter(x.values())
