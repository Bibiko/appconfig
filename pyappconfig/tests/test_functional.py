from mock import Mock, MagicMock, patch
from clldutils.path import Path


def _make_app(name='testapp'):
    from pyappconfig.config import Config, App

    return Config(App, Path(__file__).parent.joinpath('fixtures', 'apps.ini'))[name]


@patch.multiple('pyappconfig.util',
                time=Mock(),
                getpass=Mock(return_value='password'),
                confirm=Mock(return_value=True),
                exists=Mock(return_value=True),
                virtualenv=MagicMock(),
                sudo=Mock(return_value='/usr/venvs/__init__.py'),
                run=Mock(return_value='{"status": "ok"}'),
                local=Mock(),
                env=MagicMock(),
                service=Mock(),
                cd=MagicMock(),
                require=Mock(),
                postgres=Mock(),
                get_input=Mock(return_value='app'),
                import_module=Mock(return_value=None),
                upload_template=Mock())
def test_deploy():
    from pyappconfig.util import deploy

    app = _make_app()
    assert app.src
    deploy(app, 'test', with_files=False)
    deploy(app, 'test', with_alembic=True, with_files=False)
    deploy(app, 'production', with_files=False)


@patch.multiple('pyappconfig.tasks', execute=Mock())
def test_tasks():
    import pyappconfig.tasks
    from pyappconfig.tasks import (
        init, deploy, start, stop, maintenance, cache, uncache, run_script,
        create_downloads, uninstall,
    )

    pyappconfig.tasks.APP = _make_app()
    deploy('test')
    stop('test')
    start('test')
    maintenance('test')
    cache()
    uncache()
    run_script('test', 'script')
    create_downloads('test')
    uninstall('test')
