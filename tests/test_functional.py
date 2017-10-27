# test_functional.py

from __future__ import unicode_literals

from pyappconfig import tasks


def test_deploy(mocker, app):
    mocker.patch.multiple('pyappconfig.tasks',
        time=mocker.Mock(),
        getpass=mocker.Mock(return_value='password'),
        confirm=mocker.Mock(return_value=True),
        exists=mocker.Mock(return_value=True),
        virtualenv=mocker.MagicMock(),
        sudo=mocker.Mock(return_value='/usr/venvs/__init__.py'),
        run=mocker.Mock(return_value='{"status": "ok"}'),
        local=mocker.Mock(),
        env=mocker.MagicMock(),
        service=mocker.Mock(),
        cd=mocker.MagicMock(),
        require=mocker.Mock(),
        postgres=mocker.Mock(),
        get_input=mocker.Mock(return_value='app'),
        import_module=mocker.Mock(return_value=None),
        upload_template=mocker.Mock(),
        APP=app)

    tasks.deploy('test', with_files=False)
    tasks.deploy('test', with_alembic=True, with_files=False)
    tasks.deploy('production', with_files=False)


def test_tasks(mocker, app):
    mocker.patch.multiple('pyappconfig.tasks', execute=mocker.Mock(), APP=app)

    tasks.deploy('test')
    tasks.stop('test')
    tasks.start('test')
    tasks.maintenance('test')
    tasks.cache()
    tasks.uncache()
    tasks.run_script('test', 'script')
    tasks.create_downloads('test')
    tasks.uninstall('test')
