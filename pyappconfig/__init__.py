# pyappconfig - remote control for DLCE apps

from pyappconfig._compat import pathlib

from fabric.api import env

PKG_DIR = pathlib.Path(__file__).parent
REPOS_DIR = PKG_DIR.parent
TEMPLATE_DIR = PKG_DIR / 'templates'

__all__ = ['PKG_DIR', 'REPOS_DIR', 'TEMPLATE_DIR']

env.use_ssh_config = True
