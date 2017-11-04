# config.py - load apps.ini into name/object dict

"""Configuration of DLCE apps.

.. note::

    Some fabric tasks require additional information like

    - ssh config
    - environment variables
"""

from __future__ import unicode_literals

import io
import copy
import argparse
import warnings
import configparser

from ._compat import PY2, pathlib, iteritems, itervalues

from . import helpers

__all__ = ['Config']


class Config(dict):

    @classmethod
    def from_file(cls, filename, value_cls=None, validate=True):
        if value_cls is None:
            value_cls = App
        parser = ConfigParser.from_file(filename)
        items = {s: value_cls(**parser[s]) for s in parser.sections()
                if not s.startswith('_')}
        inst = cls(items)
        if validate:
            inst.validate()
        return inst

    def validate(self):
        mismatch = [(name, app.name) for name, app in iteritems(self)
                    if name != app.name]
        if mismatch:
            raise ValueError('section/name mismatch: %r' % mismatch)
        ports = [app.port for app in itervalues(self)]
        duplicates = helpers.duplicates(ports)
        if duplicates:
            raise ValueError('duplicate port(s): %r' % duplicates)
        for app in itervalues(self):
            if not app.fabfile_dir.exists():
                warnings.warn('missing fabfile dir: %s' % app.name)


class ConfigParser(configparser.ConfigParser):

    _init_defaults = {
        'delimiters': ('=',),
        'comment_prefixes': ('#',),
        'inline_comment_prefixes': ('#',),
        'interpolation': configparser.ExtendedInterpolation(),
    }

    @classmethod
    def from_file(cls, filename, encoding='utf-8-sig', **kwargs):
        self = cls(**kwargs)
        if PY2 and isinstance(filename, pathlib.Path):  # pragma: no cover
            filename = str(filename)
        with io.open(filename, encoding=encoding) as fd:
            self.read_file(fd)
        return self

    def __init__(self, defaults=None, **kwargs):
        for k, v in iteritems(self._init_defaults):
            kwargs.setdefault(k, v)
        super(ConfigParser, self).__init__(defaults, **kwargs)


def getboolean(s):
    return ConfigParser.BOOLEAN_STATES[s.lower()]


def getwords(s):
    return s.strip().split()


class App(argparse.Namespace):

    _fields = dict.fromkeys([
        'name', 'test', 'production',
        'domain', 'error_email',
        'sqlalchemy_url', 'app_pkg',
    ])

    _fields.update({
        'port': int,
        'with_blog': getboolean,
        'workers': int,
        'deploy_duration': int,
        'require_deb': getwords,
        'require_pip': getwords,
        'pg_collkey': getboolean,
        'pg_unaccent': getboolean,
    })

    _fields.update(dict.fromkeys([
        'home_dir', 'www_dir',
        'config',
        'gunicorn_pid',
        'venv_dir', 'venv_bin', 'src_dir', 'download_dir',
        'alembic', 'gunicorn',
        'log_dir', 'access_log', 'error_log',
        'logrotate',
        'supervisor',
        'nginx_default_site', 'nginx_site', 'nginx_location', 'nginx_htpasswd',
    ], pathlib.PurePosixPath))

    def __init__(self, **kwargs):
        kw = self._fields.copy()
        for k, f in list(kw.items()):
            try:
                value = kwargs.pop(k)
            except KeyError:
                raise ValueError('missing attribute %r' % k)
            kw[k] = f(value) if f is not None else value
        if kwargs:
            raise ValueError('unknown attribute(s) %r' % kwargs)
        super(App, self).__init__(**kw)

    def replace(self, **kwargs):
        old, new = self.__dict__, self._fields.copy()
        for k, f in list(new.items()):
            if k in kwargs:
                value = f(kwargs.pop(k)) if f is not None else kwargs.pop(k)
            else:
                value = copy.copy(old[k])
            new[k] = value
        if kwargs:
            raise ValueError('unknown attribute(s) %r' % kwargs)
        inst = object.__new__(self.__class__)
        inst.__dict__ = new
        return inst

    @property
    def fabfile_dir(self):
        from . import REPOS_DIR
        return REPOS_DIR / self.name
