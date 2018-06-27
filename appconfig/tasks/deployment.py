# deployment.py

import os
import json
import time
import getpass
import platform
import tempfile
import functools
import pathlib

from fabric.api import env, settings, shell_env, prompt, sudo, run, cd, local
from fabric.contrib.files import exists, comment
from fabric.contrib.console import confirm
from fabtools import (
    require, files, python, postgres, nginx, system, service, supervisor, user)

from .. import PKG_DIR
from .. import helpers

from . import task_app_from_environment

__all__ = ['deploy', 'start', 'stop', 'uninstall']

PLATFORM = platform.system().lower()

VBOX_HOSTNAMES = {'vbox', 'xenial'}  # run on localhost

PG_COLLKEY_DIR = PKG_DIR / 'pg_collkey-v0.5'

TEMPLATE_DIR = PKG_DIR / 'templates'


def template_context(app, workers=3, with_blog=False,):
    ctx = {
        'SITE': {'test': False, 'production': True}[env.environment],
        'TEST': {'production': False, 'test': True}[env.environment],
        'VBOX_LOCALHOST': env.host_string in VBOX_HOSTNAMES,
        'app': app, 'env': env, 'workers': workers,
        'auth': '',
        'bloghost': '', 'bloguser': '', 'blogpassword': '',
    }

    if with_blog:  # pragma: no cover
        for key, default in [
            ('bloghost', 'blog.%s' % app.domain),
            ('bloguser', app.name),
            ('blogpassword', ''),
        ]:
            ctx[key] = os.environ.get(('%s_%s' % (app.name, key)).upper()) or \
                       prompt('Blog %s:' % key[4:], default=default)
        assert ctx['blogpassword']

    return ctx


def sudo_upload_template(template, dest, context=None,
                         mode=None, user_own=None, **kwargs):
    """
    A wrapper around upload_template in fabtools. Used to upload template files.

    :param user_own: Set to user name that's supposed to own the file.
        If it is None, the uploading user's rights are used.
    :type user_own: str

    :return: None
    """
    if kwargs:
        if context is None:
            context = kwargs
        else:
            context = context.copy()
            context.update(kwargs)
    files.upload_template(template, dest, context, use_jinja=True,
                          template_dir=str(TEMPLATE_DIR), use_sudo=True,
                          backup=False, mode=mode, chown=True, user=user_own)


@task_app_from_environment
def start(app):
    """start app by changing the supervisord config"""
    require_supervisor(app.supervisor, app)
    supervisor.update_config()
    service.reload('nginx')


@task_app_from_environment
def stop(app, maintenance_hours=1):
    """pause app by changing the supervisord config

    create a maintenance page giving a date when we expect the service will be back
    :param maintenance_hours: Number of hours we expect the downtime to last.
    """
    if maintenance_hours is not None:
        require.directory(str(app.www_dir), use_sudo=True)
        timestamp = helpers.strfnow(add_hours=maintenance_hours)
        sudo_upload_template('503.html', dest=str(app.www_dir / '503.html'),
                             app_name=app.name, timestamp=timestamp)

    require_supervisor(app.supervisor, app, pause=True)
    supervisor.update_config()
    service.reload('nginx')


def require_supervisor(filepath, app, pause=False):
    # TODO: consider require.supervisor.process
    sudo_upload_template('supervisor.conf', dest=str(filepath), mode='644',
                         name=app.name, gunicorn=app.gunicorn, config=app.config,
                         user=app.name, group=app.name, pid_file=app.gunicorn_pid,
                         error_log=app.error_log, PAUSE=pause)


@task_app_from_environment
def uninstall(app):  # pragma: no cover
    """uninstall the app"""
    for path in (app.nginx_location, app.nginx_site, app.venv_dir):
        if exists(str(path)):
            files.remove(str(path), recursive=True, use_sudo=True)

    stop.execute_inner(app)
    if user.exists(app.name):
        sudo('dropdb --if-exists %s' % app.name, user='postgres')
        sudo('userdel -rf %s' % app.name)

    if exists(str(app.supervisor)):
        files.remove(str(app.supervisor), recursive=True, use_sudo=True)

    supervisor.update_config()
    service.reload('nginx')


