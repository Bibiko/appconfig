# pyappconfig - remote control for DLCE apps

from __future__ import unicode_literals

from ._compat import pathlib

from . import config

__all__ = ['PKG_DIR', 'REPOS_DIR', 'CONFIG_FILE', 'APPS']

PKG_DIR = pathlib.Path(__file__).parent

REPOS_DIR = PKG_DIR.parent

CONFIG_FILE = REPOS_DIR / 'apps.ini'

APPS = config.Config.from_file(CONFIG_FILE)
