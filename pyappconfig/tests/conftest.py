# conftest.py

import pytest

from pyappconfig._compat import pathlib

FIXTURES = pathlib.Path(__file__) / '..' / 'fixtures'


@pytest.fixture
def app(name='testapp'):
    from pyappconfig.config import Config, App

    filename = FIXTURES / 'apps.ini'
    apps = Config(App, filename)

    return apps[name]