@task_app_from_environment
def deploy(app, with_blog=None, with_alembic=False):
    """deploy the app"""
    assert system.distrib_id() == 'Ubuntu'
    lsb_codename = system.distrib_codename()
    if lsb_codename != 'xenial':
        raise ValueError('unsupported platform: %s' % lsb_codename)

    require.deb.packages(getattr(app, 'require_deb_%s' % lsb_codename) +
                         app.require_deb)

    require.users.user(app.name, create_home=True, shell='/bin/bash')
    require.directory(str(app.www_dir), use_sudo=True)
    require.directory(str(app.www_dir / 'files'), use_sudo=True)

    require_logging(app.log_dir,
                    logrotate=app.logrotate,
                    access_log=app.access_log, error_log=app.error_log)

    workers = 3 if app.workers > 3 and env.environment == 'test' else app.workers
    with_blog = with_blog if with_blog is not None else app.with_blog
    ctx = template_context(app, workers=workers, with_blog=with_blog)

    if app.stack == 'clld':
        require_venv(
            app.venv_dir, venv_python='python3',
            require_packages=[app.app_pkg] + app.require_pip,
            assets_name=app.name)

    require_nginx(ctx,
                  default_site=app.nginx_default_site,
                  site=app.nginx_site,
                  location=app.nginx_location,
                  logrotate=app.logrotate,
                  venv_dir=app.venv_dir,
                  htpasswd_file=app.nginx_htpasswd,
                  htpasswd_user=app.name,
                  with_clld=app.stack == 'clld',
                  public=app.public)

    if app.stack == 'soundcomparisons':
        #
        # service php-fpm restart (or similar)
        #
        service.reload('nginx')
        return

    require_bibutils()

    require_postgres(app.name,
                     user_name=app.name, user_password=app.name,
                     pg_unaccent=app.pg_unaccent, pg_collkey=app.pg_collkey,
                     lsb_codename=lsb_codename)

    require_config(app.config, app, ctx)

    # if gunicorn runs, make it gracefully reload the app by sending HUP
    # TODO: consider 'supervisorctl signal HUP $name' instead (xenial+)
    sudo('( [ -f {0} ] && kill -0 $(cat {0}) 2> /dev/null '
         '&& kill -HUP $(cat {0}) ) || echo no reload '.format(app.gunicorn_pid))

    if not with_alembic and confirm('Recreate database?', default=False):
        stop.execute_inner(app)
        upload_local_sqldump(app, ctx, lsb_codename)
    elif exists(str(app.src_dir / 'alembic.ini')) and confirm('Upgrade database?', default=False):
        # Note: stopping the app is not strictly necessary, because
        #       the alembic revisions run in separate transactions!
        stop.execute_inner(app, maintenance_hours=app.deploy_duration)
        alembic_upgrade_head(app, ctx)

    start.execute_inner(app)

    time.sleep(5)
    res = run('curl http://localhost:%s/_ping' % app.port)
    assert json.loads(res)['status'] == 'ok'


def require_bibutils(executable='/usr/local/bin/bib2xml',
                     url='https://sourceforge.net/projects/bibutils/files/'
                         'bibutils_6.2_src.tgz/download'):
    if not exists(executable):
        tgz = url.partition('/download')[0].rpartition('/')[2]
        tdir = tgz.partition('_src.tgz')[0]
        with cd('/tmp'):
            require.file(tgz, url=url, mode='')
            run('tar xzf %s' % tgz)
            with cd(tdir):
                run('./configure')
                run('make')
                sudo('make install')


def require_postgres(database_name, user_name, user_password, pg_unaccent, pg_collkey,
                     lsb_codename, drop=False):
    if drop:
        with cd('/var/lib/postgresql'):
            sudo('dropdb %s' % database_name, user='postgres')

    with shell_env(SYSTEMD_PAGER=''):
        require.postgres.server()
        require.postgres.user(user_name, password=user_password)
        require.postgres.database(database_name, owner=user_name)

    if pg_unaccent:
        sql = 'CREATE EXTENSION IF NOT EXISTS unaccent WITH SCHEMA public;'
        sudo('psql -c "%s" -d %s' % (sql, database_name), user='postgres')

    if pg_collkey:
        pg_dir, = run('find /usr/lib/postgresql/ -mindepth 1 -maxdepth 1 -type d').splitlines()
        pg_version = pathlib.PurePosixPath(pg_dir).name
        if not exists('/usr/lib/postgresql/%s/lib/collkey_icu.so' % pg_version):
            require.deb.packages(['postgresql-server-dev-%s' % pg_version, 'libicu-dev'])
            with cd('/tmp'):
                sudo_upload_template('pg_collkey.Makefile', dest='Makefile', pg_version=pg_version)
                require.file('collkey_icu.c', source=str(PG_COLLKEY_DIR / 'collkey_icu.c'))
                run('make')
                sudo('make install')
        with cd('/tmp'):
            require.file('collkey_icu.sql', source=str(PG_COLLKEY_DIR / 'collkey_icu.sql'))
            sudo('psql -f collkey_icu.sql -d %s' % database_name, user='postgres')


def require_config(filepath, app, ctx):
    # We only set add a setting clld.files, if the corresponding directory exists;
    # otherwise the app would throw an error on startup.
    files_dir = app.www_dir / 'files'
    files = files_dir if exists(str(files_dir)) else None
    sudo_upload_template('config.ini', dest=str(filepath), context=ctx, files=files)


