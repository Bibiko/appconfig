"""
Configuration of DLCE apps.

.. note::

    Some fabric tasks require additional information like

    - ssh config
    - environment variables
"""
import attr
from clldutils.inifile import INI
from clldutils.path import Path

from pyappconfig.util import REPOS_DIR


@attr.s
class Server(object):
    name = attr.ib()
    hostname = attr.ib()


@attr.s
class App(object):
    name = attr.ib()
    port = attr.ib(convert=int)
    deploy_duration = attr.ib(convert=int)
    test = attr.ib()
    production = attr.ib()
    domain = attr.ib(default=None)
    workers = attr.ib(convert=int, default=3)
    require_deb = attr.ib(convert=lambda s: s.strip().split(), default=attr.Factory(list))
    require_pip = attr.ib(convert=lambda s: s.strip().split(), default=attr.Factory(list))
    with_blog = attr.ib(convert=lambda s: INI.BOOLEAN_STATES[s.lower()], default='0')
    pg_collkey = attr.ib(convert=lambda s: INI.BOOLEAN_STATES[s.lower()], default='0')
    pg_unaccent = attr.ib(convert=lambda s: INI.BOOLEAN_STATES[s.lower()], default='0')
    error_email = attr.ib(default='lingweb@shh.mpg.de')

    @property
    def src(self):
        """directory containing a clone of the app's source repository.
        """
        return self.venv.joinpath('src', self.name)

    @property
    def venv(self):
        """directory containing virtualenvs for clld apps.
        """
        return Path('/usr/venvs').joinpath(self.name)

    @property
    def home(self):
        """home directory of the user running the app.
        """
        return Path('/home').joinpath(self.name)

    @property
    def www(self):
        return self.home.joinpath('www')

    @property
    def config(self):
        """path of the app's config file.
        """
        return self.home.joinpath('config.ini')

    @property
    def logs(self):
        """directory containing the app's logfiles.
        """
        return Path('/var/log').joinpath(self.name)

    @property
    def error_log(self):
        return self.logs.joinpath('error.log')

    def bin(self, command):
        """bin directory of the app's virtualenv.
        """
        return str(self.venv.joinpath('bin', command))

    @property
    def supervisor(self):
        return Path('/etc/supervisor/conf.d').joinpath('%s.conf' % self.name)

    @property
    def nginx_location(self):
        return Path('/etc/nginx/locations.d').joinpath('%s.conf' % self.name)

    @property
    def nginx_htpasswd(self):
        return Path('/etc/nginx/locations.d').joinpath('%s.htpasswd' % self.name)

    @property
    def nginx_site(self):
        return Path('/etc/nginx/sites-enabled').joinpath(self.name)

    @property
    def sqlalchemy_url(self):
        return 'postgresql://{0}@/{0}'.format(self.name)


class Config(dict):
    def __init__(self, cls, fname):
        parser = INI.from_file(fname)
        objs = [cls(name=section, **dict(parser.items(section)))
                for section in parser.sections()]
        super(Config, self).__init__((obj.name, obj) for obj in objs)


APPS = Config(App, REPOS_DIR.joinpath('apps.ini'))
SERVERS = Config(Server, REPOS_DIR.joinpath('servers.ini'))
