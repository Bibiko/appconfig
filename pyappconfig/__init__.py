# pyappconfig - remote control for DLCE apps

from __future__ import unicode_literals

from ._compat import pathlib

__all__ = ['PKG_DIR', 'REPOS_DIR', 'TEMPLATE_DIR']

PKG_DIR = pathlib.Path(__file__).parent
REPOS_DIR = PKG_DIR.parent
TEMPLATE_DIR = PKG_DIR / 'templates'
