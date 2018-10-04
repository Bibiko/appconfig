# other.py

import tempfile
import os
import subprocess
import pathlib

from fabric.api import sudo, run, cd, local, get
from fabric.contrib.console import confirm
from fabtools import require, python

from .. import APPS_DIR
from .. import cdstar

from . import task_app_from_environment

__all__ = [
    'run_script', 'create_downloads',
    'copy_downloads', 'copy_rdfdump',
    'pip_freeze', 'load_db', 'dump_db',
    'upload_db_to_cdstar',
    'list_dumps', 'remove_dumps',
]


def dump_db(app, dbname=None):
    remote_dump = '/tmp/db.sql'
    if app.stack == 'soundcomparisons':
        dbname = dbname or app.name
        dump_cmd = 'mysqldump -h localhost -u {0} -p --routines --single-transaction {1} >> {2}'.format(
            app.name, dbname, remote_dump)
    else:
        assert dbname is None
        dump_cmd = 'pg_dump --no-owner --no-acl -f %s %s' % (remote_dump, app.name)
    sudo(dump_cmd, user=app.name)
    sudo('gzip -f {0}'.format(remote_dump), user=app.name)
    remote_dump += '.gz'
    local_dump = pathlib.Path(tempfile.mktemp(suffix='.sql.gz', prefix='%s-' % app.name))
    get(remote_path=remote_dump, local_path=str(local_dump))
    sudo('rm %s' % remote_dump, user=app.name)
    return local_dump


def upload_db_to_cdstar(app, dbname=None):
    sql_dump = dump_db(app, dbname=dbname)
    cdstar.add_bitstream(app.dbdump, sql_dump)
    sql_dump.unlink()


@task_app_from_environment
def list_dumps(app):
    if app.dbdump:
        for i, bs in enumerate(cdstar.get_bitstreams(app.dbdump), start=1):
            print('{0}\t{1}\t{2}\t{3}\t{4}'.format(i, bs.datetime.isoformat(), bs.name, bs.size_h, bs.size))


@task_app_from_environment
def remove_dumps(app, keep=10):
    if app.dbdump:
        i = 0
        for bs in cdstar.get_bitstreams(app.dbdump):
            if i > int(keep) and bs.name.startwith('db_dump_'):
                print('deleting dump {0}'.format(bs.name))
                bs.bitstream.delete()
                i += 1


@task_app_from_environment
def load_db(app, local_name=None):
    """Dump remote app DB and try loading the dump into a local database."""
    local_name = local_name or app.name
    local_dump = dump_db(app)
    assert local_dump.exists()
    try:
        local_dbs = [
            l.split(b'|')[0] for l in subprocess.check_output(['psql', '-lAt']).splitlines()]
        if local_name in local_dbs:
            if confirm('Drop existing DB {0}?'.format(local_name), default=False):
                local('dropdb {0}'.format(local_name))
            else:
                print('SQL dump downloaded to {0}'.format(local_dump))
                return
    except FileNotFoundError:  # No PostgreSQL available?
        print('SQL dump downloaded to {0}'.format(local_dump))
        return

    local('createdb {0}'.format(local_name))
    res = local('gunzip -c %s | psql -1 -d %s' % (local_dump, local_name), capture=True)
    if res.return_code != 0:
        print(res.stdout)
        print('SQL dump downloaded to {0}'.format(local_dump))
    else:
        os.remove(str(local_dump))


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
    run_script.execute_inner(app, 'create_downloads')

    require.directory(str(app.download_dir), use_sudo=True, mode='755')


@task_app_from_environment
def copy_downloads(app, source_dir, pattern='*'):
    """copy downloads for the app"""
    require.directory(str(app.download_dir), use_sudo=True, mode='777')

    source_dir = pathlib.Path(source_dir)
    for f in source_dir.glob(pattern):
        require.file(str(app.download_dir / f.name), source=f,
                     use_sudo=True, owner=app.name, group=app.name)

    require.directory(str(app.download_dir), use_sudo=True, mode='755')


@task_app_from_environment
def copy_rdfdump(app, source_dir):
    """copy rdfdump for the app"""
    copy_downloads.execute_inner(app, source_dir, pattern='*.n3.gz')


@task_app_from_environment('production')
def pip_freeze(app):
    """write installed versions to <app_name>/requirements.txt"""
    with python.virtualenv(str(app.venv_dir)):
        stdout = run('pip freeze', combine_stderr=False)

    def iterlines(lines):
        warning = ('\x1b[33m', 'You should ')
        warning_within = ('SNIMissingWarning', 'InsecurePlatformWarning')
        app_git = '%s.git' % app.name.lower()
        ignore = {'babel', 'fabric', 'fabtools', 'newrelic', 'paramiko', 'pycrypto', 'pyx'}
        for line in lines:
            if line.startswith(warning) or any(w in line for w in warning_within):
                continue  # https://github.com/pypa/pip/issues/2470
            elif app_git in line or line.partition('==')[0].lower() in ignore:
                continue
            elif 'clld.git' in line:
                line = 'clld'
            elif 'clldmpg.git' in line:
                line = 'clldmpg'
            yield line + '\n'

    target = APPS_DIR / app.name / 'requirements.txt'
    with target.open('w', encoding='ascii') as fp:
        fp.writelines(iterlines(stdout.splitlines()))
