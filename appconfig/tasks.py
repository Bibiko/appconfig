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
import time
import json
import functools
from getpass import getpass
from datetime import datetime, timedelta
from importlib import import_module

from ._compat import pathlib, iteritems

from fabric.api import (
    env, task, execute, settings, shell_env, prompt, sudo, run, cd, local)
from fabric.contrib.console import confirm
from fabric.contrib.files import exists
from fabtools import require, service, postgres
from fabtools.files import upload_template
from fabtools.python import virtualenv
from pytz import timezone, utc

from . import PKG_DIR, APPS, varnish, tools

__all__ = [
    'init', 'task_app_from_environment',
    'deploy', 'start', 'stop', 'maintenance', 'uninstall',
    'cache', 'uncache',
    'run_script', 'create_downloads', 'copy_downloads', 'copy_rdfdump',
    'pipfreeze',
]

BIBUTILS_DIR = PKG_DIR / 'bibutils'

PG_COLLKEY_DIR = PKG_DIR / 'pg_collkey-v0.5'

TEMPLATE_DIR = PKG_DIR / 'templates'

APP = None


env.use_ssh_config = True  # configure your username in .ssh/config


def init(app_name=None):
    global APP
    if app_name is None:
        app_name = tools.caller_dirname()
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
        wrapper.inner_func = func
        return task(wrapper)
    else:
        def decorator(_func):
            _wrapper = task_app_from_environment(_func).wrapped
            wrapper = functools.wraps(_wrapper)(functools.partial(_wrapper, _environment))
            wrapper.inner_func = _wrapper.inner_func
            return task(wrapper)
        return decorator


