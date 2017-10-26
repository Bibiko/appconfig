# cli.py - command line interface

from __future__ import unicode_literals

import sys

from clldutils.clilib import ArgumentParserWithLogging, command

from pyappconfig import REPOS_DIR


@command()
def check(args):  # pragma: no cover
    from pyappconfig.config import APPS, SERVERS

    ports = set()
    for app in APPS.values():
        if app.port in ports:
            args.log.error('{0}: Duplicate port: {1}'.format(app.name, app.port))
        ports.add(app.port)
        if app.test not in SERVERS:
            args.log.error('{0}: invalid test server: {1}'.format(app.name, app.test))
        if app.production not in SERVERS:
            args.log.error(
                '{0}: invalid production server: {1}'.format(app.name, app.production))
        if not REPOS_DIR.joinpath(app.name).exists():
            args.log.warn('{0}: Missing config dir'.format(app.name))


def main():  # pragma: no cover
    parser = ArgumentParserWithLogging('pyappconfig')
    sys.exit(parser.main())
