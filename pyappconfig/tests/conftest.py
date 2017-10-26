# conftest.py

import pytest

from pyappconfig._compat import pathlib

FIXTURES = pathlib.Path(__file__).parent / 'fixtures'


@pytest.fixture
def app(name='testapp'):
    from pyappconfig.config import Config, App

    return Config(App, FIXTURES / 'apps.ini')[name]
