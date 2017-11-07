# test_tasks.py

from __future__ import unicode_literals

from appconfig import tasks


def test_init(mocker, app_name='nonname'):
    mocker.patch('appconfig.APPS', {app_name: mocker.sentinel.app})

    try:
        tasks.init(app_name)
        assert tasks.APP is mocker.sentinel.app
    finally:
        tasks.APP = None


def test_tasks(mocker):
    mocker.patch('appconfig.tasks.fabric.api.execute', autospec=True)

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
