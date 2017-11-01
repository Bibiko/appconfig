# tasks.py - top-level fabric tasks: from pyappconfig.tasks import *

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

from ._compat import pathlib, string_types, input, iteritems

from fabric.api import env, task, execute, settings, shell_env, sudo, run, cd, local
from fabric.contrib.console import confirm
from fabric.contrib.files import exists
from fabtools import require, service, postgres
from fabtools.files import upload_template
from fabtools.python import virtualenv
from pytz import timezone, utc

from . import PKG_DIR, APPS, varnish, tools

__all__ = [
    'init',
    'task_app_from_environment',
    'pipfreeze',
    'bootstrap', 'deploy', 'uninstall',
    'start', 'stop', 'maintenance',
    'cache', 'uncache',
    'create_downloads', 'copy_downloads', 'copy_rdfdump',
    'run_script',
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
                # This allows overriding the configured hosts by explicitly passing a host for
                # the task using fab's -H option.
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


@task
def bootstrap():
    require.deb.packages(['vim', 'tree', 'open-vm-tools'])


@task_app_from_environment
def stop(app):
    """stop app by changing the supervisord config"""
    execute(supervisor, app, 'pause')


@task_app_from_environment
def start(app):
    """start app by changing the supervisord config"""
    execute(supervisor, app, 'run')


def supervisor(app, command, template_variables=None):
    """
    .. seealso: http://serverfault.com/a/479754
    """
    # TODO: consider fabtools.supervisor
    template_variables = template_variables or get_template_variables(app)
    template_variables['PAUSE'] = {'pause': True, 'run': False}[command]
    upload_template_as_root(
        app.supervisor, 'supervisor.conf', template_variables, mode='644')
    if command == 'run':
        sudo('supervisorctl reread')
        sudo('supervisorctl update %s' % app.name)
        sudo('supervisorctl restart %s' % app.name)
    else:
        sudo('supervisorctl stop %s' % app.name)
        #sudo('supervisorctl reread %s' % app.name)
        #sudo('supervisorctl update %s' % app.name)
    time.sleep(1)


def get_template_variables(app, monitor_mode=False, with_blog=False):
    res = {
        'app': app, 'env': env, 'monitor_mode': monitor_mode,
        'auth': '',
        'bloghost': '', 'bloguser': '', 'blogpassword': '',
    }

    if with_blog:  # pragma: no cover
        for key, default in [
            ('bloghost', 'blog.%s' % app.domain),
            ('bloguser', app.name),
            ('blogpassword', ''),
        ]:
            res[key] = (os.environ.get(('%s_%s' % (app.name, key)).upper())
                        or get_input('Blog %s [%s]: ' % (key[4:], default))
                        or default)
        assert res['blogpassword']

    return res


@task_app_from_environment('production')
def cache(app):
    """"""
    execute(varnish.cache, app)


@task_app_from_environment('production')
def uncache(app):
    execute(varnish.uncache, app)


@task_app_from_environment
def maintenance(app, hours=2, template_variables=None):
    """create a maintenance page giving a date when we expect the service will be back

    :param hours: Number of hours we expect the downtime to last.
    """
    template_variables = template_variables or get_template_variables(app)
    ts = utc.localize(datetime.utcnow() + timedelta(hours=hours))
    ts = ts.astimezone(timezone('Europe/Berlin')).strftime('%Y-%m-%d %H:%M %Z%z')
    template_variables['timestamp'] = ts
    require.directory(str(app.www), use_sudo=True)
    upload_template_as_root(app.www / '503.html', '503.html', template_variables)


@task_app_from_environment
def deploy(app, with_blog=None, with_alembic=False, with_files=True):
    """deploy the app"""
    if with_blog is None:
        with_blog = app.with_blog

    if app.workers > 3 and env.environment == 'test':
        app.workers = 3

    lsb_release = run('lsb_release --all', warn_only=True)
    for codename in ['precise', 'trusty', 'xenial']:
        if codename in lsb_release:
            lsb_release = codename
            break
    else:
        if lsb_release != '{"status": "ok"}':
            # if this were the case, we'd be in a test!
            raise ValueError('unsupported platform: %r' % lsb_release)

    jre_deb = 'default-jre' if lsb_release == 'xenial' else 'openjdk-6-jre'
    python_deb = 'python-dev' if lsb_release == 'precise' else 'python3-dev'
    require.deb.packages(app.require_deb + [jre_deb, python_deb])

    require.users.user(app.name, shell='/bin/bash')
    require_bibutils(app.home)
    require.directory(str(app.logs), use_sudo=True)

    template_variables = get_template_variables(app,
        monitor_mode='true' if env.environment == 'production' else 'false',
        with_blog=with_blog)

    require_postgres(app.name,
        user_name=app.name, user_password=app.name,
        pg_unaccent=app.pg_unaccent, pg_collkey=app.pg_collkey,
        lsb_release=lsb_release)

    template_variables['clld_dir'] = require_venv(app.venv,
        venv_python='python2' if lsb_release == 'precise' else 'python3',
        require_packages=[app.app_pkg] + app.require_pip,
        assets_name=app.name)

    #
    # configure nginx:
    #
    with shell_env(SYSTEMD_PAGER=''):
        require.nginx.server()
    require.directory(str(app.nginx_location.parent), owner='root', group='root', use_sudo=True)

    restricted, auth = http_auth(app)
    if restricted:
        template_variables['auth'] = auth
    template_variables['admin_auth'] = auth

    # TODO: consider require.nginx.site
    if env.environment == 'test':
        upload_template_as_root(app.nginx_default_site, 'nginx-default.conf')
        template_variables['SITE'] = False
        upload_template_as_root(app.nginx_location, 'nginx-app.conf', template_variables)
    elif env.environment == 'production':
        template_variables['SITE'] = True
        upload_template_as_root(app.nginx_site, 'nginx-app.conf', template_variables)
        upload_template_as_root(app.logrotate, 'logrotate.conf', template_variables)

    maintenance.inner_func(app, hours=app.deploy_duration, template_variables=template_variables)
    service.reload('nginx')

    if not with_alembic and confirm('Recreate database?', default=False):
        db_name = get_input('from db [{0}]: '.format(app.name))
        local('pg_dump -x -O -f /tmp/{0}.sql {1}'.format(app.name, db_name or app.name))
        local('gzip -f /tmp/{0}.sql'.format(app.name))
        require.file(
            '/tmp/{0}.sql.gz'.format(app.name),
            source="/tmp/{0}.sql.gz".format(app.name))
        sudo('gunzip -f /tmp/{0}.sql.gz'.format(app.name))
        supervisor(app, 'pause', template_variables)

        if postgres.database_exists(app.name):
            require_postgres(app.name,
                user_name=app.name, user_password=app.name,
                pg_unaccent=app.pg_unaccent, pg_collkey=app.pg_collkey,
                lsb_release=lsb_release, drop=True)

        sudo('psql -f /tmp/{0}.sql -d {0}'.format(app.name), user=app.name)
    elif exists(app.src / 'alembic.ini') and confirm('Upgrade database?', default=False):
        # Note: stopping the app is not strictly necessary, because the alembic
        # revisions run in separate transactions!
        supervisor(app, 'pause', template_variables)
        with virtualenv(str(app.venv)), cd(str(app.src)):
            sudo('%s -n production upgrade head' % (app.venv_bin / 'alembic'), user=app.name)

        if confirm('Vacuum database?', default=False):
            flag = '-f ' if confirm('VACUUM FULL?', default=False) else ''
            sudo('vacuumdb %s-z -d %s' % (flag, app.name), user=postgres)

    template_variables['TEST'] = {'test': True, 'production': False}[env.environment]
    # We only set add a setting clld.files, if the corresponding directory exists;
    # otherwise the app would throw an error on startup.
    template_variables['files'] = False
    if exists(app.www / 'files'):
        template_variables['files'] = app.www / 'files'
    upload_template_as_root(app.config, 'config.ini', template_variables)

    supervisor(app, 'run', template_variables)

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
        require.file(target, source=source.as_posix(), use_sudo=True, mode='')

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
        sudo('psql -c "{0}" -d {1.name}'.format(sql, app), user='postgres')
    if pg_collkey:
        pg_version = '9.1' if lsb_release == 'precise' else '9.3'
        if not exists('/usr/lib/postgresql/%s/lib/collkey_icu.so' % pg_version):
            require.deb.packages(['postgresql-server-dev-%s' % pg_version, 'libicu-dev'])
            with cd('/tmp'):
                upload_template_as_root('Makefile', 'pg_collkey_Makefile', {'pg_version': pg_version})
                require.file('collkey_icu.c', source=str(PG_COLLKEY_DIR / 'collkey_icu.c'))
                sudo('make')
                sudo('make install')
        with cd('/tmp'):
            require.file('collkey_icu.sql', source=str(PG_COLLKEY_DIR / 'collkey_icu.sql'))
            sudo('psql -f collkey_icu.sql -d %s' % database_name, user='postgres')


def require_venv(directory, venv_python, require_packages, assets_name):
    directory = str(directory)
    require.directory(directory, use_sudo=True)
    with settings(sudo_prefix=env.sudo_prefix + ' -H'):  # set HOME for pip log/cache
        require.python.virtualenv(directory, venv_python=venv_python, use_sudo=True)
        with virtualenv(directory):
            require.python.packages(require_packages, use_sudo=True)
            sudo('webassets -m %s.assets build' % assets_name)
            res = sudo('python -c "import clld; print(clld.__file__)"')
            assert res.startswith('/usr/venvs') and '__init__.py' in res
            return '/'.join(res.split('/')[:-1])


def get_input(prompt):  # to facilitate mocking
    return input(prompt)


def upload_template_as_root(dest, template, context=None, mode=None, owner='root'):
    if isinstance(mode, string_types):
        mode = int(mode, 8)
    upload_template(
        template, str(dest), context, use_jinja=True,
        template_dir=TEMPLATE_DIR.as_posix(), use_sudo=True, backup=False,
        mode=mode, chown=True, user=owner)


def http_auth(app):
    pwds = {
        app.name: getpass(prompt='HTTP Basic Auth password for user %s: ' % app.name),
        'admin': ''}

    while not pwds['admin']:
        pwds['admin'] = getpass(prompt='HTTP Basic Auth password for user admin: ')

    for i, pair in enumerate([(n, p) for n, p in iteritems(pwds) if p]):
        opts = 'bd'
        if i == 0:
            opts += 'c'
        sudo('htpasswd -%s %s %s %s' % (opts, app.nginx_htpasswd, pair[0], pair[1]))

    return bool(pwds[app.name]), """\
        proxy_set_header Authorization $http_authorization;
        proxy_pass_header  Authorization;
        auth_basic "%s";
        auth_basic_user_file %s;""" % (app.name, app.nginx_htpasswd)


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


@task_app_from_environment
def uninstall(app):  # pragma: no cover
    """uninstall the app"""
    for file_ in [app.supervisor, app.nginx_location, app.nginx_site]:
        if exists(str(file_)):
            sudo('rm %s' % file_)
    service.reload('nginx')
    sudo('supervisorctl stop %s' % app.name)


@task_app_from_environment
def create_downloads(app):
    """create all configured downloads"""
    dl_dir = app.src / app.name / 'static' / 'download'
    require.directory(dl_dir, use_sudo=True, mode="777")
    # run the script to create the exports from the database as glottolog3 user
    run_script(app, 'create_downloads')
    require.directory(dl_dir, use_sudo=True, mode="755")


@task_app_from_environment
def copy_downloads(app, pattern='*'):
    """copy downloads for the app"""
    dl_dir = app.src / app.name / 'static' / 'download'
    require.directory(dl_dir, use_sudo=True, mode="777")
    local_dl_dir = pathlib.Path(import_module(app.name).__file__).parent / 'static' / 'download'
    for f in local_dl_dir.glob(pattern):
        target = dl_dir / f.name
        create_file_as_root(target, open(f.as_posix()).read())
        sudo('chown %s:%s %s' % (app.name, app.name, target))
    require.directory(dl_dir, use_sudo=True, mode="755")


def create_file_as_root(path, contents, owner='root', group='root', **kw):
    require.file(str(path), contents, use_sudo=True, owner=owner, group=group, **kw)


@task_app_from_environment
def copy_rdfdump(app):
    """copy rdfdump for the app"""
    execute(copy_downloads(app, pattern='*.n3.gz'))


@task_app_from_environment
def run_script(app, script_name, *args):  # pragma: no cover
    """"""
    with cd(str(app.home)):
        sudo(
            '%s %s %s#%s %s' % (
                app.venv_bin / 'python',
                app.src / app.name / 'scripts' / ('%s.py' % script_name),
                app.config.name,
                app.name,
                ' '.join('%s' % arg for arg in args),
            ),
            user=app.name)
