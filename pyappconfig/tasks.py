# tasks.py - top-level fabric tasks: from pyappconfig.tasks import *

"""
fabric tasks
------------

We use the following mechanism to provide common task implementations for all clld apps:
This module defines and exports tasks which are run on localhost and take a first argument
"environment". The environment is used to determine the correct host to run the actual
task on. To connect tasks to a certain app, the app's fabfile needs to import this module
and run the init function, passing an app name defined in the global clld app config.
"""

from __future__ import unicode_literals

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


def _assign_host(environment):
    assert environment in ['production', 'test']
    if not env.hosts:
        # This allows overriding the configured hosts by explicitly passing a host for
        # the task using fab's -H option.
        env.hosts = [getattr(APP, environment)]


@task
def bootstrap():
    _tasks.bootstrap()  # pragma: no cover


@hosts('localhost')
@task
def stop(environment):
    """stop app by changing the supervisord config
    """
    _assign_host(environment)
    execute(_tasks.supervisor, APP, 'pause')


@hosts('localhost')
@task
def start(environment):
    """start app by changing the supervisord config
    """
    _assign_host(environment)
    execute(_tasks.supervisor, APP, 'run')


@hosts('localhost')
@task
def cache():
    """
    """
    _assign_host('production')
    execute(varnish.cache, APP)


@hosts('localhost')
@task
def uncache():
    """
    """
    _assign_host('production')
    execute(varnish.uncache, APP)


@hosts('localhost')
@task
def maintenance(environment, hours=2):
    """create a maintenance page giving a date when we expect the service will be back

    :param hours: Number of hours we expect the downtime to last.
    """
    _assign_host(environment)
    execute(_tasks.maintenance, APP, hours=hours)


@hosts('localhost')
@task
def deploy(environment, with_blog=False):
    """deploy the app
    """
    _assign_host(environment)
    if not with_blog:
        with_blog = getattr(APP, 'with_blog', False)
    execute(_tasks.deploy, APP, environment, with_blog=with_blog)


@hosts('localhost')
@task
def pipfreeze(environment):
    """get installed versions
    """
    _assign_host(environment)
    execute(_tasks.pipfreeze, APP, environment)


@hosts('localhost')
@task
def uninstall(environment):
    """uninstall the app
    """
    _assign_host(environment)
    execute(_tasks.uninstall, APP)


@hosts('localhost')
@task
def create_downloads(environment):
    """create all configured downloads
    """
    _assign_host(environment)
    execute(_tasks.create_downloads, APP)


@hosts('localhost')
@task
def copy_downloads(environment):
    """copy downloads for the app
    """
    _assign_host(environment)
    execute(_tasks.copy_downloads, APP)


@hosts('localhost')
@task
def copy_rdfdump(environment):
    """copy rdfdump for the app
    """
    _assign_host(environment)
    execute(_tasks.copy_rdfdump, APP)


@hosts('localhost')
@task
def run_script(environment, script_name, *args):
    """
    """
    _assign_host(environment)
    execute(_tasks.run_script, APP, script_name, *args)
