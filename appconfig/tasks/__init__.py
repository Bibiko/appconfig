# tasks - top-level fabric tasks: from appconfig.tasks import *

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

import fabric.api

from .. import _compat, helpers

__all__ = ['init', 'task_app_from_environment']

APP = None


fabric.api.env.use_ssh_config = True  # configure your username in .ssh/config


def init(app_name=None):
    global APP
    from .. import APPS
    if app_name is None:  # pragma: no cover
        app_name = helpers.caller_dirname()
    APP = APPS[app_name]


def task_app_from_environment(func_or_environment):
    if callable(func_or_environment):
        func, _environment = func_or_environment, None
    else:
        func, _environment = None, func_or_environment

    if func is not None:
        @functools.wraps(func)
        def wrapper(environment, *args, **kwargs):
            assert environment in ('production', 'test')
            if not fabric.api.env.hosts:
                # allow overriding the hosts by using fab's -H option
                fabric.api.env.hosts = [getattr(APP, environment)]
            fabric.api.env.environment = environment
            return fabric.api.execute(func, APP, *args, **kwargs)
        wrapper.execute_inner = func
        return fabric.api.task(wrapper)
    else:
        def decorator(_func):
            _wrapper = task_app_from_environment(_func).wrapped
            wrapper = functools.wraps(_wrapper)(functools.partial(_wrapper, _environment))
            wrapper.execute_inner = _wrapper.execute_inner
            return fabric.api.task(wrapper)
        return decorator


from .deployment import *
from .varnish import *
from .other import *

__all__ += deployment.__all__ + varnish.__all__+ other.__all__

if _compat.PY2:  # https://bugs.python.org/issue21720
    __all__ = map(str, __all__)
