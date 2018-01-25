from fabric.api import cd, sudo, local
from fabric.contrib import console
from fabtools import require

from appconfig.tasks import *

DUMP_URL = 'https://cdstar.shh.mpg.de/bitstreams/EAEA0-F088-DE0E-0712-0/glottolog.sql.gz'
DUMP_MD5 = 'df0e3dd9963b9a5c983a84873e4198c5'

init()


@task_app_from_environment('production')
def load_sqldump(app, url=DUMP_URL, md5=DUMP_MD5):
    if console.confirm('Fill the database with %s?' % url, default=False):
        _, _, filename = url.rpartition('/')
        with cd('/tmp'):
            require.file(filename, url=url, md5=md5)
            sudo('gunzip -c %s | psql %s' % (filename, app.name), user=app.name)


@task_app_from_environment('production')
def copy_archive(app):
    raise NotImplementedError
    arc = 'archive.tgz'
    local('tar -czf {0} archive'.format(arc))
    with cd('/tmp'):
        require.file(arc, source=arc)
        sudo('tar -xzf {0}'.format(arc))
        sudo('rm {0}/*'.format(app.files))
        sudo('mv archive/* {0}'.format(app.files))
        sudo('rm {0}'.format(arc))
    local('rm {0}'.format(arc))


@task_app_from_environment('production')
def fetch_downloads(app):
    sudo('{0}/python {1}/src/glottolog3/glottolog3/scripts/fetch_downloads.py'.format(
        app.venv_bin, app.venv_dir))

