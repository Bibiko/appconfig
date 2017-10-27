# __main__.py - command line interface

from __future__ import unicode_literals

import sys

from clldutils.clilib import ArgumentParserWithLogging, command

from . import REPOS_DIR
from .config import APPS

__all__ = ['main']


@command()
def check(args):  # pragma: no cover
    ports = set()
    for app in APPS.values():
        if app.port in ports:
            args.log.error('{0}: Duplicate port: {1}'.format(app.name, app.port))
        ports.add(app.port)
        if not (REPOS_DIR / app.name).exists():
            args.log.warn('{0}: Missing config dir'.format(app.name))


def main():  # pragma: no cover
    parser = ArgumentParserWithLogging('pyappconfig')
    sys.exit(parser.main())


if __name__ == '__main__':
    main()
