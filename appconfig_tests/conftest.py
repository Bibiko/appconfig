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
def config(filename=TEST_DIR / 'apps.ini'):
    with pytest.warns(UserWarning) as w:
        result = Config.from_file(filename)
    # TODO: use match when avail https://github.com/pytest-dev/pytest/pull/2711
    assert ['%s' % _.message for _ in w] == ['missing fabfile dir: testapp']
    return result


@pytest.fixture(scope='session')
def app(config, name='testapp'):
    return config[name]


@pytest.fixture
def APP(mocker, app):
    yield mocker.patch('appconfig.tasks.APP', app)


@pytest.fixture
def execute(mocker):
    yield mocker.patch('appconfig.tasks.execute', new_callable=mocker.Mock)
