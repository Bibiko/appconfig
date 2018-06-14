# appconfig - remote control for DLCE apps

import pathlib

from . import config

__all__ = ['PKG_DIR', 'APPS_DIR', 'CONFIG_FILE', 'APPS']

PKG_DIR = pathlib.Path(__file__).parent

APPS_DIR = PKG_DIR.parent / 'apps'

CONFIG_FILE = APPS_DIR / 'apps.ini'

APPS = config.Config.from_file(CONFIG_FILE)

# TODO: consider https://pypi.python.org/pypi/pyvbox
#       for scripting tests with virtualbox
