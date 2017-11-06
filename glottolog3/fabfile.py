from fabric.api import cd, sudo
from fabric.contrib import files, console
from fabtools import require

from appconfig.tasks import *

DUMP_URL = 'https://cdstar.shh.mpg.de/bitstreams/EAEA0-54DF-D3B3-7041-0/glottolog.sql.gz'
DUMP_MD5 = '2cd8f1d52c7ea27b17937e205cb978a4'

init()


@task_app_from_environment('production')
def load_sqldump(app, url=DUMP_URL, md5=DUMP_MD5):
    if console.confirm('Fill the database with %s?' % url, default=False):
        _, _, filename = url.rpartition('/')
        with cd('/tmp'):
            require.file(filename, url=url, md5=md5)
            sudo('gunzip -c %s | psql %s' % (filename, app.name), user=app.name)


@task_app_from_environment('production')
def enable_vbox(app):
    # TODO: adapt normal template for this
    files.comment(app.nginx_default_site, 'server_name localhost;', use_sudo=True)
    files.sed(app.nginx_site, 'server_name glottolog.org;', 'server_name localhost;', use_sudo=True)
    sudo('service nginx restart')