def require_venv(directory, venv_python, require_packages, assets_name):
    require.directory(str(directory), use_sudo=True)

    with settings(sudo_prefix=env.sudo_prefix + ' -H'):  # set HOME for pip log/cache
        require.python.virtualenv(str(directory), venv_python='python3', use_sudo=True)

        with python.virtualenv(str(directory)):
            require.python.packages(require_packages, use_sudo=True)
            sudo('webassets -m %s.assets build' % assets_name)


def require_logging(log_dir, logrotate, access_log, error_log):
    require.directory(str(log_dir), use_sudo=True)

    if env.environment == 'production':
        sudo_upload_template('logrotate.conf', dest=str(logrotate),
                             access_log=access_log, error_log=error_log)


def require_nginx(ctx, default_site, site, location, logrotate, venv_dir,
                  htpasswd_file, htpasswd_user, with_clld=False, public=False):
    with shell_env(SYSTEMD_PAGER=''):
        require.nginx.server()

    auth, admin_auth = http_auth(htpasswd_file, username=htpasswd_user, public=public)

    # TODO: consider require.nginx.site
    upload_app = functools.partial(
        sudo_upload_template, 
        'nginx-app.conf',
        context=ctx,
        clld_dir=get_clld_dir(venv_dir) if with_clld else '',
        auth=auth,
        admin_auth=admin_auth)

    if ctx['SITE']:
        upload_app(dest=str(site))
        nginx.enable(site.name)
        if ctx['VBOX_LOCALHOST']:
            comment(default_site, 'server_name localhost;', use_sudo=True)
    else:  # test environment
        require.directory(str(location.parent), use_sudo=True)
        upload_app(dest=str(location))
        sudo_upload_template('nginx-default.conf', dest=str(default_site))


def get_clld_dir(venv_dir):
    # /usr/venvs/<app_name>/local/lib/python<version>/site-packages/clld/__init__.pyc
    with python.virtualenv(str(venv_dir)):
        stdout = sudo('python -c "import clld; print(clld.__file__)"')
    clld_path = pathlib.PurePosixPath(stdout.split()[-1])
    return clld_path.parent


def http_auth(htpasswd_file, username, public=False):
    if not (public and env.environment == 'production'):
        userpass = getpass.getpass(
            prompt='HTTP Basic Auth password for user %s: ' % username)
    else:
        userpass = None
    pwds = {username: userpass, 'admin': ''}
    while not pwds['admin']:
        pwds['admin'] = getpass.getpass(
            prompt='HTTP Basic Auth password for user admin: ')

    require.directory(str(htpasswd_file.parent), use_sudo=True)
    pairs = [(u, p) for u, p in pwds.items() if p]
    for opts, pairs in [('-bdc', pairs[:1]), ('-bd', pairs[1:])]:
        for u, p in pairs:
            sudo('htpasswd %s %s %s %s' % (opts, htpasswd_file, u, p))

    auth = ('proxy_set_header Authorization $http_authorization;\n'
            'proxy_pass_header Authorization;\n'
            'auth_basic "%s";\n'
            'auth_basic_user_file %s;\n' % (username, htpasswd_file))
    return auth if userpass else '', auth


def upload_local_sqldump(app, ctx, lsb_codename):
    db_name = prompt('Replace with dump of local database:', default=app.name)
    sqldump = pathlib.Path(tempfile.mktemp(suffix='.sql.gz', prefix='%s-' % db_name))
    target = pathlib.PurePosixPath('/tmp') / sqldump.name

    db_user = '-U postgres ' if PLATFORM == 'windows' else ''
    local('pg_dump %s--no-owner --no-acl -Z 9 -f %s %s' % (db_user, sqldump, db_name))

    require.file(str(target), source=str(sqldump))
    sqldump.unlink()

    # TODO: assert supervisor.process_status(app.name) != 'RUNNING'
    if postgres.database_exists(app.name):
        require_postgres(app.name,
                         user_name=app.name, user_password=app.name,
                         pg_unaccent=app.pg_unaccent, pg_collkey=app.pg_collkey,
                         lsb_codename=lsb_codename, drop=True)

    sudo('gunzip -c %s | psql -d %s' % (target, app.name), user=app.name)
    sudo('vacuumdb -zf %s' % app.name, user='postgres')
    files.remove(str(target))


def alembic_upgrade_head(app, ctx):
    with python.virtualenv(str(app.venv_dir)), cd(str(app.src_dir)):
        sudo('%s -n production upgrade head' % (app.alembic), user=app.name)

    if confirm('Vacuum database?', default=False):
        flag = '-f ' if confirm('VACUUM FULL?', default=False) else ''
        sudo('vacuumdb %s-z -d %s' % (flag, app.name), user='postgres')
