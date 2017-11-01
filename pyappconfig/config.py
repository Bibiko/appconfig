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
import configparser

from ._compat import pathlib, iteritems

__all__ = ['Config']


class Config(dict):

    @classmethod
    def from_file(cls, filename, value_cls=None):
        if value_cls is None:
            value_cls = App
        parser = ConfigParser.from_file(filename)
        items = {s: value_cls(**parser[s]) for s in parser.sections()
                if not s.startswith('_')}
        assert all(s == v.name for s, v in iteritems(items))
        return cls(items)


class ConfigParser(configparser.ConfigParser):

    _init_defaults = {
        'delimiters': ('=',),
        'comment_prefixes': ('#',),
        'interpolation': configparser.ExtendedInterpolation(),
    }

    @classmethod
    def from_file(cls, filename, encoding='utf-8-sig', **kwargs):
        self = cls(**kwargs)
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
        'home', 'config', 'www',
        'venv', 'venv_bin', 'gunicorn', 'src',
        'logs', 'error_log', 'logrotate',
        'supervisor', 'nginx_site', 'nginx_location', 'nginx_htpasswd',
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
