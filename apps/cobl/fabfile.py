import pathlib

from appconfig.tasks import *
from appconfig import cdstar
from appconfig.systemd import enable


init()


@task_app_from_environment
def shutdown(app):
    stop.execute_inner(app, maintenance_hours=None)
    sql_dump = dump_db(app)
    cdstar.add_bitstream(app.dbdump, sql_dump)
    sql_dump.unlink()


@task_app_from_environment
def systemd(app):
    enable(app, pathlib.Path(__file__).parent / 'systemd')
