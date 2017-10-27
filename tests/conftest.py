# conftest.py

from __future__ import unicode_literals

import sys
if sys.version_info < (3,):  
    import pathlib2 as pathlib
else:
    import pathlib

import pytest

from pyappconfig import config

FIXTURES = pathlib.Path(__file__).parent / 'fixtures'


@pytest.fixture
def app(name='testapp'):
    result = config.Config(config.App, FIXTURES / 'apps.ini')[name]
    assert result.src
    return result
