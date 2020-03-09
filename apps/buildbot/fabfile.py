import os
import pathlib

from fabric.api import local, env
from fabric.contrib.console import confirm
from fabtools import require, nginx, system, service

from appconfig import systemd
from appconfig.tasks import letsencrypt
from appconfig.tasks import task_app_from_environment
from appconfig.tasks.deployment import require_venv, require_nginx


@task_app_from_environment
def deploy(app):
    assert system.distrib_id() == 'Ubuntu'
    lsb_codename = system.distrib_codename()
    if lsb_codename != 'xenial':
        raise ValueError('unsupported platform: %s' % lsb_codename)

    # See whether the local appconfig clone is up-to-date with the remot master:
    remote_repo = local('git ls-remote git@github.com:shh-dlce/appconfig.git HEAD | awk \'{ print $1}\'')
    local_clone = local('git rev-parse HEAD')

    if remote_repo != local_clone:
        if confirm('Local appconfig clone is not up-to-date '
                   'with remote master, continue?', default=False):
            print("Continuing deployment.")
        else:
            print("Deployment aborted.")
            return

    require.deb.packages(getattr(app, 'require_deb_%s' % lsb_codename) + app.require_deb)
    require.users.user(app.name, create_home=True, shell='/bin/bash')
    require.directory(str(app.www_dir), use_sudo=True)
    require.directory(str(app.www_dir / 'files'), use_sudo=True)

    # Test and production instances are publicly accessible over HTTPS.
    letsencrypt.require_certbot()
    letsencrypt.require_cert(env.host)
    if env.environment == 'production':
        letsencrypt.require_cert(app)


    #
    # Create a virtualenv for the app and install the app package in development mode, i.e. with
    # repository working copy in /usr/venvs/<APP>/src
    #
    require_venv(
        app.venv_dir,
        require_packages=[app.app_pkg] + app.require_pip,
    )

    require_nginx(dict(app=app))


    #start.execute_inner(app)
    #check(app)
    if env.environment == 'production':
        systemd.enable(app, pathlib.Path(os.getcwd()) / 'systemd')
