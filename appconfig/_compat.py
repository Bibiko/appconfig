# _compat.py - Python 2/3 compatibility

import sys

PY2 = sys.version_info < (3,)


if PY2:  # pragma: no cover
    import pathlib2 as pathlib
    from urllib2 import urlopen, HTTPError

    iteritems = lambda x: x.iteritems()
    itervalues = lambda x: x.itervalues()

else:  # pragma: no cover
    import pathlib
    from urllib.request import urlopen, HTTPError

    iteritems = lambda x: iter(x.items())
    itervalues = lambda x: iter(x.values())