def template_context(app, workers=3, with_blog=False,):
    ctx = {
        'app': app, 'env': env, 'workers': workers,
        'auth': '',
        'bloghost': '', 'bloguser': '', 'blogpassword': '',
        'TEST': {'production': False, 'test': True}[env.environment],
        'SITE': {'test': False, 'production': True}[env.environment],
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


def sudo_upload_template(template, dest, context=None, mode=None, user='root', **kwargs):
    if kwargs:
        context = context.copy()
        context.update(kwargs)
    upload_template(template, dest, context, use_jinja=True,
        template_dir=str(TEMPLATE_DIR), use_sudo=True, backup=False,
        mode=mode, chown=True, user=user)


@task_app_from_environment
def deploy(app, with_blog=None, with_alembic=False, with_files=True):
    """deploy the app"""
    lsb_release = run('lsb_release --all', warn_only=True)
    for codename in ['precise', 'trusty', 'xenial']:
        if codename in lsb_release:
            lsb_release = codename
            break
    else:
        if lsb_release != '{"status": "ok"}':  # not in a test
            raise ValueError('unsupported platform: %r' % lsb_release)

    jre_deb = 'default-jre' if lsb_release == 'xenial' else 'openjdk-6-jre'
    python_deb = 'python-dev' if lsb_release == 'precise' else 'python3-dev'
    require.deb.packages(app.require_deb + [jre_deb, python_deb])

    require.users.user(app.name, shell='/bin/bash')

    require.directory(str(app.logs), use_sudo=True)

    require_bibutils(app.home)

    require_postgres(app.name,
        user_name=app.name, user_password=app.name,
        pg_unaccent=app.pg_unaccent, pg_collkey=app.pg_collkey,
        lsb_release=lsb_release)

    ctx = template_context(app,
        workers=3 if app.workers > 3 and env.environment == 'test' else app.workers,
        with_blog=with_blog if with_blog is not None else app.with_blog)

    clld_dir = require_venv(app.venv,
        venv_python='python2' if lsb_release == 'precise' else 'python3',
        require_packages=[app.app_pkg] + app.require_pip,
        assets_name=app.name)

    require_nginx(app, ctx,
        default_site=app.nginx_default_site, site=app.nginx_site, location=app.nginx_location,
        logrotate=app.logrotate, clld_dir=clld_dir, deploy_duration=app.deploy_duration)

    if not with_alembic and confirm('Recreate database?', default=False):
        db_name = prompt('from db:', default=app.name)
        archive = '/tmp/%s.sql.gz' % db_name
        local('pg_dump --no-owner --no-acl -Z 9 -f %s %s' % (archive, db_name))
        require.file(archive, source=archive)

        supervisor(app, 'pause', context=ctx)
        if postgres.database_exists(app.name):
            require_postgres(app.name,
                user_name=app.name, user_password=app.name,
                pg_unaccent=app.pg_unaccent, pg_collkey=app.pg_collkey,
                lsb_release=lsb_release, drop=True)
        sudo('gunzip -f %s' % archive)
        dump, _ = os.path.splitext(archive)
        sudo('psql -f %s -d %s' % (dump, app.name), user=app.name)
    elif exists(app.src / 'alembic.ini') and confirm('Upgrade database?', default=False):
        # Note: stopping the app is not strictly necessary, because the alembic
        # revisions run in separate transactions!
        supervisor(app, 'pause', context=ctx)
        with virtualenv(str(app.venv)), cd(str(app.src)):
            sudo('%s -n production upgrade head' % (app.venv_bin / 'alembic'), user=app.name)

        if confirm('Vacuum database?', default=False):
            flag = '-f ' if confirm('VACUUM FULL?', default=False) else ''
            sudo('vacuumdb %s-z -d %s' % (flag, app.name), user=postgres)

    # We only set add a setting clld.files, if the corresponding directory exists;
    # otherwise the app would throw an error on startup.
    sudo_upload_template('config.ini', dest=str(app.config), context=ctx,
                         files=app.www / 'files' if exists(app.www / 'files') else False)

    supervisor(app, 'run', context=ctx)

    time.sleep(5)
    res = run('wget -q -O - http://localhost:%s/_ping' % app.port)
    assert json.loads(res)['status'] == 'ok'


def require_bibutils(directory):  # pragma: no cover
    """
    tar -xzvf bibutils_5.0_src.tgz -C {app.home}
    cd {app.home}/bibutils_5.0
    configure
    make
    sudo make install
    """
    if not exists('/usr/local/bin/bib2xml'):
        source = BIBUTILS_DIR / 'bibutils_5.0_src.tgz'
        target = '/tmp/%s' % source.name
        require.file(target, source=str(source), use_sudo=True, mode='')

        sudo('tar -xzvf %s -C %s' % (target, directory))
        with cd(str(directory / 'bibutils_5.0')):
            run('./configure')
            run('make')
            sudo('make install')


def require_postgres(database_name, user_name, user_password, pg_unaccent, pg_collkey,
                     lsb_release, drop=False):
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
        pg_version = os.path.basename(pg_dir)
        if not exists('/usr/lib/postgresql/%s/lib/collkey_icu.so' % pg_version):
            require.deb.packages(['postgresql-server-dev-%s' % pg_version, 'libicu-dev'])
            with cd('/tmp'):
                context = {'pg_version': pg_version}
                sudo_upload_template('pg_collkey_Makefile', dest='Makefile', context=context)
                require.file('collkey_icu.c', source=str(PG_COLLKEY_DIR / 'collkey_icu.c'))
                run('make')
                sudo('make install')
        with cd('/tmp'):
            require.file('collkey_icu.sql', source=str(PG_COLLKEY_DIR / 'collkey_icu.sql'))
            sudo('psql -f collkey_icu.sql -d %s' % database_name, user='postgres')


def require_venv(directory, venv_python, require_packages, assets_name):
    require.directory(str(directory), use_sudo=True)

    with settings(sudo_prefix=env.sudo_prefix + ' -H'):  # set HOME for pip log/cache
        require.python.virtualenv(str(directory), venv_python=venv_python, use_sudo=True)

        with virtualenv(str(directory)):
            require.python.packages(require_packages, use_sudo=True)
            sudo('webassets -m %s.assets build' % assets_name)
            res = sudo('python -c "import clld; print(clld.__file__)"')

    assert res.startswith('/usr/venvs') and '__init__.py' in res
    return '/'.join(res.split('/')[:-1])


def require_nginx(app, ctx, default_site, site, location, logrotate, clld_dir, deploy_duration):
    with shell_env(SYSTEMD_PAGER=''):
        require.nginx.server()
    require.directory(str(location.parent), owner='root', group='root', use_sudo=True)

    auth, admin_auth = http_auth(username=app.name, htpasswd_file=app.nginx_htpasswd)

    # TODO: consider require.nginx.site
    if ctx['SITE']:
        conf_dest = site
        sudo_upload_template('logrotate.conf', dest=str(logrotate), context=ctx)
    else:  # test environment
        conf_dest = location
        sudo_upload_template('nginx-default.conf', dest=str(default_site))
    sudo_upload_template('nginx-app.conf', dest=str(conf_dest), context=ctx,
                         clld_dir=clld_dir, auth=auth, admin_auth=admin_auth)

    maintenance.inner_func(app, hours=deploy_duration, ctx=ctx)
    service.reload('nginx')


def http_auth(username, htpasswd_file):
    userpass = getpass(prompt='HTTP Basic Auth password for user %s: ' % username)
    pwds = {username: userpass, 'admin': ''}
    while not pwds['admin']:
        pwds['admin'] = getpass(prompt='HTTP Basic Auth password for user admin: ')

    pairs = [(u, p) for u, p in iteritems(pwds) if p]
    for opts, pairs in [('-bdc', pairs[:1]), ('-bd', pairs[1:])]:
        for u, p in pairs:
            sudo('htpasswd %s %s %s %s' % (opts, htpasswd_file, u, p))

    auth = ('proxy_set_header Authorization $http_authorization;\n'
        'proxy_pass_header Authorization;\n'
        'auth_basic "%s";\n'
        'auth_basic_user_file %s;' % (username, htpasswd_file))
    return auth if userpass else '', auth


@task_app_from_environment
def start(app):
    """start app by changing the supervisord config"""
    execute(supervisor, app, 'run')


@task_app_from_environment
def stop(app):
    """stop app by changing the supervisord config"""
    execute(supervisor, app, 'pause')


def supervisor(app, command, context=None):
    """
    .. seealso: http://serverfault.com/a/479754
    """
    # TODO: consider fabtools.supervisor
    ctx = context if context is not None else template_context(app)

    sudo_upload_template('supervisor.conf', dest=str(app.supervisor), context=ctx, mode='644',
                         PAUSE={'pause': True, 'run': False}[command])

    if command == 'run':
        sudo('supervisorctl reread')
        sudo('supervisorctl update %s' % app.name)
        sudo('supervisorctl restart %s' % app.name)
    else:
        sudo('supervisorctl stop %s' % app.name)
        #sudo('supervisorctl reread %s' % app.name)
        #sudo('supervisorctl update %s' % app.name)
    time.sleep(1)


@task_app_from_environment
def maintenance(app, hours=2, ctx=None):
    """create a maintenance page giving a date when we expect the service will be back

    :param hours: Number of hours we expect the downtime to last.
    """
    if ctx is None:
        ctx = template_context(app)

    ts = utc.localize(datetime.utcnow() + timedelta(hours=hours))
    ts = ts.astimezone(timezone('Europe/Berlin')).strftime('%Y-%m-%d %H:%M %Z%z')
    require.directory(str(app.www), use_sudo=True)
    sudo_upload_template('503.html', dest=str(app.www / '503.html'), context=ctx, timestamp=ts)


@task_app_from_environment
def uninstall(app):  # pragma: no cover
    """uninstall the app"""
    for path in [app.supervisor, app.nginx_location, app.nginx_site]:
        if exists(str(path)):
            sudo('rm %s' % path)

    service.reload('nginx')
    sudo('supervisorctl stop %s' % app.name)


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
        app.src / app.name, script_name,
        app.config.name, app.name,
        ' '.join('%s' % a for a in args))
    with cd(str(app.home)):
        sudo(cmd, user=app.name)


