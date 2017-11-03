# tasks.py - top-level fabric tasks: from appconfig.tasks import *

"""
fabric tasks
------------

We use the following mechanism to provide common task implementations for all clld apps:
This module defines and exports tasks which take a first argument "environment".
The environment is used to determine the correct host to run the actual task on.
To connect tasks to a certain app, the app's fabfile needs to import this module
and run the init function, passing an app name defined in the global clld app config.
"""

from __future__ import unicode_literals

import os
import json
import time
import getpass
import platform
import tempfile
import importlib
import functools

from ._compat import pathlib, iteritems

from fabric.api import (
    env, task, execute, settings, shell_env, prompt, sudo, run, cd, local)
from fabric.contrib.files import exists
from fabric.contrib.console import confirm
from fabtools import require, files, python, postgres, service, supervisor, system

from . import PKG_DIR, REPOS_DIR, APPS, helpers, varnish

__all__ = [
    'init', 'task_app_from_environment',
    'deploy', 'start', 'stop', 'uninstall',
    'cache', 'uncache',
    'run_script', 'create_downloads', 'copy_downloads', 'copy_rdfdump',
    'pip_freeze',
]

PLATFORM = platform.system().lower()

BIBUTILS_DIR = PKG_DIR / 'bibutils'

PG_COLLKEY_DIR = PKG_DIR / 'pg_collkey-v0.5'

TEMPLATE_DIR = PKG_DIR / 'templates'

APP = None


env.use_ssh_config = True  # configure your username in .ssh/config


def init(app_name=None):
    global APP
    if app_name is None:
        app_name = helpers.caller_dirname()
    APP = APPS[app_name]


def task_app_from_environment(func_or_environment):
    if callable(func_or_environment):
        func, _environment = func_or_environment, None
    else:
        func, _environment = None, func_or_environment

    if func is not None:
        @functools.wraps(func)
        def wrapper(environment, *args, **kwargs):
            assert environment in ('production', 'test')
            if not env.hosts:
                # allow overriding the hosts by using fab's -H option
                env.hosts = [getattr(APP, environment)]
            env.environment = environment
            return execute(func, APP, *args, **kwargs)
        wrapper.execute_inner = func
        return task(wrapper)
    else:
        def decorator(_func):
            _wrapper = task_app_from_environment(_func).wrapped
            wrapper = functools.wraps(_wrapper)(functools.partial(_wrapper, _environment))
            wrapper.execute_inner = _wrapper.execute_inner
            return task(wrapper)
        return decorator


