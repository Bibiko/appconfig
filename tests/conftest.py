# conftest.py - pytest fixtures

from __future__ import unicode_literals

import sys
if sys.version_info < (3,):  
    import pathlib2 as pathlib
else:
    import pathlib

import pytest

from appconfig.config import Config

TEST_DIR = pathlib.Path(__file__).parent


@pytest.fixture(scope='session')
def config(filepath=TEST_DIR / 'apps.ini'):
    with pytest.warns(UserWarning, match='missing fabfile dir: testapp'):
        result = Config.from_file(filepath)
    return result


@pytest.fixture(scope='session')
def app(config, name='testapp'):
    return config[name]


@pytest.fixture
def APP(mocker, app):
    yield mocker.patch('appconfig.tasks.APP', app)
