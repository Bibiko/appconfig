import os

from fabric.api import cd, run, sudo
from fabric.contrib import files, console

from pyappconfig.tasks import *

LATEST_DUMP = 'https://cdstar.shh.mpg.de/bitstreams/EAEA0-54DF-D3B3-7041-0/glottolog.sql.gz'


init()


@task_app_from_environment
def load_sqldump(app, url=LATEST_DUMP):
    _, _, gzfile = url.rpartition('/')
    filename, _ = os.path.splitext(gzfile)
    with cd('/tmp'):
        run('wget %s' % url)
        run('gunzip %s' % gzfile)
        if console.confirm('Overwrite the database with %s?' % filename, default=False):
            sudo('psql -f %s %s' %(filename, app.name), user=app.name)


@task_app_from_environment
def enable_vbox(app):
    files.comment(app.nginx_default_site, 'server_name localhost;', use_sudo=True)
    set_localhost = "'s/server_name glottolog.org;/server_name localhost;/'"
    sudo('sed -i %s %s' % (set_localhost, app.nginx_site))
    sudo('service nginx restart')
