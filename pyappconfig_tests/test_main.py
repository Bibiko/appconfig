# test_main.py

from __future__ import unicode_literals

from pyappconfig import __main__


def test_check():
    assert callable(__main__.check)
