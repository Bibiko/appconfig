from appconfig.tasks import *


init()


@task_app_from_environment
def shutdown(app):
    stop.execute_inner(app, maintenance_hours=None)
    upload_db_to_cdstar(app)


@task_app_from_environment
def backup_to_cdstar(app):
    upload_db_to_cdstar(app)
