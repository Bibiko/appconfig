# deployment.py

import os
import json
import time
import platform
import tempfile
import functools
import random
import pathlib
import re

from fabric.api import env, settings, shell_env, prompt, sudo, run, cd, local
from fabric.contrib.files import exists, comment, sed
from fabric.contrib.console import confirm
from fabtools import (
    require, files, python, postgres, nginx, system, service, supervisor, user, deb)

from .. import PKG_DIR
from .. import helpers
from .. import cdstar
from .. import systemd
from . import letsencrypt

from . import task_app_from_environment

__all__ = ['deploy', 'start', 'stop', 'uninstall', 'sudo_upload_template']

PLATFORM = platform.system().lower()
VBOX_HOSTNAMES = {'vbox', 'xenial'}  # run on localhost
PG_COLLKEY_DIR = PKG_DIR / 'pg_collkey-v0.5'
TEMPLATE_DIR = PKG_DIR / 'templates'


def template_context(app, workers=3, with_blog=False):
    ctx = {
        'SITE': {'test': False, 'production': True}[env.environment],
        'SSL': env.host.endswith('clld.org'),
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


def sudo_upload_template(template,
                         dest,
                         context=None,
                         mode=None,
                         user_own=None,
                         **kwargs):
    """
    A wrapper around upload_template in fabtools. Used to upload template files.

    :param user_own: Set to user name that's supposed to own the file.
        If it is None, the uploading user's rights are used.
    :type user_own: str

    :return: None
    """
    if kwargs:
        context = (context or {}).copy()
        context.update(kwargs)
    files.upload_template(
        template,
        dest,
        context,
        use_jinja=True,
        template_dir=str(TEMPLATE_DIR),
        use_sudo=True,
        backup=False,
        mode=mode,
        chown=True,
        user=user_own)


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
    sudo_upload_template('supervisor.conf', dest=str(filepath), mode='644', PAUSE=pause, app=app)


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

    require.deb.packages(getattr(app, 'require_deb_%s' % lsb_codename) + app.require_deb)
    require.users.user(app.name, create_home=True, shell='/bin/bash')
    require.directory(str(app.www_dir), use_sudo=True)
    require.directory(str(app.www_dir / 'files'), use_sudo=True)
    require_logging(app.log_dir,
                    logrotate=app.logrotate,
                    access_log=app.access_log, error_log=app.error_log)

    workers = 3 if app.workers > 3 and env.environment == 'test' else app.workers
    with_blog = with_blog if with_blog is not None else app.with_blog
    ctx = template_context(app, workers=workers, with_blog=with_blog)

    if app.stack == 'soundcomparisons':  # pragma: no cover
        require.git.working_copy(
            'https://github.com/{0}/{1}.git'.format(app.github_org, app.github_repos),
            path=str(app.home_dir / app.name),
            use_sudo=True,
            user=app.name)
        require_bower(app, d=app.home_dir / app.name / 'site' / 'js')
        require_grunt(app, d=app.home_dir / app.name / 'site' / 'js')
        require_php(app)
        require_mysql(app)

        with shell_env(SYSTEMD_PAGER=''):
            require.nginx.server()

        sudo_upload_template('nginx-php-fpm-app.conf', str(app.nginx_site), app=app)
        nginx.enable(app.name)
        systemd.enable(app, pathlib.Path(os.getcwd()) / 'systemd')
        return

    #
    # Create a virtualenv for the app and install the app package in development mode, i.e. with
    # repository working copy in /usr/venvs/<APP>/src
    #
    require_venv(
        app.venv_dir,
        require_packages=[app.app_pkg] + app.require_pip,
        assets_name=app.name if app.stack == 'clld' else None)

    #
    # If some of the static assets are managed via bower, update them.
    #
    require_bower(app)
    require_grunt(app)

    require_nginx(ctx)

    if app.stack == 'clld':
        require_bibutils()

    require_postgres(app)

    require_config(app.config, app, ctx)

    # if gunicorn runs, make it gracefully reload the app by sending HUP
    # TODO: consider 'supervisorctl signal HUP $name' instead (xenial+)
    sudo('( [ -f {0} ] && kill -0 $(cat {0}) 2> /dev/null '
         '&& kill -HUP $(cat {0}) ) || echo no reload '.format(app.gunicorn_pid))

    if not with_alembic and confirm('Recreate database?', default=False):
        stop.execute_inner(app)
        upload_sqldump(app)
    elif exists(str(app.src_dir / 'alembic.ini')) and confirm('Upgrade database?', default=False):
        # Note: stopping the app is not strictly necessary, because
        #       the alembic revisions run in separate transactions!
        stop.execute_inner(app, maintenance_hours=app.deploy_duration)
        alembic_upgrade_head(app, ctx)

    start.execute_inner(app)

    time.sleep(5)
    res = run('curl http://localhost:%s/_ping' % app.port)
    assert json.loads(res)['status'] == 'ok'

    if env.environment == 'production' and app.public:
        res_https = run('curl https://%s/_ping' % (app.domain))
        assert json.loads(res_https)['status'] == 'ok'

    systemd.enable(app, pathlib.Path(os.getcwd()) / 'systemd')


def require_php(app):  # pragma: no cover
    require.deb.package('php-fpm')
    sed('/etc/php/7.0/fpm/php.ini',
        'variables_order = "GPCS"',
        'variables_order = "EGPCS"', use_sudo=True)
    sudo_upload_template(
        'php-fpm-www.conf',
        '/etc/php/7.0/fpm/pool.d/www{0}.conf'.format(app.name),
        app=app,
    )
    sudo('systemctl restart php7.0-fpm.service')


def require_mysql(app):  # pragma: no cover
    if not deb.is_installed('mariadb-server'):
        require.deb.packages(['mariadb-server', 'mariadb-client', 'php-mysql'])

    require.mysql.user(app.name, app.name)
    require.mysql.database(app.name, owner=app.name)

    if confirm('Recreate database?', default=False):
        upload_sqldump(app)


def require_bower(app, d=None):
    d = d or app.static_dir
    if exists(str(d / 'bower.json')):
        require.deb.packages(['npm', 'nodejs-legacy'])
        sudo('npm install -g bower@1.8.4')
        with cd(str(d)):
            sudo('bower --allow-root install')


def require_grunt(app, d=None):
    d = d or app.static_dir
    if exists(str(d / 'Gruntfile.js')):
        require.deb.packages(['npm', 'nodejs-legacy'])
        sudo('npm install -g grunt-cli@1.2.0')
        with cd(str(d)):
            sudo('npm install')
            sudo('grunt')


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


def require_postgres(app, drop=False):
    if drop:
        with cd('/var/lib/postgresql'):
            sudo('dropdb %s' % app.name, user='postgres')

    with shell_env(SYSTEMD_PAGER=''):
        require.postgres.server()
        require.postgres.user(app.name, password=app.name)
        require.postgres.database(app.name, owner=app.name)

    if app.pg_unaccent:
        sql = 'CREATE EXTENSION IF NOT EXISTS unaccent WITH SCHEMA public;'
        sudo('psql -c "%s" -d %s' % (sql, app.name), user='postgres')

    if app.pg_collkey:
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
            sudo('psql -f collkey_icu.sql -d %s' % app.name, user='postgres')


def require_config(filepath, app, ctx):
    # We only set add a setting clld.files, if the corresponding directory exists;
    # otherwise the app would throw an error on startup.
    files_dir = app.www_dir / 'files'
    files = files_dir if exists(str(files_dir)) else None
    sudo_upload_template('config.ini', dest=str(filepath), context=ctx, files=files)

    if app.stack == 'django' and confirm('Recreate secret key?', default=True):
        key_chars = "abcdefghijklmnopqrstuvwxyz0123456789!@#$%^&*(-_=+)"
        secret_key = "".join([random.choice(key_chars) for i in range(50)])
        require.file(
            str(filepath.parent / 'secret_key'), contents=secret_key, use_sudo=True, mode='644')


def require_venv(directory, require_packages=None, assets_name=None, requirements=None):
    require.directory(str(directory), use_sudo=True)

    with settings(sudo_prefix=env.sudo_prefix + ' -H'):  # set HOME for pip log/cache
        require.python.virtualenv(str(directory), venv_python='python3', use_sudo=True)

        with python.virtualenv(str(directory)):
            if require_packages:
                require.python.packages(require_packages, use_sudo=True)
            if requirements:
                require.python.requirements(requirements, use_sudo=True)
            if assets_name:
                sudo('webassets -m %s.assets build' % assets_name)


def require_logging(log_dir, logrotate, access_log, error_log):
    require.directory(str(log_dir), use_sudo=True)

    if env.environment == 'production':
        sudo_upload_template('logrotate.conf', dest=str(logrotate),
                             access_log=access_log, error_log=error_log)


def require_nginx(ctx):
    app = ctx['app']

    with shell_env(SYSTEMD_PAGER=''):
        require.nginx.server()

    auth, admin_auth = http_auth(app)

    if env.host.endswith('clld.org'):
        letsencrypt.require_certbot()
        letsencrypt.require_cert(env.host)
        if env.environment == 'production':
            letsencrypt.require_cert(ctx['app'])

    # TODO: consider require.nginx.site
    upload_app = functools.partial(
        sudo_upload_template,
        'nginx-app.conf',
        context=ctx,
        clld_dir=get_clld_dir(app.venv_dir) if app.stack == 'clld' else '',
        auth=auth,
        admin_auth=admin_auth)

    sudo_upload_template('nginx-default.conf', dest=str(app.nginx_default_site), host=env.host)
    if ctx['SITE']:
        upload_app(dest=str(app.nginx_site))
        nginx.enable(app.nginx_site.name)
        if ctx['VBOX_LOCALHOST']:
            comment(app.nginx_default_site, 'server_name localhost;', use_sudo=True)
    else:  # test environment
        require.directory(str(app.nginx_location.parent), use_sudo=True)
        upload_app(dest=str(app.nginx_location))


def get_clld_dir(venv_dir):
    # /usr/venvs/<app_name>/local/lib/python<version>/site-packages/clld/__init__.pyc
    with python.virtualenv(str(venv_dir)):
        stdout = sudo('python -c "import clld; print(clld.__file__)"')
    clld_path = pathlib.PurePosixPath(stdout.split()[-1])
    return clld_path.parent


def http_auth(app):
    pwds = {
        app.name: None,  # Require no HTTP authentication by default in production.
        'admin': 'admin'  # For the /admin path, require trivial HTTP auth by default.
    }
    if not (app.public and env.environment == 'production'):
        # Non-public or test sites:
        pwds[app.name] = helpers.getpwd(app.name)
    if app.with_admin:
        pwds['admin'] = helpers.getpwd('admin')

    require.directory(str(app.nginx_htpasswd.parent), use_sudo=True)
    pairs = [(u, p) for u, p in pwds.items() if p]
    for opts, pairs in [('-bdc', pairs[:1]), ('-bd', pairs[1:])]:
        for u, p in pairs:
            sudo('htpasswd %s %s %s %s' % (opts, app.nginx_htpasswd, u, p))

    auth = ('proxy_set_header Authorization $http_authorization;\n'
            'proxy_pass_header Authorization;\n'
            'auth_basic "%s";\n'
            'auth_basic_user_file %s;\n' % (app.name, app.nginx_htpasswd))
    return auth if pwds[app.name] else '', auth


def upload_sqldump(app):
    if app.dbdump:
        if re.match('http(s)?://', app.dbdump):
            fname = 'dump.sql.gz'
            url = app.dbdump
        else:
            latest = cdstar.get_latest_bitstream(app.dbdump)
            fname, url = latest.name, latest.url
        target = pathlib.PurePosixPath('/tmp') / fname
        run('curl -s -o {0} {1}'.format(target, url))
    else:
        db_name = prompt('Replace with dump of local database:', default=app.name)
        sqldump = pathlib.Path(tempfile.mktemp(suffix='.sql.gz', prefix='%s-' % db_name))
        target = pathlib.PurePosixPath('/tmp') / sqldump.name

        db_user = '-U postgres ' if PLATFORM == 'windows' else ''
        local('pg_dump %s--no-owner --no-acl -Z 9 -f %s %s' % (db_user, sqldump, db_name))

        require.file(str(target), source=str(sqldump))
        sqldump.unlink()

    if app.stack == 'soundcomparisons':
        sudo('echo "drop database {0};" | mysql'.format(app.name))
        require.mysql.database(app.name, owner=app.name)
        sudo('gunzip -c {0} | mysql -u {1} --password={1} -D {1}'.format(target, app.name), user=app.name)
    else:
        # TODO: assert supervisor.process_status(app.name) != 'RUNNING'
        if postgres.database_exists(app.name):
            require_postgres(app, drop=True)

        sudo('gunzip -c %s | psql -d %s' % (target, app.name), user=app.name)
        sudo('vacuumdb -zf %s' % app.name, user='postgres')
    files.remove(str(target))


def alembic_upgrade_head(app, ctx):
    with python.virtualenv(str(app.venv_dir)), cd(str(app.src_dir)):
        sudo('%s -n production upgrade head' % (app.alembic), user=app.name)

    if confirm('Vacuum database?', default=False):
        flag = '-f ' if confirm('VACUUM FULL?', default=False) else ''
        sudo('vacuumdb %s-z -d %s' % (flag, app.name), user='postgres')
