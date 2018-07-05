from fabric.api import sudo
from appconfig.tasks import *

init()


@task_app_from_environment
def shutdown(app):
    sudo('systemctl stop php7.0-fpm.service')
    upload_db_to_cdstar(app, dbname='v4')


@task_app_from_environment
def backup_to_cdstar(app):
    upload_db_to_cdstar(app, dbname='v4')
