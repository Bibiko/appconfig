import pathlib
import functools

from fabric.api import env, sudo, shell_env
from fabric.context_managers import cd
from fabtools import require, system, python
from fabtools.require import git

from appconfig import systemd
from appconfig.tasks import letsencrypt
from appconfig.tasks import task_app_from_environment, init
from appconfig.tasks.deployment import require_venv, require_nginx

CATALOGS = {
    'glottolog': 'https://github.com/glottolog/glottolog',
    'concepticon': 'https://github.com/concepticon/concepticon-data',
    'clts': 'https://github.com/cldf-clts/clts',
}

init()


def _ctl(cmd, warn_only=False):
    for proc in ['master', 'worker']:
        sudo("systemctl {0} buildbot-{1}".format(cmd, proc), warn_only=warn_only)


start = functools.partial(_ctl, 'start')
stop = functools.partial(_ctl, 'stop')


def require_catalogversions(app, **kw):
    for name, url in CATALOGS.items():
        if name in kw:
            with cd(str(app.home_dir / url.split('/')[-1])):
                sudo('git fetch origin', user=app.name)
                sudo('git checkout {}'.format(kw[name]), user=app.name)


@task_app_from_environment
def catalogversions(app, **kw):
    """
    usage: fab catalogversions:production,glottolog=v4.1,concepticon=v2.3,clts=v1.4.1
    """
    require_catalogversions(app, **kw)


@task_app_from_environment
def deploy(app):
    assert system.distrib_id() == "Ubuntu"
    assert env.environment == "production"

    require.deb.packages(app.require_deb + ["libcairo2", "python3-venv"])
    require.users.user(app.name, create_home=True, shell="/bin/bash")

    with shell_env(SYSTEMD_PAGER=''):
        require.nginx.server()

    letsencrypt.require_certbot()
    letsencrypt.require_cert(env.host)
    letsencrypt.require_cert(app)

    require_nginx(dict(app=app))

    git.working_copy(
        "https://github.com/cldf/cldf-buildbot.git",
        path=str(app.home_dir / "cldf-buildbot"),
        user=app.name,
        use_sudo=True,
        update=True,
    )
    for name, url in CATALOGS.items():
        git.working_copy(
            url + ".git",
            path=str(app.home_dir / url.split('/')[-1]),
            user=app.name,
            use_sudo=True,
            update=False,
        )
    require_catalogversions(app, **app.extra)

    require_venv(
        app.venv_dir, requirements=str(app.home_dir / "cldf-buildbot" / "requirements.txt"))

    require.directory(str(app.home_dir / "master"), owner=app.name, use_sudo=True)
    require.directory(str(app.home_dir / "worker"), owner=app.name, use_sudo=True)
    require.files.file(
        path=str(app.home_dir / "master" / "settings.py"),
        owner=app.name,
        contents="URL='https://{}/'".format(app.domain),
        use_sudo=True,
        mode="777",
    )

    bbdo = functools.partial(sudo, user=app.name)
    bbdo("cp {0.home_dir}/cldf-buildbot/reposlist.json {0.home_dir}/master".format(app))
    bbdo("cp {0.home_dir}/cldf-buildbot/config.py {0.home_dir}/master".format(app))

    stop(warn_only=True)

    with python.virtualenv(str(app.venv_dir)):
        bbdo("buildbot create-master -c config.py {0.home_dir}/master".format(app))
        bbdo("buildbot-worker create-worker {0.home_dir}/worker localhost worker pass".format(app))

    systemd.enable(app, pathlib.Path(__file__).parent / "systemd")
    sudo("systemctl daemon-reload", warn_only=True)
    start()
