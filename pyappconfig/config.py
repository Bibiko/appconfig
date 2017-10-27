# config.py - load apps.ini and hosts.ini into name/object dicts

"""Configuration of DLCE apps.

.. note::

    Some fabric tasks require additional information like

    - ssh config
    - environment variables
"""

from __future__ import unicode_literals

from ._compat import pathlib

import attr
from clldutils import inifile

from . import REPOS_DIR

__all__ = ['APPS', 'HOSTS']


class Config(dict):

    def __init__(self, cls, filename):
        parser = inifile.INI.from_file(filename)
        objs = [cls(name=section, **dict(parser.items(section)))
                for section in parser.sections()]
        super(Config, self).__init__((obj.name, obj) for obj in objs)


RemotePath = pathlib.PurePosixPath


@attr.s
class App(object):

    _filename = REPOS_DIR / 'apps.ini'

    name = attr.ib()
    port = attr.ib(convert=int)
    test = attr.ib()
    production = attr.ib()
    deploy_duration = attr.ib(convert=int)
    domain = attr.ib(default=None)
    workers = attr.ib(convert=int, default=3)
    require_deb = attr.ib(convert=lambda s: s.strip().split(), default=attr.Factory(list))
    require_pip = attr.ib(convert=lambda s: s.strip().split(), default=attr.Factory(list))
    with_blog = attr.ib(convert=lambda s: inifile.INI.BOOLEAN_STATES[s.lower()], default='0')
    pg_collkey = attr.ib(convert=lambda s: inifile.INI.BOOLEAN_STATES[s.lower()], default='0')
    pg_unaccent = attr.ib(convert=lambda s: inifile.INI.BOOLEAN_STATES[s.lower()], default='0')
    error_email = attr.ib(default='lingweb@shh.mpg.de')

    @property
    def src(self):
        """directory containing a clone of the app's source repository.
        """
        return self.venv / 'src' / self.name

    @property
    def venv(self):
        """directory containing virtualenvs for clld apps.
        """
        return RemotePath('/usr/venvs') / self.name

    @property
    def home(self):
        """home directory of the user running the app.
        """
        return RemotePath('/home') / self.name

    @property
    def www(self):
        return self.home / 'www'

    @property
    def config(self):
        """path of the app's config file.
        """
        return self.home / 'config.ini'

    @property
    def logs(self):
        """directory containing the app's logfiles.
        """
        return RemotePath('/var/log') / self.name

    @property
    def error_log(self):
        return self.logs / 'error.log'

    def bin(self, command):
        """bin directory of the app's virtualenv.
        """
        return str(self.venv / 'bin' / command)

    @property
    def supervisor(self):
        return RemotePath('/etc/supervisor/conf.d') / ('%s.conf' % self.name)

    @property
    def nginx_location(self):
        return RemotePath('/etc/nginx/locations.d') / ('%s.conf' % self.name)

    @property
    def nginx_htpasswd(self):
        return RemotePath('/etc/nginx/locations.d') / ('%s.htpasswd' % self.name)

    @property
    def nginx_site(self):
        return RemotePath('/etc/nginx/sites-enabled') / self.name

    @property
    def sqlalchemy_url(self):
        return 'postgresql://{0}@/{0}'.format(self.name)


@attr.s
class Host(object):

    _filename = REPOS_DIR / 'hosts.ini'

    name = attr.ib()
    hostname = attr.ib()


APPS, HOSTS = (Config(cls, cls._filename) for cls in (App, Host))