@task_app_from_environment
def create_downloads(app):
    """create all configured downloads"""
    require.directory(str(app.download), use_sudo=True, mode='777')

    # run the script to create the exports from the database as glottolog3 user
    run_script(app, 'create_downloads')
    require.directory(str(app.download), use_sudo=True, mode='755')


@task_app_from_environment
def copy_downloads(app, pattern='*'):
    """copy downloads for the app"""
    require.directory(str(app.download), use_sudo=True, mode='777')

    app_dir = pathlib.Path(import_module(app.name).__file__).parent  # FIXME
    local_dl_dir = app_dir / 'static' / 'download'
    for f in local_dl_dir.glob(pattern):
        require.file(str(app.download / f.name), source=f, use_sudo=True, owner='root', group='root')
        sudo('chown %s:%s %s' % (app.name, app.name, target))
    require.directory(str(app.download), use_sudo=True, mode='755')


@task_app_from_environment
def copy_rdfdump(app):
    """copy rdfdump for the app"""
    execute(copy_downloads, app, pattern='*.n3.gz')


@task_app_from_environment
def pipfreeze(app):
    """get installed versions"""
    with virtualenv(app.venv):
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

    with open('requirements.txt', 'w') as fp:
        fp.writelines(iterlines(stdout.splitlines()))
