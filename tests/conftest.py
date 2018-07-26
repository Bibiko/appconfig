# conftest.py - pytest fixtures

from __future__ import unicode_literals

try:
    import pathlib2 as pathlib
except ImportError:
    import pathlib

import pytest

from appconfig.config import Config


@pytest.fixture(scope='session')
def testdir():
    return pathlib.Path(__file__).parent


@pytest.fixture(scope='session')
def config(testdir):
    with pytest.warns(UserWarning, match='missing fabfile dir: testapp'):
        result = Config.from_file(testdir / 'apps.ini')
    return result


@pytest.fixture(scope='session')
def app(config, name='testapp'):
    return config[name]


@pytest.fixture
def APP(mocker, app):
    yield mocker.patch('appconfig.tasks.APP', app)
