# test_tasks.py

from __future__ import unicode_literals

import pytest

from appconfig import tasks


pytestmark = pytest.mark.usefixtures('APP')


def test_deploy(mocker):
    mocker.patch.multiple('appconfig.tasks',
        time=mocker.Mock(),
        getpass=mocker.Mock(**{'getpass.return_value': 'password'}),
        pathlib=mocker.DEFAULT,
        env=mocker.DEFAULT,
        prompt=mocker.Mock(return_value='app'),
        sudo=mocker.Mock(return_value='/usr/venvs/__init__.py'),
        run=mocker.Mock(return_value='{"status": "ok"}'),
        cd=mocker.DEFAULT,
        local=mocker.Mock(),
        exists=mocker.Mock(return_value=True),
        confirm=mocker.Mock(return_value=True),
        require=mocker.Mock(),
        files=mocker.Mock(),
        python=mocker.DEFAULT,
        postgres=mocker.Mock(),
        service=mocker.Mock(),
        supervisor=mocker.Mock(),
        system=mocker.Mock(**{'distrib_id.return_value': 'Ubuntu',
                              'distrib_codename.return_value': 'xenial'}),
    )

    tasks.deploy('test')
    tasks.deploy('test', with_alembic=True)
    tasks.deploy('production')
    tasks.deploy('production', with_alembic=True)


@pytest.mark.usefixtures('execute')
def test_tasks():
    tasks.deploy('test')
    tasks.start('test')
    tasks.stop('test')
    tasks.uninstall('test')
    tasks.cache()
    tasks.uncache()
    tasks.run_script('test', 'script')
    tasks.create_downloads('test')
    tasks.copy_rdfdump('test')
    tasks.pip_freeze()