def template_context(app, workers=3, with_blog=False,):
    ctx = {
        'SITE': {'test': False, 'production': True}[env.environment],
        'TEST': {'production': False, 'test': True}[env.environment],
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
            ctx[key] = (os.environ.get(('%s_%s' % (app.name, key)).upper())
                        or prompt('Blog %s:' % key[4:], default=default))
        assert ctx['blogpassword']

    return ctx


def sudo_upload_template(template, dest, context=None, mode=None, **kwargs):
    if kwargs:
        if context is None:
            context = kwargs
        else:
            context = context.copy()
            context.update(kwargs)
    files.upload_template(template, dest, context, use_jinja=True,
        template_dir=str(TEMPLATE_DIR), use_sudo=True, backup=False,
        mode=mode, chown=True)


@task_app_from_environment
def deploy(app, with_blog=None, with_alembic=False):
    """deploy the app"""
    assert system.distrib_id() == 'Ubuntu'
    lsb_codename = system.distrib_codename()
    if lsb_codename not in ('precise', 'trusty', 'xenial'):
        raise ValueError('unsupported platform: %s' % lsb_codename)

    jre_deb = 'default-jre' if lsb_codename == 'xenial' else 'openjdk-6-jre'
    require.deb.packages(app.require_deb + [jre_deb])

    require.users.user(app.name, shell='/bin/bash')

    require_bibutils(app.home_dir)

    require_postgres(app.name,
        user_name=app.name, user_password=app.name,
        pg_unaccent=app.pg_unaccent, pg_collkey=app.pg_collkey,
        lsb_codename=lsb_codename)

    ctx = template_context(app,
        workers=3 if app.workers > 3 and env.environment == 'test' else app.workers,
        with_blog=with_blog if with_blog is not None else app.with_blog)

    require_config(app.config, app, ctx)

    clld_dir = require_venv(app.venv_dir,
        venv_python='python2' if lsb_codename == 'precise' else 'python3',
        require_packages=[app.app_pkg] + app.require_pip,
        assets_name=app.name)

    require_logging(app.log_dir,
        logrotate=app.logrotate, access_log=app.access_log, error_log=app.error_log)

    require_nginx(ctx,
        default_site=app.nginx_default_site, site=app.nginx_site, location=app.nginx_location,
        logrotate=app.logrotate, clld_dir=clld_dir,
        htpasswd_file=app.nginx_htpasswd, htpasswd_user=app.name)

    stop.execute_inner(app, maintenance_hours=app.deploy_duration)

    if not with_alembic and confirm('Recreate database?', default=False):
        upload_local_sqldump(app, ctx, lsb_codename)
    elif exists(str(app.src_dir / 'alembic.ini')) and confirm('Upgrade database?', default=False):
        alembic_upgrade_head(app, ctx)

    start.execute_inner(app)

    time.sleep(5)
    res = run('curl http://localhost:%s/_ping' % app.port)
    assert json.loads(res)['status'] == 'ok'


def require_bibutils(directory):  # pragma: no cover
    """
    tar -xzf bibutils_5.0_src.tgz -C {app.home_dir}
    cd {app.home_dir}/bibutils_5.0
    configure
    make
    sudo make install
    """
    # FIXME: update?, download/include in repo?
    if not exists('/usr/local/bin/bib2xml'):
        source = BIBUTILS_DIR / 'bibutils_5.0_src.tgz'
        target = '/tmp/%s' % source.name
        require.file(target, source=str(source), use_sudo=True, mode='')

        sudo('tar -xzf %s -C %s' % (target, directory))
        with cd(str(directory / 'bibutils_5.0')):
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
                sudo_upload_template('pg_collkey_Makefile', dest='Makefile', pg_version=pg_version)
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
        require.python.virtualenv(str(directory), venv_python=venv_python, use_sudo=True)

        with python.virtualenv(str(directory)):
            require.python.packages(require_packages, use_sudo=True)
            sudo('webassets -m %s.assets build' % assets_name)
            res = sudo('python -c "import clld; print(clld.__file__)"')

    assert res.startswith('/usr/venvs') and '__init__.py' in res
    return '/'.join(res.split('/')[:-1])


def require_logging(log_dir, logrotate, access_log, error_log):
    require.directory(str(log_dir), use_sudo=True)

    if env.environment == 'production':
        sudo_upload_template('logrotate.conf', dest=str(logrotate),
                             access_log=access_log, error_log=error_log)


def require_nginx(ctx, default_site, site, location, logrotate, clld_dir,
                  htpasswd_file, htpasswd_user):
    with shell_env(SYSTEMD_PAGER=''):
        require.nginx.server()

    auth, admin_auth = http_auth(htpasswd_file, username=htpasswd_user)

    # TODO: consider require.nginx.site
    if ctx['SITE']:
        conf_dest = site
    else:  # test environment
        sudo_upload_template('nginx-default.conf', dest=str(default_site))
        require.directory(str(location.parent), use_sudo=True)
        conf_dest = location
    sudo_upload_template('nginx-app.conf', dest=str(conf_dest), context=ctx,
                         clld_dir=clld_dir, auth=auth, admin_auth=admin_auth)


def http_auth(htpasswd_file, username):
    userpass = getpass.getpass(prompt='HTTP Basic Auth password for user %s: ' % username)
    pwds = {username: userpass, 'admin': ''}
    while not pwds['admin']:
        pwds['admin'] = getpass.getpass(prompt='HTTP Basic Auth password for user admin: ')

    require.directory(str(htpasswd_file.parent), use_sudo=True)
    pairs = [(u, p) for u, p in iteritems(pwds) if p]
    for opts, pairs in [('-bdc', pairs[:1]), ('-bd', pairs[1:])]:
        for u, p in pairs:
            sudo('htpasswd %s %s %s %s' % (opts, htpasswd_file, u, p))

    auth = ('proxy_set_header Authorization $http_authorization;\n'
        'proxy_pass_header Authorization;\n'
        'auth_basic "%s";\n'
        'auth_basic_user_file %s;' % (username, htpasswd_file))
    return auth if userpass else '', auth


def upload_local_sqldump(app, ctx, lsb_codename):
    db_name = prompt('Replace with dump of local database:', default=app.name)
    sqldump = pathlib.Path(tempfile.mktemp(suffix='.sql.gz', prefix='%s-' % db_name))
    target = pathlib.PurePosixPath('/tmp') / sqldump.name

    db_user = '-U postgres ' if PLATFORM == 'windows' else ''
    local('pg_dump %s--no-owner --no-acl -Z 9 -f %s %s' % (db_user, sqldump, db_name))

    require.file(str(target), source=sqldump)
    sqldump.unlink()

    stop.execute_inner(app)

    if postgres.database_exists(app.name):
        require_postgres(app.name,
            user_name=app.name, user_password=app.name,
            pg_unaccent=app.pg_unaccent, pg_collkey=app.pg_collkey,
            lsb_codename=lsb_codename, drop=True)

    sudo('gunzip -c %s | psql -d %s' % (target, app.name), user=app.name)
    files.remove(str(target))


def alembic_upgrade_head(app, ctx):
    # Note: stopping the app is not strictly necessary, because the alembic
    # revisions run in separate transactions!
    stop.execute_inner(app)

    with python.virtualenv(str(app.venv_dir)), cd(str(app.src_dir)):
        sudo('%s -n production upgrade head' % (app.alembic), user=app.name)

    if confirm('Vacuum database?', default=False):
        flag = '-f ' if confirm('VACUUM FULL?', default=False) else ''
        sudo('vacuumdb %s-z -d %s' % (flag, app.name), user='postgres')


def require_supervisor(filepath, app, pause=False):
    # TODO: consider require.supervisor.process
    sudo_upload_template('supervisor.conf', dest=str(filepath), mode='644',
                         name=app.name, gunicorn=app.gunicorn, user=app.name, group=app.name,
                         error_log=app.error_log, config=app.config, PAUSE=pause)


@task_app_from_environment
def start(app):
    """start app by changing the supervisord config"""
    require_supervisor(app.supervisor, app)
    supervisor.update_config()
    service.reload('nginx')


@task_app_from_environment
def stop(app, maintenance_hours=2):
    """pause app by changing the supervisord config

    create a maintenance page giving a date when we expect the service will be back
    :param maintenance_hours: Number of hours we expect the downtime to last.
    """
    if maintenance_hours is not None:
        require.directory(str(app.www_dir), use_sudo=True)  # FIXME
        sudo_upload_template('503.html', dest=str(app.www_dir / '503.html'), app_name=app.name,
                             timestamp=helpers.strfnow(add_hours=maintenance_hours))

    require_supervisor(app.supervisor, app, pause=True)
    supervisor.update_config()
    service.reload('nginx')


@task_app_from_environment
def uninstall(app):  # pragma: no cover
    """uninstall the app"""
    for path in (app.supervisor, app.nginx_location, app.nginx_site):
        if exists(str(path)):
            files.remove(str(path), use_sudo=True)

    supervisor.update_config()
    service.reload('nginx')


@task_app_from_environment('production')
def cache(app):
    """"""
    execute(varnish.cache, app)


@task_app_from_environment('production')
def uncache(app):
    execute(varnish.uncache, app)


@task_app_from_environment
def run_script(app, script_name, *args):  # pragma: no cover
    """"""
    cmd = '%s/python %s/scripts/%s.py %s#%s %s' % (
        app.venv_bin,
        app.src_dir / app.name, script_name,
        app.config.name, app.name,
        ' '.join('%s' % a for a in args))
    with cd(str(app.home_dir)):
        sudo(cmd, user=app.name)


@task_app_from_environment
def create_downloads(app):
    """create all configured downloads"""
    require.directory(str(app.download_dir), use_sudo=True, mode='777')

    # run the script to create the exports from the database as glottolog3 user
    run_script(app, 'create_downloads')

    require.directory(str(app.download_dir), use_sudo=True, mode='755')


@task_app_from_environment
def copy_downloads(app, pattern='*'):
    """copy downloads for the app"""
    require.directory(str(app.download_dir), use_sudo=True, mode='777')

    local_app = importlib.import_module(app.name)  # FIXME
    local_dl_dir = pathlib.Path(local_app.__file__).parent / 'static' / 'download'
    for f in local_dl_dir.glob(pattern):
        require.file(str(app.download_dir / f.name), source=f, use_sudo=True,
                     owner=app.name, group=app.name)

    require.directory(str(app.download_dir), use_sudo=True, mode='755')


@task_app_from_environment
def copy_rdfdump(app):
    """copy rdfdump for the app"""
    copy_downloads.execute_inner(app, pattern='*.n3.gz')


@task_app_from_environment('production')
def pip_freeze(app):
    """write installed versions to <app_name>/requirements.txt"""
    with python.virtualenv(str(app.venv_dir)):
        stdout = run('pip freeze', combine_stderr=False)

    def iterlines(lines):
        warning = ('\x1b[33m', 'You should ')
        app_git = '%s.git' % app.name.lower()
        ignore = {'babel', 'fabric', 'fabtools', 'newrelic', 'paramiko', 'pycrypto', 'pyx'}
        for line in lines:
            if line.startswith(warning):
                continue  # https://github.com/pypa/pip/issues/2470
            elif app_git in line or line.partition('==')[0].lower() in ignore:
                continue
            elif 'clld.git' in line:
                line = 'clld'
            elif 'clldmpg.git' in line:
                line = 'clldmpg'
            yield line + '\n'

    target = REPOS_DIR / app.name / 'requirements.txt'
    with target.open('w', encoding='ascii') as fp:
        fp.writelines(iterlines(stdout.splitlines()))
