# coding: utf8
from __future__ import unicode_literals, print_function, division

from fabric.api import env, sudo, execute, hide

from appconfig import APPS

env.use_ssh_config = True


def run_sql_(sql):
    apps = [a for a in APPS.values() if a.stack == 'clld' and a.production == env.host]
    if apps:
        with hide('output'):
            dbs = [
                l.split('|')[0] for l in sudo('psql -lAt', user='postgres').splitlines()]
        for app in apps:
            if app.name in dbs:
                print(sudo('psql -d {0} -c "{1}"'.format(app.name, sql), user='postgres'))


def run_sql(sql):
    execute(run_sql_, sql, hosts=set(app.production for app in APPS.values()))
