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

import functools

from fabric.api import task, hosts, execute, env

from pyappconfig import config, _tasks, varnish, tools

APP = None

__all__ = [
    'init',
    'pipfreeze',
    'bootstrap', 'deploy', 'uninstall',
    'start', 'stop', 'maintenance',
    'cache', 'uncache',
    'create_downloads', 'copy_downloads', 'copy_rdfdump',
    'run_script',
]


def init(app_name=None):
    global APP
    if app_name is None:
        app_name = tools.caller_dirname()
    APP = config.APPS[app_name]


def task_host_from_environment(func):
    @functools.wraps(func)
    def wrapper(environment='production', *args, **kwargs):
        assert environment in ['production', 'test']
        if not env.hosts:
            # This allows overriding the configured hosts by explicitly passing a host for
            # the task using fab's -H option.
            env.hosts = [getattr(APP, environment)]
        env.environment = environment
        execute(func, APP, *args, **kwargs)
    return task(wrapper)


@task
def bootstrap():
    _tasks.bootstrap()  # pragma: no cover


@task_host_from_environment
def stop(app):
    """stop app by changing the supervisord config"""
    execute(_tasks.supervisor, app, 'pause')


@task_host_from_environment
def start(app):
    """start app by changing the supervisord config"""
    execute(_tasks.supervisor, app, 'run')


@task_host_from_environment
def cache(app):
    """"""
    execute(varnish.cache, app)


@task_host_from_environment
def uncache(app):
    execute(varnish.uncache, app)


@task_host_from_environment
def maintenance(app, hours=2):
    """create a maintenance page giving a date when we expect the service will be back

    :param hours: Number of hours we expect the downtime to last.
    """
    execute(_tasks.maintenance, app, hours=hours)


@task_host_from_environment
def deploy(app, with_blog=False, **kwargs):
    """deploy the app"""
    if not with_blog:
        with_blog = getattr(app, 'with_blog', False)
    execute(_tasks.deploy, app, env.environment, with_blog=with_blog, **kwargs)


@task_host_from_environment
def pipfreeze(app):
    """get installed versions"""
    execute(_tasks.pipfreeze, app)


@task_host_from_environment
def uninstall(app):
    """uninstall the app"""
    execute(_tasks.uninstall, app)


@task_host_from_environment
def create_downloads(app):
    """create all configured downloads"""
    execute(_tasks.create_downloads, app)


@task_host_from_environment
def copy_downloads(app):
    """copy downloads for the app"""
    execute(_tasks.copy_downloads, app)


@task_host_from_environment
def copy_rdfdump(app):
    """copy rdfdump for the app"""
    execute(_tasks.copy_rdfdump, app)


@task_host_from_environment
def run_script(app, script_name, *args):
    """"""
    execute(_tasks.run_script, app, script_name, *args)
