# test_cli.py

from __future__ import unicode_literals

from pyappconfig import __main__ as cli


def test_check():
    assert callable(cli.check)
